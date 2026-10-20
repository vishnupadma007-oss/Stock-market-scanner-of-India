"""Expectations agent: is the news already priced in?

Before results (or any big news) a stock often moves on what people expect. If it already ran
up, was talked up in the news and trades above analysts' targets, good results are expected
and only a big beat will lift it further; a fall is likely if results merely match ("sell the
news"). The reverse holds when pessimism is priced in.

Signals:
  run-up    stock vs Nifty over 1 and 4 weeks before the event
  hype      how much and how positively the stock was covered in the days before
  analysts  price vs the average analyst target (INDmoney consensus)
  reaction  after the event: did the price move the way the news says? If not, it was priced in.

    python -m agents.expectations TECHM
"""
import sys
from datetime import date, datetime, timedelta

import pandas as pd

from . import intel


def run_up(daily: pd.DataFrame, nifty: pd.DataFrame, before: date) -> dict:
    """Stock and relative-to-Nifty % change over 5 and 20 sessions up to the close before `before`."""
    s = daily[daily.index.date < before]["Close"]
    n = nifty[nifty.index.date < before]["Close"]
    out = {}
    for days in (5, 20):
        if len(s) > days and len(n) > days:
            stock = (s.iloc[-1] / s.iloc[-1 - days] - 1) * 100
            index = (n.iloc[-1] / n.iloc[-1 - days] - 1) * 100
            out[f"stock_{days}d"], out[f"vs_nifty_{days}d"] = round(stock, 1), round(stock - index, 1)
    return out


def hype(symbol: str, before: datetime, days: int = 7) -> dict:
    """Coverage of the stock in the intelligence log over the days before the event."""
    names = [(before.date() - timedelta(d)).isoformat() for d in range(days, -1, -1)]
    items = [i for i in intel.load(*names) if symbol in i["symbols"] and i["kind"] == "news"
             and i["time"] < before.strftime("%Y-%m-%d %H:%M:%S")]
    toned = [i["sentiment"] for i in items if i["sentiment"]]
    return {"stories": len(items), "tone": round(sum(toned) / len(toned), 2) if toned else 0.0,
            "days": days}


def analysts(details: dict) -> dict:
    """From INDmoney get_indian_stocks_details(segments=["analyst"]) for one stock."""
    f = details.get("analyst_forecast") or {}
    t, c = f.get("target_price") or {}, f.get("consensus") or {}
    if not t.get("mean"):
        return {}
    return {"upside_pct": t.get("upside_per"), "target": t.get("mean"), "high": t.get("high"),
            "analysts": t.get("num_analysts"), "buy_pct": c.get("buy_per")}


def assess(run: dict, coverage: dict, street: dict) -> dict:
    """Priced-in score: +100 = good news fully expected, -100 = bad news fully expected."""
    score, notes = 0, []
    rel = run.get("vs_nifty_20d")
    if rel is not None:
        if rel >= 10:
            score += 35; notes.append(f"Ran up {rel:+.1f}% vs Nifty in 4 weeks: good news largely expected")
        elif rel >= 5:
            score += 20; notes.append(f"Outperformed Nifty by {rel:+.1f}% in 4 weeks")
        elif rel <= -10:
            score -= 35; notes.append(f"Lagged Nifty by {rel:.1f}% in 4 weeks: bad news largely expected")
        elif rel <= -5:
            score -= 20; notes.append(f"Underperformed Nifty by {rel:.1f}% in 4 weeks")
    if coverage.get("stories", 0) >= 5:
        if coverage["tone"] >= 0.3:
            score += 20; notes.append(f"{coverage['stories']} upbeat stories before the event (hype)")
        elif coverage["tone"] <= -0.3:
            score -= 20; notes.append(f"{coverage['stories']} gloomy stories before the event")
    up = street.get("upside_pct")
    if up is not None:
        if up <= 0:
            score += 25; notes.append(f"Trades {-up:.1f}% above the average analyst target (₹{street['target']:,.0f})")
        elif up <= 5:
            score += 10; notes.append(f"Only {up:.1f}% below the average analyst target")
        elif up >= 20:
            score -= 15; notes.append(f"{up:.1f}% upside to analyst targets still")
    score = max(-100, min(100, score))
    if score >= 50:
        label, bar = "largely priced in", "needs a clear beat to rise; an in-line result can fall"
    elif score >= 20:
        label, bar = "partly priced in", "needs a solid beat to rise much"
    elif score <= -50:
        label, bar = "pessimism priced in", "a merely decent result can lift it"
    elif score <= -20:
        label, bar = "some pessimism priced in", "an in-line result may hold up"
    else:
        label, bar = "not priced in", "the result itself will drive the move"
    return {"priced_in": score, "label": label, "bar": bar, "notes": notes}


def reaction(news_view: str, move_pct: float) -> str | None:
    """After the event: news_view "strong"/"good" or "weak", move_pct the stock's move since."""
    if news_view in ("strong", "good") and move_pct <= -1:
        return f"Good news but the stock is {move_pct:+.1f}%: it was priced in (sell the news)"
    if news_view == "weak" and move_pct >= 1:
        return f"Weak news but the stock is {move_pct:+.1f}%: the bad news was priced in (relief)"
    return None


def adjust_forecast(view: dict, expectation: dict) -> dict:
    """Lower a forecast's confidence when its direction is already priced in."""
    p = expectation.get("priced_in", 0)
    if (view["direction"] == "up" and p >= 50) or (view["direction"] == "down" and p <= -50):
        return {**view, "confidence": max(0, view["confidence"] - 25),
                "priced_in_note": f"{expectation['label']}: {expectation['bar']}"}
    return view


def day_move(daily: pd.DataFrame, day: date) -> float | None:
    """The stock's % move on `day` (None if there is no candle for it yet)."""
    if len(daily) < 2 or daily.index[-1].date() != day:
        return None
    return round((daily["Close"].iloc[-1] / daily["Close"].iloc[-2] - 1) * 100, 2)


async def stock_key(im, symbol: str) -> str:
    rows = await im.call("lookup_ind_keys", names=[symbol], filter_type="IN_STOCKS")
    return next(r["ind_key"] for r in rows if r.get("ind_key", "").startswith("INDS"))


async def for_symbol(im, symbol: str, key: str, event_time: datetime, nifty: pd.DataFrame | None = None,
                     news_view: str | None = None) -> dict:
    """Full check for one stock (2-3 INDmoney calls). `news_view` ("strong"/"good"/"weak") adds
    the reaction check: is the price already going against the news?"""
    daily = await im.candles(key, "1day", "1y")
    if nifty is None:
        nifty = await im.candles("INDI00012", "1day", "1y")
    details = (await im.quotes([key], ["analyst"])).get(key, {})
    out = {"run_up": run_up(daily, nifty, event_time.date()), "hype": hype(symbol, event_time),
           "analysts": analysts(details), "day_move_pct": day_move(daily, event_time.date())}
    out.update(assess(out["run_up"], out["hype"], out["analysts"]))
    if news_view and out["day_move_pct"] is not None:
        out["reaction"] = reaction(news_view, out["day_move_pct"])
    return out


def main(argv: list[str]) -> None:
    import asyncio
    import json
    from .indmoney import IndMoney

    async def go(symbol):
        async with IndMoney() as im:
            return await for_symbol(im, symbol, await stock_key(im, symbol), datetime.now())
    print(json.dumps(asyncio.run(go(argv[1].upper())), indent=1))


if __name__ == "__main__":
    main(sys.argv)
