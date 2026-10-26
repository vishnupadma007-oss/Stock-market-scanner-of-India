import pytest

import watcher


@pytest.fixture(autouse=True)
def keep_journal_clean(monkeypatch, tmp_path):
    """Tests must never write into the real journal."""
    monkeypatch.setattr(watcher, "IDEAS", tmp_path / "news_ideas.csv")
    monkeypatch.setattr(watcher, "HELD", tmp_path / "held_setups.csv")
    monkeypatch.setattr(watcher, "FILINGS_LOG", tmp_path / "announcements.csv")
    # No network in tests: the reaction analyst's price history comes from Yahoo.
    monkeypatch.setattr(watcher, "results_reaction", lambda item, now: {"notes": []})
    monkeypatch.setattr(watcher.reaction, "typical_move", lambda symbol: 1.8)
    monkeypatch.setattr(watcher.intel, "DIR", tmp_path / "intel")  # never read the real news log
    monkeypatch.setattr(watcher, "GUARD_LOG", tmp_path / "news_guard.csv")
    monkeypatch.setattr(watcher, "SKIPS_DIR", tmp_path / "skips")
