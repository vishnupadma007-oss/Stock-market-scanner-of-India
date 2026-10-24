import numpy as np
import pandas as pd

from agents import orderflow


def days(n_days=12, bars=75, vol=1000.0):
    frames = []
    for d in range(n_days):
        idx = pd.date_range(f"2026-10-{1 + d:02d} 09:15", periods=bars, freq="5min", tz="Asia/Kolkata")
        frames.append(pd.DataFrame({"Open": 100.0, "High": 100.2, "Low": 99.8, "Close": 100.0, "Volume": vol}, index=idx))
    return pd.concat(frames)


def test_squeeze_breakout_with_volume_gives_a_call():
    df = days()
    rng = np.random.default_rng(0)
    df["Close"] = 100 + rng.normal(0, 0.3, len(df))
    df["Open"] = df["Close"].shift().fillna(100)
    df["High"] = df[["Open", "Close"]].max(axis=1) + 0.3
    df["Low"] = df[["Open", "Close"]].min(axis=1) - 0.3
    # Last day: 10 very tight candles (the squeeze), then a big green breakout candle on 3x volume.
    last = df.index[-20:]
    df.loc[last[:10], ["Open", "High", "Low", "Close"]] = [100.0, 100.02, 99.98, 100.0]
    df.loc[last[10], ["Open", "High", "Low", "Close", "Volume"]] = [100.0, 101.5, 99.99, 101.4, 3000.0]
    sig = orderflow.signals(orderflow.features(df))
    assert sig.loc[last[10], "squeeze"] == 1


def test_spring_and_upthrust():
    df = days(n_days=4, bars=30)  # earlier days give the usual volume for each time of day
    t = df.index[-10]
    df.loc[t, ["Open", "High", "Low", "Close", "Volume"]] = [100.0, 100.1, 99.0, 100.05, 500.0]  # poke below, close back in
    u = df.index[-5]
    df.loc[u, ["Open", "High", "Low", "Close", "Volume"]] = [100.0, 101.0, 99.9, 99.95, 1000.0]  # poke above, long wick
    sig = orderflow.signals(orderflow.features(df))
    assert sig.loc[t, "spring"] == 1 and sig.loc[u, "spring"] == -1


def test_latest_needs_history():
    assert orderflow.latest(days(n_days=1, bars=10)) == {}
