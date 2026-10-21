import asyncio
import json
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd

import review
import watcher
from agents.config import load_config
from tests.test_watcher import chain

IST = ZoneInfo("Asia/Kolkata")
NOW = datetime(2026, 10, 21, 11, 0, tzinfo=IST)
CFG = {**load_config(), "strike_choice": "ITM1",
       "teams": {"movers": {"capital": 30000}, "news": {"capital": 200000, "auto_trade": True}}}


class FakeIndMoney:
    def __init__(self, move):
        self.move = move

    async def call(self, tool, **args):
        return [{"ind_key": "INDS01469", "name": "Tech Mahindra"}]

    async def quotes(self, keys, segments=None):
        return {"INDS01469": {"entity_stats": {"live_price": 1790, "day_change_percentage": self.move}}}

    async def option_chain(self, key):
        return chain()


def idea(direction="up", confidence=80, at=NOW):
    watcher._daily.clear()
    watcher.reset_daily(NOW.date().isoformat())
    watcher._daily["ideas"] = {"TECHM": {"direction": direction, "confidence": confidence, "source": "results",
                                         "reason": "Results strong", "priced_in": "not priced in", "at": at}}


def test_each_team_has_its_own_book():
    rows = [{"status": "OPEN", "strategy": "reversal", "entry_ask": "50", "qty": "600", "net_pnl": ""},
            {"status": "TARGET", "strategy": "results", "entry_ask": "40", "qty": "600", "net_pnl": "500"}]
    assert watcher.has_open(rows, "movers") and not watcher.has_open(rows, "news")
    assert watcher.account(rows, CFG, "movers") == (30000, 0.0)
    assert watcher.account(rows, CFG, "news") == (200500, 200500)


def test_news_team_trades_when_price_confirms(capsys):
    idea("up")
    trades = []
    asyncio.run(watcher.news_team(FakeIndMoney(move=1.2), trades, NOW, {**CFG, "capital": 200000}))
    assert len(trades) == 1 and trades[0]["strategy"] == "results" and trades[0]["contract"].endswith("CALL")
    kind, body = capsys.readouterr().out.strip().split(" ", 1)
    assert kind == "SIGNAL" and json.loads(body)["team"] == "news"
    # Already traded TECHM today: no second trade on the same idea.
    asyncio.run(watcher.news_team(FakeIndMoney(move=1.2), trades, NOW, {**CFG, "capital": 200000}))
    assert len(trades) == 1


def test_news_team_waits_for_confirmation_and_skips_weak_or_stale_ideas():
    for move, conf, at in ((0.2, 80, NOW),                       # price not moving yet
                           (-1.0, 80, NOW),                      # price going the other way
                           (5.0, 80, NOW),                       # move already used up
                           (1.2, 50, NOW),                       # confidence too low (e.g. priced in)
                           (1.2, 80, NOW.replace(hour=8))):      # idea too old
        idea("up", conf, at)
        trades = []
        asyncio.run(watcher.news_team(FakeIndMoney(move=move), trades, NOW, {**CFG, "capital": 200000}))
        assert trades == [], (move, conf, at)
    idea("down")
    trades = []
    asyncio.run(watcher.news_team(FakeIndMoney(move=-1.5), trades, NOW, {**CFG, "capital": 200000}))
    assert trades[0]["contract"].endswith("PUT")


def test_ideas_are_logged_once_per_direction(monkeypatch, tmp_path):
    monkeypatch.setattr(watcher, "IDEAS", tmp_path / "ideas.csv")
    watcher._daily.clear()
    watcher.reset_daily(NOW.date().isoformat())
    hot = {"priced_in": 80, "label": "largely priced in", "bar": "needs a clear beat"}
    watcher.add_idea("TECHM", "up", 80, "results", "strong", hot, NOW)
    watcher.add_idea("TECHM", "up", 85, "intel", "again", hot, NOW)
    watcher.add_idea("INFY", "neutral", 90, "intel", "x", {}, NOW)
    assert watcher._daily["ideas"]["TECHM"]["confidence"] == 60  # priced in: 85 - 25
    assert (tmp_path / "ideas.csv").read_text().count("\n") == 2  # header + one idea


def test_scoreboard():
    df = pd.DataFrame({"date": ["2026-10-21"] * 3, "strategy": ["reversal", "results", "intel"],
                       "net_pnl": [300.0, -100.0, 400.0], "net_pct": [1.0, -0.5, 1.2], "hit": [True, False, True]})
    text = "\n".join(review.scoreboard(df, "2026-10-21", {"movers": 30000, "news": 30000}, {"movers": 4, "news": 6}))
    assert "| movers | 4 | 1 | ₹300 | 1 | 100% | +1.00% | ₹300 | +1.0% |" in text
    assert "| news | 6 | 2 | ₹300 | 2 | 50% | +0.35% | ₹300 | +1.0% |" in text


def test_news_team_skips_ideas_whose_priced_in_check_failed():
    idea("up")
    watcher._daily["ideas"]["TECHM"]["priced_in"] = None  # e.g. INDmoney's hourly limit was hit
    trades = []
    asyncio.run(watcher.news_team(FakeIndMoney(move=1.2), trades, NOW, {**CFG, "capital": 200000}))
    assert trades == []
