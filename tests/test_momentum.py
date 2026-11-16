def _bars_today(closes, highs=None, start="2026-11-16 09:15"):
    import pandas as pd
    idx = pd.date_range(start, periods=len(closes), freq="5min", tz="Asia/Kolkata")
    highs = highs or [c + 1 for c in closes]
    return pd.DataFrame({"Open": closes, "High": highs, "Low": [c - 1 for c in closes], "Close": closes,
                         "Volume": [1000] * len(closes)}, index=idx)


def test_faded_after_giving_back_the_gap():
    from agents.momentum import faded
    df = _bars_today([7850, 7840, 7800, 7760, 7732], highs=[7860, 7845, 7805, 7765, 7735])
    assert "gave back" in faded(df, "up")


def test_not_faded_when_holding_the_move():
    from agents.momentum import faded
    df = _bars_today([100, 100.5, 101, 101.4, 101.6])
    assert faded(df, "up") is None
