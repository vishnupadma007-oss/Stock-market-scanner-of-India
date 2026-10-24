"""Order-flow / early-movement detectors from 5-minute candles (user's "Early Movement:
Derivatives & Order Flow Strategies" whitepaper, 24 Oct 2026).

Each detector returns, per candle, +1 (buy a CALL), -1 (buy a PUT) or 0:
  squeeze    Bollinger Bands (20, 2) inside the Keltner Channel (20 EMA +- 1.5 ATR) for the 6
             previous candles, then the first close outside the bands with relative volume >= 2x
             (same time of day on earlier days), on the right side of VWAP.
  spring     price pokes below the last hour's low on light volume and closes back above it
             (CALL); upthrust: pokes above the last hour's high and closes back below it with a
             long upper wick (PUT).
  vwap       close crosses VWAP with relative volume >= 1.8x and a close in the bar's upper half
             (CALL) / lower half (PUT).
  cvd        absorption: a new 6-candle low while estimated buying pressure (CVD) rose over those
             candles (CALL); a new 6-candle high while it fell (PUT).

CVD here is an estimate from candles (close location x volume): true CVD needs every trade
with its aggressor side, which no free Indian data source gives. The paper's option-OI
velocity, gamma exposure (GEX) and order-book checks need live data with no history, so they
cannot be backtested here (see `python backtest_orderflow.py`).
"""
import numpy as np
import pandas as pd

from .indicators import atr, ema, vwap

DETECTORS = ("squeeze", "spring", "vwap", "cvd")


def features(df: pd.DataFrame) -> pd.DataFrame:
    """Indicators on a stock's 5-minute candles (several days, so averages have history)."""
    f = df[["Open", "High", "Low", "Close", "Volume"]].copy()
    f["vwap"] = vwap(df)
    mid, sd = f["Close"].rolling(20).mean(), f["Close"].rolling(20).std()
    f["bb_up"], f["bb_lo"] = mid + 2 * sd, mid - 2 * sd
    e, a = ema(f["Close"], 20), atr(df, 20)
    f["squeeze_on"] = (f["bb_up"] < e + 1.5 * a) & (f["bb_lo"] > e - 1.5 * a)
    # Relative volume: this candle vs the median at the same time on the previous 10 days.
    tod = f.index.time
    usual = f.groupby(tod)["Volume"].transform(lambda v: v.shift(1).rolling(10, min_periods=3).median())
    f["rvol"] = f["Volume"] / usual.replace(0, np.nan)
    rng = (f["High"] - f["Low"]).replace(0, np.nan)
    f["clv"] = ((f["Close"] - f["Low"]) - (f["High"] - f["Close"])) / rng  # -1 (close at low) .. +1 (at high)
    f["delta"] = (f["clv"].fillna(0) * f["Volume"])
    f["cvd"] = f["delta"].groupby(f.index.date).cumsum()
    f["bar"] = f.groupby(f.index.date).cumcount()  # 0 = 09:15 candle
    return f


def signals(f: pd.DataFrame) -> pd.DataFrame:
    """+1 / -1 / 0 per candle for every detector."""
    out = pd.DataFrame(0, index=f.index, columns=list(DETECTORS))
    c, h, l, o = f["Close"], f["High"], f["Low"], f["Open"]
    day = pd.Series(f.index.date, index=f.index)

    was_squeezed = f["squeeze_on"].shift(1).rolling(6).sum() == 6
    out.loc[was_squeezed & (c > f["bb_up"]) & (f["rvol"] >= 2.0) & (c > f["vwap"]), "squeeze"] = 1
    out.loc[was_squeezed & (c < f["bb_lo"]) & (f["rvol"] >= 2.0) & (c < f["vwap"]) & (f["delta"] < 0), "squeeze"] = -1

    # Last hour's range within the same day (12 candles before this one).
    prev_low = l.groupby(day).transform(lambda s: s.shift(1).rolling(12).min())
    prev_high = h.groupby(day).transform(lambda s: s.shift(1).rolling(12).max())
    body = (c - o).abs()
    upper_wick = h - np.maximum(o, c)
    out.loc[(l < prev_low) & (c > prev_low) & (f["rvol"] < 1.0), "spring"] = 1
    out.loc[(h > prev_high) & (c < prev_high) & (upper_wick >= 2 * body), "spring"] = -1

    below_before = (c.shift(1) < f["vwap"].shift(1)) & (day == day.shift(1))
    above_before = (c.shift(1) > f["vwap"].shift(1)) & (day == day.shift(1))
    out.loc[below_before & (c > f["vwap"]) & (f["rvol"] >= 1.8) & (f["clv"] > 0), "vwap"] = 1
    out.loc[above_before & (c < f["vwap"]) & (f["rvol"] >= 1.8) & (f["clv"] < 0), "vwap"] = -1

    low6 = l.groupby(day).transform(lambda s: s.shift(1).rolling(6).min())
    high6 = h.groupby(day).transform(lambda s: s.shift(1).rolling(6).max())
    cvd_change = f["cvd"] - f["cvd"].groupby(day).shift(6)
    out.loc[(l < low6) & (cvd_change > 0), "cvd"] = 1
    out.loc[(h > high6) & (cvd_change < 0), "cvd"] = -1
    return out


def latest(df: pd.DataFrame) -> dict:
    """Detectors firing on the latest candle: {"squeeze": 1, ...} (only non-zero ones)."""
    if len(df) < 40:
        return {}
    s = signals(features(df)).iloc[-1]
    return {k: int(v) for k, v in s.items() if v}
