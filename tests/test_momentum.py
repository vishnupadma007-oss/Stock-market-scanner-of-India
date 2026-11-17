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


def test_chart_turn_fires_on_a_turn_against_a_call():
    from agents.momentum import chart_turn
    up = [100 + i * 0.2 for i in range(25)]
    down = [up[-1] - 0.6, up[-1] - 1.4, up[-1] - 2.4, up[-1] - 3.6, up[-1] - 4.8, up[-1] - 6.0]
    closes = up + down
    df = _bars_today(closes, highs=[c + 0.1 for c in closes])
    df["Open"] = [closes[0]] + closes[:-1]
    assert chart_turn(df, "up") is not None
    assert chart_turn(df, "down") is None


def test_chart_turn_quiet_while_the_trend_holds():
    from agents.momentum import chart_turn
    closes = [100 + i * 0.2 for i in range(30)]
    df = _bars_today(closes)
    df["Open"] = [closes[0]] + closes[:-1]
    assert chart_turn(df, "up") is None
