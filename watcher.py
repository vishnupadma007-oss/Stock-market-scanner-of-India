"""Market watcher: runs the rule-based agents on live INDmoney data all day and stays quiet
until something happens. It prints one line per event, so Claude (or you) only needs to
look when there is a signal:

    SIGNAL {...}   new paper trade opened (rule-based agents said TRADE)
    EXIT {...}     paper trade closed (target reached, or square-off time)
    ERROR {...}    something needs attention (each distinct error at most once an hour)
    STATUS {...}   start of watching / market closed

Usage:  python watcher.py            (every 5 minutes during market hours)
        python watcher.py --once     (one scan, for testing)
"""
import argparse
import asyncio
import csv
import json
import sys
import time as clock
from datetime import datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

from agents import daymode, macro, news, psychology
from agents.chart_reader import read_chart
from agents.config import load_config
from agents.costs import round_trip_charges
from agents.decision import decide
from agents.forecast import reversal_target
from agents.indicators import intraday_sigma_per_min
from agents.indmoney import IndMoney, LoginRequired, pick_option
from agents.regime import assess
from agents.risk import plan
from agents.scanner import stock_profile
from agents.sectors import SECTORS, sector_of

IST = ZoneInfo("Asia/Kolkata")
NIFTY_KEY, VIX_KEY = "INDI00012", "INDI00318"
TRADES = Path(__file__).resolve().parent / "journal" / "paper_trades.csv"
FIELDS = ["date", "opened", "symbol", "side", "contract", "underlying_key", "derivative_id",
          "qty", "entry_ask", "target_bid", "spread_pct", "hit_probability", "chart_score", "oi_type",
          "status", "closed", "exit_bid", "charges", "net_pnl", "claude_verdict", "notes"]

_errors_seen: dict[str, float] = {}
_daily: dict = {}  # once-a-day lookups: results calendar, crude contract


def usdinr_change() -> float | None:
    """Today's USD/INR % change (INDmoney has no rupee quote; Yahoo is fine for this)."""
    try:
        import yfinance as yf
        d = yf.Ticker("INR=X").history(period="5d", interval="1d")["Close"]
        return float(d.iloc[-1] / d.iloc[-2] - 1) * 100
    except Exception:
        return None


async def market_context(im: IndMoney, now: datetime) -> dict:
    """Sector, crude and rupee moves for the Macro agent; results calendar for the News agent."""
    today = now.date().isoformat()
    if _daily.get("date") != today:
        _daily.clear()
        _daily.update(date=today, results=news.results_calendar(), crude_key=await im.crude_key())
    keys = [k for k, _ in SECTORS.values()] + ([_daily["crude_key"]] if _daily["crude_key"] else [])
    changes = await im.day_changes(keys[:10])
    return {"results": _daily["results"], "usdinr": usdinr_change(),
            "crude": changes.get(_daily["crude_key"]),
            "sectors": {name: changes.get(k) for name, (k, _) in SECTORS.items()}}


def emit(kind: str, payload: dict) -> None:
    if kind == "ERROR":
        key = payload.get("error", "")[:120]
        if clock.time() - _errors_seen.get(key, 0) < 3600:
            return
        _errors_seen[key] = clock.time()
    print(f"{kind} {json.dumps(payload, default=str)}", flush=True)


def load_trades() -> list[dict]:
    if not TRADES.exists():
        return []
    with open(TRADES, newline="") as f:
        return list(csv.DictReader(f))


def save_trades(rows: list[dict]) -> None:
    TRADES.parent.mkdir(exist_ok=True)
    with open(TRADES, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)


def _t(hhmm: str) -> time:
    h, m = hhmm.split(":")
    return time(int(h), int(m))


async def manage_open_trades(im: IndMoney, trades: list[dict], now: datetime, cfg: dict) -> None:
    square_off = now.time() >= _t(cfg["square_off_time"])
    for t in (t for t in trades if t["status"] == "OPEN"):
        chain = await im.option_chain(t["underlying_key"], strikes_around_atm=10)
        leg = next((r[side] for r in chain.get("option_chain_data", [])
                    for side in ("call_data", "put_data") if r[side]["derivative_id"] == t["derivative_id"]), None)
        if leg is None:
            continue
        bid = leg.get("buy_price", leg.get("bp")) or 0
        if bid >= float(t["target_bid"]) or square_off:
            qty, entry = int(t["qty"]), float(t["entry_ask"])
            charges = round_trip_charges(entry, bid, qty, cfg["charges"])["total"]
            t.update(status="TARGET" if bid >= float(t["target_bid"]) else "SQUARED_OFF",
                     closed=now.strftime("%H:%M"), exit_bid=bid, charges=round(charges, 2),
                     net_pnl=round((bid - entry) * qty - charges, 2))
            emit("EXIT", {k: t[k] for k in ("symbol", "contract", "status", "entry_ask", "exit_bid", "qty", "net_pnl")})


