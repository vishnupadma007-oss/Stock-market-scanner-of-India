"""Trend Checker for the news team: is the stock's chart going the news's way, with strength left?

The movers team's Chart Reader looks for a REVERSAL (a gainer fading). The news team bets the
other way: that the news keeps the move going. So before it buys, this agent checks the 5-minute
and daily charts for a healthy trend in the trade's direction, and marks down entries that chase
a move that is already stretched. A falling stock ("down") is read on the mirrored chart, so one
set of rules covers both directions.

Score 0-100; the news team trades only at `teams.news.min_trend_score` (default 60) or above.
"""
import pandas as pd

from .chart_reader import _mirror, _today
from .indicators import ema, rsi, vwap


def read_trend(intraday: pd.DataFrame, profile: dict, direction: str) -> dict:
    """direction "up" (buying a CALL) or "down" (buying a PUT)."""
    # Two 5-minute candles (09:25) are enough to act on overnight news: averages and RSI also use
    # the previous sessions, and the 6-candle checks simply wait until those candles exist.
    if intraday.empty or len(_today(intraday)) < 2:
        return {"score": 0, "signals": [("Not enough candles yet today", 0)]}
    down = direction == "down"
    df = _mirror(intraday) if down else intraday
    words = ("below", "falling", "lows", "selling") if down else ("above", "rising", "highs", "buying")
    side, trend, extreme, flow = words

    full = df.assign(vwap=vwap(df), ema9=ema(df["Close"], 9), ema21=ema(df["Close"], 21), rsi=rsi(df["Close"]))
    today = _today(full)
    last = today.iloc[-1]
    price = abs(float(last["Close"])) or 1.0
    r = float(last["rsi"])
    signals = []

    def add(cond, text, pts):
        if cond:
            signals.append((text, pts))

    add(last["Close"] > last["vwap"], f"Price {side} VWAP: the day's {flow} is in control", 20)
    add(last["ema9"] > last["ema21"], f"9-EMA {side} 21-EMA on 5-min: short-term trend {trend}", 15)
    add(55 <= r <= 75, f"RSI {r if not down else 100 - r:.0f}: healthy momentum, not exhausted", 15)
    add(r > 80, f"RSI {r if not down else 100 - r:.0f}: overbought/oversold, late to the move", -15)

    last6 = today.tail(6)
    if len(last6) >= 6:
        add(last6["Low"].tail(3).min() > last6["Low"].head(3).min(),
            f"Higher {'highs' if down else 'lows'} on the last 6 candles: buyers stepping in on dips" if not down
            else "Lower highs on the last 6 candles: sellers stepping in on bounces", 15)
        up_vol = float(last6.loc[last6["Close"] >= last6["Open"], "Volume"].sum())
        dn_vol = float(last6.loc[last6["Close"] < last6["Open"], "Volume"].sum())
        add(up_vol > dn_vol, f"Volume heavier on {'red' if down else 'green'} candles: real {flow}", 10)
        # Post-news fade / distribution guard: last 3 candles all below 9-EMA with counter-trend volume dominating
        add((last6["Close"].tail(3) < last6["ema9"].tail(3)).all() and dn_vol > 1.2 * up_vol,
            f"Last 3 candles broke { 'above' if down else 'below' } 9-EMA on counter-trend volume: news move fading", -15)

    day_extreme = float(today["High"].max())
    bars_since = int(today["High"].values[::-1].argmax())  # from the latest touch of the extreme
    add(bars_since <= 3 and last["Close"] >= day_extreme - 0.005 * price,
        f"Near the day's {'low' if down else 'high'}, made recently: the move is still alive", 10)
    stretched = (last["Close"] - last["vwap"]) / price * 100
    add(stretched > 2.5, f"{stretched:.1f}% {side} VWAP: stretched, chasing the move", -15)

    sign = -1 if down else 1
    dist = float(profile.get("dist_sma20_atr", 0.0)) * sign
    add(dist > 0, f"Daily chart agrees: {'below' if down else 'above'} the 20-day average", 15)
    add(dist >= 3, "Far from the 20-day average on the daily chart: much of the move is done", -10)

    score = max(0, min(100, sum(p for _, p in signals)))
    return {"score": score, "signals": signals}


def early_signals(intraday: pd.DataFrame, depth: dict, direction: str,
                  volume_x: float = 1.5, book_x: float = 1.5) -> dict:
    """Early entry for the news team (before the stock has moved the full confirmation %):
    the latest 5-minute candle trades `volume_x` times the usual volume, closes the news's way
    without an adverse rejection wick (closes in the top half of its range for 'up', bottom half
    for 'down'), and the NSE order book holds `book_x` times more buyers than sellers (for "up";
    the reverse for "down"). Order-book imbalance leads price over seconds to minutes; volume shows
    real buying or selling. No history of NSE order books exists, so this rule is judged on paper."""
    up = direction == "up"
    notes, ok = [], True
    if intraday.empty or len(intraday) < 13:
        return {"ok": False, "volume_x": None, "book_x": None, "notes": ["Not enough candles for an early entry"]}
    last = intraday.iloc[-1]
    # Usual volume at this time of day on earlier days (opening candles are always heavy),
    # or the last hour's candles when there is no such history.
    t, d = intraday.index[-1].time(), intraday.index[-1].date()
    same_time = intraday[(intraday.index.time == t) & (intraday.index.date < d)]["Volume"]
    usual = float(same_time.mean() if len(same_time) >= 2 else intraday["Volume"].iloc[-13:-1].mean()) or 1.0
    vx = float(last["Volume"]) / usual
    rng = float(last["High"] - last["Low"])
    strong_close = ((float(last["Close"] - last["Low"]) >= 0.4 * rng) if up
                    else (float(last["High"] - last["Close"]) >= 0.4 * rng)) if rng > 0 else True
    with_news = ((last["Close"] > last["Open"]) if up else (last["Close"] < last["Open"])) and strong_close
    if vx < volume_x or not with_news:
        ok = False
    notes.append(f"Volume {vx:.1f}x usual on a {'green' if last['Close'] > last['Open'] else 'red'} candle")
    nse = (depth or {}).get("NSE") or {}
    bid, ask = float(nse.get("total_bid_qty") or 0), float(nse.get("total_ask_qty") or 0)
    if bid <= 0 or ask <= 0:
        return {"ok": False, "volume_x": round(vx, 2), "book_x": None, "notes": notes + ["NSE order book empty"]}
    bx = bid / ask if up else ask / bid
    if bx < book_x:
        ok = False
    notes.append(f"Order book: {'buyers' if up else 'sellers'} {bx:.1f}x {'sellers' if up else 'buyers'}")
    return {"ok": ok, "volume_x": round(vx, 2), "book_x": round(bx, 2), "notes": notes}
