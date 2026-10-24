import numpy as np
import pandas as pd


def ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    # Only gains so far: 100, not the neutral 50 used for flat or first bars.
    return (100 - 100 / (1 + rs)).where(~((loss == 0) & (gain > 0)), 100.0).fillna(50)


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    prev_close = df["Close"].shift()
    tr = pd.concat(
        [df["High"] - df["Low"], (df["High"] - prev_close).abs(), (df["Low"] - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False).mean()


def vwap(df: pd.DataFrame) -> pd.Series:
    """Session VWAP, reset each trading day."""
    typical = (df["High"] + df["Low"] + df["Close"]) / 3
    pv = typical * df["Volume"]
    day = df.index.date
    cum_vol = df["Volume"].groupby(day).cumsum().replace(0, np.nan)
    return (pv.groupby(day).cumsum() / cum_vol).fillna(typical)


def hist_vol(close: pd.Series, window: int = 20) -> float:
    """Annualised historical volatility from daily closes."""
    rets = np.log(close / close.shift()).dropna().tail(window)
    return float(rets.std() * np.sqrt(252)) if len(rets) > 1 else 0.3


def intraday_sigma_per_min(df: pd.DataFrame, minutes_per_bar: int = 5) -> float:
    """Typical rupee move per minute, from the last two sessions of intraday candles."""
    if df.empty:
        return 0.0
    days = sorted(set(df.index.date))[-2:]
    close = df.loc[[d in days for d in df.index.date], "Close"]
    diffs = close.groupby(close.index.date).diff().dropna()  # skip overnight gaps
    return float(diffs.std() / np.sqrt(minutes_per_bar)) if len(diffs) > 2 else 0.0