async def scan(im: IndMoney, trades: list[dict], now: datetime, cfg: dict) -> None:
    day = daymode.load(now.date())
    if day["mode"] == "no_trade":
        return
    cfg = daymode.apply(cfg, day)
    nifty = await im.candles(NIFTY_KEY, "1day", "1y")
    vix = await im.candles(VIX_KEY, "1day", "14d")
    mkt = assess(nifty, vix, cfg)
    if mkt["no_trade"]:
        return

    ctx = await market_context(im, now)
    universe = set(cfg["universe"]) - set(day["avoid"])
    today = now.date().isoformat()
    taken = {t["contract"] for t in trades if t["date"] == today}
    trades_today = sum(t["date"] == today for t in trades)

    for side, category, ok in (("gainer", "top-gainers", mkt["gainers_ok"]),
                               ("loser", "top-losers", mkt["losers_ok"])):
        if not ok:
            continue
        movers = [m for m in await im.movers(category, 50)
                  if m["symbol"] in universe and abs(m["change_pct"]) >= cfg["min_move_pct"]][:cfg["top_n"]]
        for m in movers:
            daily = await im.candles(m["ind_key"], "1day", "1y")
            intraday = await im.candles(m["ind_key"], "5minute", "7d")
            if len(daily) < 25 or intraday.empty:
                continue
            profile = {**stock_profile(daily), "ltp": m["price"], "chg_1d": m["change_pct"]}
            chart = read_chart(intraday, profile, side)
            if chart["score"] < cfg["min_chart_score"] + mkt["threshold_adj"]:
                continue  # skip the option-chain call for weak charts

            option = pick_option(await im.option_chain(m["ind_key"]), side, cfg["strike_choice"])
            if option is None or option["contract"] in taken:
                continue
            prev_close = m.get("previous_close") or m["price"] / (1 + m["change_pct"] / 100)
            forecast = reversal_target(intraday, float(prev_close), side)
            risk = plan(option, trades_today, now, cfg, sigma_per_min=intraday_sigma_per_min(intraday),
                        spread_pct=option["spread_pct"], forecast=forecast)
            extras = [news.assess(m["symbol"], side, m["change_pct"], now.date(), await im.news(m["ind_key"]),
                                  ctx["results"], intraday, cfg)]
            if cfg.get("use_macro", True):
                extras.append(macro.assess(m["symbol"], side, m["change_pct"],
                                           ctx["sectors"].get(sector_of(m["symbol"])), ctx["crude"],
                                           ctx["usdinr"], cfg))
            crowd = psychology.assess(side, m["price"], m["change_pct"],
                                      await im.futures_oi_change(m["symbol"], option["expiry"]),
                                      m.get("52_week_high"), m.get("52_week_low"),
                                      m.get("circuit_upper_limit"), m.get("circuit_lower_limit"), cfg)
            extras.append(crowd)
            decision = decide(side, mkt, chart, risk, None, cfg, extras)
            if decision["verdict"] != "TRADE":
                continue

            row = {f: "" for f in FIELDS}
            row.update(date=today, opened=now.strftime("%H:%M"), symbol=m["symbol"], side=side,
                       contract=option["contract"], underlying_key=m["ind_key"],
                       derivative_id=option["derivative_id"], qty=risk["qty"], entry_ask=option["ask"],
                       target_bid=risk["target_premium"], spread_pct=round(option["spread_pct"], 2),
                       hit_probability=round(risk["hit_probability"]), chart_score=chart["score"],
                       oi_type=crowd["oi_type"],
                       status="OPEN")
            trades.append(row)
            taken.add(option["contract"])
            trades_today += 1
            emit("SIGNAL", {
                **{k: row[k] for k in ("symbol", "side", "contract", "qty", "entry_ask", "target_bid",
                                       "spread_pct", "hit_probability", "chart_score")},
                "spot": m["price"], "day_change_pct": m["change_pct"], "lot_size": option["lot_size"],
                "net_profit_at_target": round(risk["net_profit"]), "square_off": cfg["square_off_time"],
                "chart_signals": [s for s, _ in chart["signals"]], "market": mkt["notes"],
                "news_and_macro": [n for e in extras for n in e["notes"]],
                "news_driven": extras[0]["news_driven"], "decision_score": decision["score"],
                "forecast": {"level": forecast.get("level") and round(forecast["level"], 2),
                             "basis": forecast["basis"],
                             "option_price_there": risk["forecast_premium"] and round(risk["forecast_premium"], 2)},
                "day_mode": day["mode"],
                "crowd": {"oi_type": crowd["oi_type"], "would_score": crowd["would_score"],
                          "would_block": crowd["would_block"]},
            })


async def cycle(cfg: dict) -> None:
    now = datetime.now(IST)
    trades = load_trades()
    async with IndMoney() as im:
        await manage_open_trades(im, trades, now, cfg)
        if _t(cfg["entry_start"]) <= now.time() <= _t(cfg["entry_end"]):
            await scan(im, trades, now, cfg)
    save_trades(trades)


def market_open(now: datetime) -> bool:
    return now.weekday() < 5 and time(9, 15) <= now.time() <= time(15, 30)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true", help="run one cycle and exit")
    ap.add_argument("--interval", type=int, default=5, help="minutes between scans")
    args = ap.parse_args()
    cfg = load_config()

    emit("STATUS", {"watching": True, "interval_min": args.interval, "time": datetime.now(IST)})
    while True:
        now = datetime.now(IST)
        if args.once or market_open(now):
            try:
                asyncio.run(cycle(cfg))
            except LoginRequired as e:
                emit("ERROR", {"error": str(e), "fix": "python -m agents.indmoney login"})
                sys.exit(2)
            except Exception as e:  # keep watching through temporary network/server errors
                emit("ERROR", {"error": f"{type(e).__name__}: {e}"})
        if args.once:
            return
        if now.time() > time(15, 30) or now.weekday() >= 5:
            emit("STATUS", {"watching": False, "reason": "market closed", "time": now})
            return
        clock.sleep(args.interval * 60)


if __name__ == "__main__":
    main()
