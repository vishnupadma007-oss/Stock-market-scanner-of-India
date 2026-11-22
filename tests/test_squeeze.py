from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd

from agents import squeeze

IST = ZoneInfo("Asia/Kolkata")


def day(direction=1, breakout=True, quiet_votes=None, start="09:15"):
    """30 min of drift, a quiet hour (12 candles), then a breakout candle and a few more."""
    t0 = pd.Timestamp(f"2026-11-20 {start}", tz=IST)
    rows, p = [], 100.0
    for i in range(6):  # morning trend the trade's way (keeps VWAP and EMAs on the right side)
        o = p; p += 0.3 * direction
        rows.append((o, max(o, p) + 0.05, min(o, p) - 0.05, p, 1000))
    votes = quiet_votes or ([1] * 8 + [-1] * 4)  # 8 green, 4 red -> lead 4
    for v in votes:  # quiet hour: tiny candles
        o = p; c = o + 0.02 * v * direction
        rows.append((o, max(o, c) + 0.01, min(o, c) - 0.01, c, 1200 if v > 0 else 600))
        p = c
    if breakout:
        o = p; p = o + 0.6 * direction
        rows.append((o, max(o, p) + 0.02, min(o, p) - 0.02, p, 5000))
    for _ in range(3):
        o = p; p += 0.05 * direction
        rows.append((o, max(o, p), min(o, p), p, 900))
    idx = [t0 + pd.Timedelta(minutes=5 * i) for i in range(len(rows))]
    return pd.DataFrame(rows, columns=["Open", "High", "Low", "Close", "Volume"], index=idx)


def test_up_signal_on_breakout():
    bars = day(1)
    sig = list(squeeze.day_signals(bars, typ=0.2, start="09:15"))
    assert len(sig) == 1
    j, d, info = sig[0]
    assert d == 1 and info["greens"] == 8 and info["reds"] == 4
    assert bars.index[j].strftime("%H:%M") == "10:45"


def test_down_signal_mirror():
    bars = day(-1)
    (_, d, info), = list(squeeze.day_signals(bars, typ=0.2, start="09:15"))
    assert d == -1 and info["reds"] == 8


def test_no_breakout_no_signal():
    assert list(squeeze.day_signals(day(1, breakout=False), typ=0.2, start="09:15")) == []


def test_split_vote_no_signal():
    bars = day(1, quiet_votes=[1, -1] * 6)
    assert list(squeeze.day_signals(bars, typ=0.2, start="09:15")) == []


def test_box_too_wide_for_usual_range():
    assert list(squeeze.day_signals(day(1), typ=0.01, start="09:15")) == []


def test_live_signal_only_on_last_closed_candle():
    bars = day(1)
    upto = bars.loc[:"2026-11-20 10:45+05:30"]
    sig = squeeze.live_signal(upto, 0.2, {"from": "09:15"})
    assert sig and sig["direction"] == "up" and sig["bar"] == "10:45" and "8 green vs 4 red" in sig["why"]
    assert squeeze.live_signal(bars, 0.2, {"from": "09:15"}) is None  # the breakout is old by now
    assert squeeze.live_signal(bars, 0.2, {"from": "09:15"}, last_n=2) is None
    assert squeeze.live_signal(bars.loc[:"2026-11-20 10:50+05:30"], 0.2, {"from": "09:15"}, last_n=2)


def test_usual_range_needs_history():
    bars = day(1)
    assert squeeze.usual_range(bars, bars.index[-1].date() + timedelta(days=1)) is None
    many = pd.concat([day(1).set_axis(day(1).index + pd.Timedelta(days=k)) for k in range(6)])
    r = squeeze.usual_range(many, (many.index[-1] + pd.Timedelta(days=1)).date())
    assert r and r > 0


def test_snapshot_bars():
    b = squeeze.SnapshotBars()
    t0 = datetime(2026, 11, 20, 9, 15, 30, tzinfo=IST)
    for i in range(11):  # one snapshot a minute, 09:15:30 .. 09:25:30
        b.add("X", t0 + timedelta(minutes=i), 100 + i, 1000 * (i + 1))
    out = b.bars("X", t0 + timedelta(minutes=10, seconds=10))  # 09:25:40: two candles closed
    assert list(out.index.strftime("%H:%M")) == ["09:15", "09:20"]
    assert out.iloc[0].Open == 100 and out.iloc[0].Close == 104 and out.iloc[1].Open == 105
    assert out.iloc[1].Volume == 5000
