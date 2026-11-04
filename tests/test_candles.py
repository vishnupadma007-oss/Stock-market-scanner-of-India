import pandas as pd

from agents import candles


def frame(rows):
    return pd.DataFrame(rows, columns=["Open", "High", "Low", "Close"])


FALL = [(100 - i, 100.2 - i, 98.8 - i, 99 - i) for i in range(8)]  # steady 5-min decline
RISE = [(100 + i, 101.2 + i, 99.8 + i, 101 + i) for i in range(8)]


def test_hammer_after_a_fall():
    df = frame(FALL + [(92.0, 92.1, 90.0, 92.05)])
    assert ("Hammer", 1) in candles.detect(df)


def test_bearish_engulfing_after_a_rise():
    df = frame(RISE + [(108.0, 109.2, 107.9, 109.0), (109.3, 109.4, 107.5, 107.7)])
    assert ("Bearish engulfing", -1) in candles.detect(df)


def test_no_reversal_pattern_without_a_prior_move():
    flat = [(100, 100.3, 99.7, 100.1)] * 8
    assert all(n != "Hammer" for n, _ in candles.detect(frame(flat + [(100.0, 100.05, 98.0, 100.02)])))


def test_observe_mode_gives_notes_but_no_points():
    df = frame(FALL + [(92.0, 92.1, 90.0, 92.05)])
    extra = candles.as_extra(df, "loser", {"candles": {"points": 0}})
    assert extra["points"] == 0 and "Hammer" in extra["notes"][0]
    assert candles.as_extra(df, "loser", {"candles": {"points": 5}})["points"] == 5
