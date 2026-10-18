"""Chart Reader agent: reads today's 5-minute candles for signs that the move is reversing.

For a top gainer it looks for exhaustion (buy PE); for a top loser it looks for a bounce
(buy CE). Losers are handled by mirroring the chart upside-down, so one set of rules
covers both sides.
"""
import pandas as pd

from .indicators import ema, rsi, vwap


def _mirror(df: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame({
        "Open": -df["Open"], "High": -df["Low"], "Low": -df["High"],
        "Close": -df["Close"], "Volume": df["Volume"],
    }, index=df.index)


def _today(df: pd.DataFrame) -> pd.DataFrame:
    return df[df.index.date == df.index[-1].date()]


def read_chart(intraday: pd.DataFrame, profile: dict, side: str) -> dict:
    """side: "gainer" (looking for a fall) or "loser" (looking for a rise)."""
    if intraday.empty or len(_today(intraday)) < 6:
        return {"score": 0, "signals": [("Not enough candles yet today", 0)], "summary": "No data"}

    flip = side == "loser"
    df = _mirror(intraday) if flip else intraday
    words = ("low", "bounce", "green", "red", "above", "below") if flip else \
            ("high", "fall", "red", "green", "below", "above")
    extreme, move, weak_c, strong_c, weak_side, strong_side = words

    full = df.assign(vwap=vwap(df), ema9=ema(df["Close"], 9), ema21=ema(df["Close"], 21),
                     rsi=rsi(df["Close"]))
    today = _today(full)
    last = today.iloc[-1]
    price = abs(last["Close"])
    # In the mirrored chart RSI is already flipped, so "extreme" always means >= 70 here.
    rsi_now, rsi_peak = last["rsi"], today["rsi"].max()
    real_rsi = 100 - rsi_now if flip else rsi_now

    signals = []

    def add(cond, text, pts):
        if cond:
            signals.append((text, pts))

    add(last["Close"] < last["vwap"], f"Price {weak_side} VWAP: buyers/sellers losing control", 20)
    add(last["ema9"] < last["ema21"], f"9-EMA crossed {weak_side} 21-EMA on 5-min", 15)
    add(rsi_peak >= 70 and rsi_now <= rsi_peak - 15,
        f"RSI was extreme today and has cooled off (now {real_rsi:.0f})", 15)

    bars_since_extreme = len(today) - 1 - int(today["High"].values.argmax())
    day_extreme = today["High"].max()
    recent = today.tail(3)
    add(bars_since_extreme >= 3 and (recent["High"] < day_extreme - 0.003 * price).all(),
        f"Day {extreme} made {bars_since_extreme} candles ago and not retested", 15)

    body = (recent["Close"] - recent["Open"]).abs()
    wick = recent["High"] - recent[["Open", "Close"]].max(axis=1)
    add(((wick > 2 * body) & (wick > 0.003 * price)).any(),
        f"Rejection wick at the {extreme} in the last 3 candles", 10)

    last6 = today.tail(6)
    weak_vol = last6.loc[last6["Close"] < last6["Open"], "Volume"].sum()
    strong_vol = last6.loc[last6["Close"] >= last6["Open"], "Volume"].sum()
    add(weak_vol > strong_vol, f"Volume heavier on {weak_c} candles recently", 10)

    sign = -1 if flip else 1
    stretched = sign * profile["dist_sma20_atr"] >= 2 or sign * profile["chg_1w"] >= 8
    add(stretched, "Stretched on the daily chart (far from 20-day average / big 1-week move)", 15)

    add(bars_since_extreme <= 1, f"Still making new {extreme}s: momentum alive, too early", -30)
    add(last["Close"] - last["vwap"] > 0.015 * price and last["ema9"] > last["ema21"],
        f"Trading well {strong_side} VWAP with rising EMAs: strong trend", -15)

    score = max(0, min(100, sum(p for _, p in signals)))
    if score >= 60:
        summary = f"Chart shows exhaustion; a {move} looks likely."
    elif score >= 40:
        summary = f"Early signs of a {move}; wait for confirmation."
    else:
        summary = f"No clear {move} yet; the trend is still in control."
    return {"score": score, "signals": signals, "summary": summary,
            "vwap": float(abs(last["vwap"])), "rsi": float(real_rsi)}
