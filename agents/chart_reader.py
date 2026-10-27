"""Chart Reader agent: reads today's 5-minute candles for signs that the move is reversing.

For a top gainer it looks for exhaustion (buy PE); for a top loser it looks for a bounce
(buy CE). Losers are handled by mirroring the chart upside-down, so one set of rules
covers both sides.

Includes microstructure confluence checks:
- Price vs session VWAP and 9/21 EMA cross
- Extreme RSI cooling and multi-swing RSI divergence
- Unretested session extreme and rejection wicks
- Climax volume passive absorption at the session extreme
- Reversing vs continuing candle volume balance and active liquidity-cascade guard
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

    # Counted from the latest touch of the extreme: a retest of the high is a fresh high.
    bars_since_extreme = int(today["High"].values[::-1].argmax())
    day_extreme = today["High"].max()
    recent = today.tail(3)
    add(bars_since_extreme >= 3 and (recent["High"] < day_extreme - 0.003 * price).all(),
        f"Day {extreme} made {bars_since_extreme} candles ago and not retested", 15)

    body = (recent["Close"] - recent["Open"]).abs()
    wick = recent["High"] - recent[["Open", "Close"]].max(axis=1)
    add(((wick > 2 * body) & (wick > 0.003 * price)).any(),
        f"Rejection wick at the {extreme} in the last 3 candles", 10)

    # Climax volume passive absorption at the day's extreme: extreme bar had >= 2x median volume
    # and left a significant rejection wick (>= 35% of bar range).
    ext_idx = int(today["High"].values.argmax())
    ext_bar = today.iloc[ext_idx]
    med_vol = float(today["Volume"].median()) or 1.0
    ext_rng = float(ext_bar["High"] - ext_bar["Low"])
    ext_wick = float(ext_bar["High"] - max(ext_bar["Open"], ext_bar["Close"]))
    add(med_vol > 0 and float(ext_bar["Volume"]) >= 2.0 * med_vol and ext_rng > 0.002 * price
        and ext_wick >= 0.35 * ext_rng,
        f"Climax volume absorption at the day's {extreme} ({float(ext_bar['Volume']) / med_vol:.1f}x median volume)", 10)

    # Multi-swing RSI divergence: price retested within 0.25% of day extreme at least 3 bars after an
    # earlier RSI peak, but with RSI >= 6 pts weaker.
    if len(today) >= 8:
        early_slice = today.iloc[:-3]
        late_slice = today.iloc[-3:]
        if (early_slice["rsi"].max() >= 68
                and late_slice["High"].max() >= day_extreme - 0.0025 * price
                and late_slice["rsi"].max() <= early_slice["rsi"].max() - 6
                and bars_since_extreme >= 2):
            add(True, f"Momentum divergence at the {extreme}: price held near peak on weaker RSI", 10)

    last6 = today.tail(6)
    weak_vol = last6.loc[last6["Close"] < last6["Open"], "Volume"].sum()
    strong_vol = last6.loc[last6["Close"] >= last6["Open"], "Volume"].sum()
    add(weak_vol > strong_vol, f"Volume heavier on {weak_c} candles recently", 10)
    add(len(last6) >= 4 and strong_vol > 2 * weak_vol, f"Volume still piling into {strong_c} candles", -15)

    sign = -1 if flip else 1
    stretched = sign * profile.get("dist_sma20_atr", 0.0) >= 2 or sign * profile.get("chg_1w", 0.0) >= 8
    add(stretched, "Stretched on the daily chart (far from 20-day average / big 1-week move)", 15)

    add(bars_since_extreme <= 1, f"Still making new {extreme}s: momentum alive, too early", -35)
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
