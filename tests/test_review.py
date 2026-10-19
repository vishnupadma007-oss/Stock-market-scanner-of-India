import pandas as pd

import review

COLS = ["date", "opened", "symbol", "side", "contract", "underlying_key", "derivative_id", "qty",
        "entry_ask", "target_bid", "spread_pct", "hit_probability", "chart_score", "oi_type", "status",
        "closed", "exit_bid", "charges", "net_pnl", "claude_verdict", "notes"]


def trade(day, side, status, net, verdict="", opened="10:30", spread=0.6):
    return dict(zip(COLS, [day, opened, "SBIN", side, f"SBIN-{side}-{net}", "K", "D", 750, 20.0, 20.4,
                           spread, 80, 70, "long unwinding", status, "11:00", 20.4, 90, net, verdict, ""]))


def write(tmp_path, rows):
    path = tmp_path / "paper_trades.csv"
    pd.DataFrame(rows, columns=COLS).to_csv(path, index=False)
    return path


def test_review_summarises_and_waits_for_enough_trades(tmp_path):
    rows = [trade("2026-10-19", "loser", "TARGET", 150, "TRADE"),
            trade("2026-10-19", "gainer", "SQUARED_OFF", -1500, "SKIP", opened="12:15", spread=1.4),
            trade("2026-10-19", "loser", "OPEN", 0)]
    df = review.load(write(tmp_path, rows))
    assert len(df) == 2  # open trades are not counted
    text = review.review(df, "2026-10-19", "2026-10-18")
    assert "2 trades, 50% hit target" in text
    assert "Claude said SKIP (avoided): 1 trades" in text
    assert "over 1%" in text and "12:00" in text
    assert "NOT YET: 2 of 30" in text
    assert "By crowd positioning" in text and "long unwinding" in text


def test_review_ready_after_thirty_trades(tmp_path):
    rows = [trade(f"2026-11-{d:02d}", "loser", "TARGET", 150) for d in range(1, 31)]
    text = review.review(review.load(write(tmp_path, rows)), "2026-11-30", "2026-10-18")
    assert "READY: 30 trades" in text


def test_last_change_date(tmp_path):
    p = tmp_path / "changes.md"
    p.write_text("| Date | Change |\n|---|---|\n| 2026-10-18 | a |\n| 2026-11-02 | b |\n")
    assert review.last_change_date(p) == "2026-11-02"
    assert review.last_change_date(tmp_path / "missing.md") == "0000-00-00"


def test_review_with_no_trades(tmp_path):
    assert "No closed paper trades yet" in review.review(review.load(tmp_path / "none.csv"), "2026-10-19", "x")
