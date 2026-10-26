import asyncio
import json
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd

import review
import watcher
from agents.config import load_config
import numpy as np

from agents import momentum
from tests.test_agents import intraday
from tests.test_watcher import chain

IST = ZoneInfo("Asia/Kolkata")
NOW = datetime(2026, 10, 21, 11, 0, tzinfo=IST)
CFG = {**load_config(), "strike_choice": "ITM1",
       "teams": {"movers": {"capital": 30000}, "news": {"capital": 200000, "auto_trade": True}}}


class FakeIndMoney:
    pick_contract = watcher.IndMoney.pick_contract

    def __init__(self, move):
        self.move = move

    async def candles(self, key, interval, lookback):
        # A steady climb in the move's direction, with a small dip: a healthy trend.
        path = 1750 + np.sign(self.move) * (np.arange(30) * 1.2 - 3 * (np.arange(30) % 4 == 3))
        if interval == "1day":
            idx = pd.bdate_range(end="2026-10-20", periods=60, tz="Asia/Kolkata")
            c = 1700 + np.sign(self.move) * np.arange(60) * 2.0
            return pd.DataFrame({"Open": c, "High": c * 1.01, "Low": c * 0.99, "Close": c, "Volume": 1e6}, index=idx)
        return intraday(path)

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


def test_restart_does_not_log_the_same_idea_twice(monkeypatch, tmp_path):
    monkeypatch.setattr(watcher, "IDEAS", tmp_path / "ideas.csv")
    for _ in range(2):  # two watcher runs on the same day
        watcher._daily.clear()
        watcher.reset_daily(NOW.date().isoformat())
        watcher.add_idea("TECHM", "up", 80, "intel", "x", {"label": "not priced in"}, NOW)
    assert (tmp_path / "ideas.csv").read_text().count("TECHM") == 1


def test_trend_checker_backs_or_blocks_the_news():
    rising = intraday(1750 + np.arange(30) * 1.2 - 3 * (np.arange(30) % 4 == 3))
    up = momentum.read_trend(rising, {"dist_sma20_atr": 1.0}, "up")
    assert up["score"] >= 60, up["signals"]
    assert momentum.read_trend(rising, {"dist_sma20_atr": 1.0}, "down")["score"] < 60  # chart against a PUT
    fading = intraday(np.r_[np.linspace(1750, 1800, 15), np.linspace(1800, 1760, 15)])
    assert momentum.read_trend(fading, {"dist_sma20_atr": 1.0}, "up")["score"] < 60  # news up, chart rolling over


def test_news_team_skips_when_the_chart_disagrees():
    class Fading(FakeIndMoney):
        async def candles(self, key, interval, lookback):
            if interval == "1day":
                return await super().candles(key, interval, lookback)
            return intraday(np.r_[np.linspace(1750, 1800, 15), np.linspace(1800, 1760, 15)])
    idea("up")
    trades = []
    asyncio.run(watcher.news_team(Fading(move=1.2), trades, NOW, {**CFG, "capital": 200000}))
    assert trades == [] and "TECHM" in watcher._daily["trend_failed"]


def test_news_team_uses_half_its_money_and_skips_cheap_options(monkeypatch):
    idea("up")
    trades = []
    asyncio.run(watcher.news_team(FakeIndMoney(move=1.2), trades, NOW, {**CFG, "capital": 200000}))
    assert float(trades[0]["entry_ask"]) * int(trades[0]["qty"]) <= 100000
    idea("up")
    from agents import indmoney
    real = indmoney.pick_option
    monkeypatch.setattr(indmoney, "pick_option", lambda *a: {**real(*a), "ask": 1.85, "est_premium": 1.85})
    trades = []
    asyncio.run(watcher.news_team(FakeIndMoney(move=1.2), trades, NOW, {**CFG, "capital": 200000}))
    assert trades == []


def _candles(last_vol, green=True, days=3):
    """Three days of 5-min candles; the last candle today carries `last_vol`."""
    frames = []
    for d in range(days, -1, -1):
        idx = pd.date_range(f"2026-10-{21 - d} 09:15", periods=12, freq="5min", tz="Asia/Kolkata")
        frames.append(pd.DataFrame({"Open": 100.0, "High": 101.0, "Low": 99.0, "Close": 100.0, "Volume": 1000.0}, index=idx))
    df = pd.concat(frames)
    df.iloc[-1, df.columns.get_loc("Volume")] = last_vol
    df.iloc[-1, df.columns.get_loc("Close")] = 100.5 if green else 99.5
    return df


def test_early_signals_need_volume_and_the_order_book():
    book = lambda bid, ask: {"NSE": {"total_bid_qty": bid, "total_ask_qty": ask}}
    assert momentum.early_signals(_candles(2500), book(30000, 10000), "up")["ok"]
    assert not momentum.early_signals(_candles(1200), book(30000, 10000), "up")["ok"]          # no volume surge
    assert not momentum.early_signals(_candles(2500), book(10000, 12000), "up")["ok"]          # sellers dominate
    assert not momentum.early_signals(_candles(2500, green=False), book(30000, 10000), "up")["ok"]  # red candle
    assert momentum.early_signals(_candles(2500, green=False), book(10000, 30000), "down")["ok"]
    assert not momentum.early_signals(_candles(2500), {"NSE": {}}, "up")["ok"]                 # empty book


def test_news_team_enters_early_on_volume_and_order_book():
    class Early(FakeIndMoney):
        async def candles(self, key, interval, lookback):
            if interval == "1day":
                return await super().candles(key, interval, lookback)
            return _candles(2500)

        async def quotes(self, keys, segments=None):
            q = await super().quotes(keys, segments)
            if segments == ["depth"]:
                q["INDS01469"]["market_depth"] = {"NSE": {"total_bid_qty": 30000, "total_ask_qty": 10000}}
            return q

    cfg = {**CFG, "capital": 200000, "teams": {**CFG["teams"], "news": {**CFG["teams"]["news"], "early_entry": True,
                                                                         "early_pct": 0.2, "early_volume_x": 1.5,
                                                                         "early_book_x": 1.5}}}
    idea("up")
    trades = []
    asyncio.run(watcher.news_team(Early(move=0.3), trades, NOW, cfg))  # 0.3%: under the 0.5% confirmation
    assert len(trades) == 1 and trades[0]["notes"].startswith("Early entry")
    idea("up")
    trades = []
    off = {**cfg, "teams": {**cfg["teams"], "news": {**cfg["teams"]["news"], "early_entry": False}}}
    asyncio.run(watcher.news_team(Early(move=0.3), trades, NOW, off))
    assert trades == []  # without the early rule, 0.3% still waits


def test_one_lot_allowed_when_half_the_money_is_less_than_a_lot():
    c = {"max_capital_per_trade": 0.5}
    cheap_lot = {"ask": 10.0, "lot_size": 500}     # Rs 5,000: fits in half of Rs 16,696
    big_lot = {"ask": 30.0, "lot_size": 400}       # Rs 12,000: more than half, less than all
    assert watcher.capital_share(cheap_lot, {"capital": 16696}, c) == 0.5
    assert watcher.capital_share(big_lot, {"capital": 16696}, c) == 1.0
    from agents.risk import plan
    r = plan({**big_lot, "est_premium": 30.0, "delta": 0.55}, 0, NOW, {**CFG, "capital": 16696, "max_capital_per_trade": 1.0})
    assert r["qty"] == 400  # exactly one lot
