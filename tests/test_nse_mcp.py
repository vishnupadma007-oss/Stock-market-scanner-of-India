from agents.nse_mcp import history_frame


def test_history_frame_orders_and_renames():
    rows = [{"date": "2026-11-13", "open": 2, "high": 3, "low": 1, "close": 2.5, "volume": 10},
            {"date": "2026-11-12", "open": 1, "high": 2, "low": 0.5, "close": 1.5, "volume": 5}]
    df = history_frame(rows)
    assert list(df.columns) == ["Open", "High", "Low", "Close", "Volume"]
    assert df.index[0].day == 12 and df["Close"].iloc[-1] == 2.5


def test_history_frame_empty():
    assert history_frame([]).empty


def test_parse_quote_reads_common_field_names():
    from agents.nse_mcp import parse_quote
    q = parse_quote({"symbol": "TCS", "ltp": "2,407.5", "prevClose": 2442.4, "volume": 3344738})
    assert q["price"] == 2407.5 and q["move_pct"] == -1.43 and q["volume"] == 3344738
    assert parse_quote({"data": {"lastPrice": 100, "pChange": 0.3}})["move_pct"] == 0.3
    assert parse_quote({"error": "No allstocks data available."}) is None
