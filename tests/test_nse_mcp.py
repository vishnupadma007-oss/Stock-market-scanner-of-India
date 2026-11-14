from agents.nse_mcp import history_frame


def test_history_frame_orders_and_renames():
    rows = [{"date": "2026-11-13", "open": 2, "high": 3, "low": 1, "close": 2.5, "volume": 10},
            {"date": "2026-11-12", "open": 1, "high": 2, "low": 0.5, "close": 1.5, "volume": 5}]
    df = history_frame(rows)
    assert list(df.columns) == ["Open", "High", "Low", "Close", "Volume"]
    assert df.index[0].day == 12 and df["Close"].iloc[-1] == 2.5


def test_history_frame_empty():
    assert history_frame([]).empty
