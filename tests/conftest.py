import pytest

import watcher


@pytest.fixture(autouse=True)
def keep_journal_clean(monkeypatch, tmp_path):
    """Tests must never write into the real journal."""
    monkeypatch.setattr(watcher, "IDEAS", tmp_path / "news_ideas.csv")
    monkeypatch.setattr(watcher, "HELD", tmp_path / "held_setups.csv")
    monkeypatch.setattr(watcher, "FILINGS_LOG", tmp_path / "announcements.csv")
