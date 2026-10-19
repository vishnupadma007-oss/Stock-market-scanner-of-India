import asyncio
import json
from datetime import datetime
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pytest

import watcher
from agents.config import load_config
from agents.indmoney import candles_frame, pick_option
from tests.test_agents import SPIKE_THEN_FADE, intraday

IST = ZoneInfo("Asia/Kolkata")
CFG = {**load_config(), "capital": 200000}  # one TECHM lot (~₹30k) must fit the per-trade budget


def leg(did, slug, price, delta, bid, ask):
    return {"derivative_id": did, "slug": slug, "current_price": price, "lot_size": 600,
            "delta": delta, "buy_price": bid, "sell_price": ask}


def chain(put_bid=49.6, put_ask=50.1):
    """Shape copied from a real INDmoney TECHM option chain."""
    return {"entity_details": {"live_price": 1790}, "selected_expiry": "20261027",
            "option_chain_data": [
                {"strike_price": 1780, "call_data": leg("C1780", "techm-27-oct-1780-call", 30.8, 0.48, 30.5, 30.8),
                 "put_data": leg("P1780", "techm-27-oct-1780-put", 37.8, -0.52, 37.85, 38.35)},
                {"strike_price": 1800, "call_data": leg("C1800", "techm-27-oct-1800-call", 22.4, 0.39, 22.25, 22.5),
                 "put_data": leg("P1800", "techm-27-oct-1800-put", 49.55, -0.61, put_bid, put_ask)},
                {"strike_price": 1820, "call_data": leg("C1820", "techm-27-oct-1820-call", 16.2, 0.31, 16.1, 16.3),
                 "put_data": leg("P1820", "techm-27-oct-1820-put", 63.75, -0.7, 63.05, 64.2)}]}


def test_pick_option_uses_live_quotes():
    put = pick_option(chain(), "gainer", "ITM1")
    assert put["contract"] == "TECHM-27-OCT-1800-PUT" and put["ask"] == 50.1
    assert round(put["spread_pct"], 2) == 1.0
    call = pick_option(chain(), "loser", "ITM1")
    assert call["strike"] == 1780 and call["type"] == "CE"


def test_candles_frame():
    df = candles_frame([{"datetime_ist": "2026-10-16 09:15:00", "open": 1, "high": 2, "low": 0.5,
                         "close": 1.5, "volume": 10}])
    assert list(df.columns) == ["Open", "High", "Low", "Close", "Volume"] and str(df.index.tz) == "Asia/Kolkata"


class FakeIndMoney:
    def __init__(self, put_bid=49.6, headlines=(), sector_chg=0.3):
        self.put_bid, self.headlines, self.sector_chg = put_bid, list(headlines), sector_chg

    async def crude_key(self):
        return "CRUDE"

    async def day_changes(self, keys):
        return {k: (0.4 if k == "CRUDE" else self.sector_chg) for k in keys}

    async def news(self, key):
        return self.headlines

    async def futures_oi_change(self, symbol, expiry):
        return 6.0  # TECHM on 16 Oct: price +8.5%, OI +6% = long build-up

    async def candles(self, key, interval, lookback):
        if interval == "1day":
            idx = pd.bdate_range(end="2026-10-16", periods=120, tz=IST)
            c = np.full(120, 1650.0) if key not in ("INDI00012", "INDI00318") else \
                np.full(120, 14.0) if key == "INDI00318" else np.linspace(22000, 22100, 120)
            return pd.DataFrame({"Open": c, "High": c * 1.01, "Low": c * 0.99, "Close": c, "Volume": 3e6}, index=idx)
        return intraday(1700 + 10 * (SPIKE_THEN_FADE - 100))  # spike to 1800 then fade

    async def movers(self, category, limit):
        return [{"symbol": "TECHM", "ind_key": "INDS01469", "price": 1790, "change_pct": 8.48}] \
            if category == "top-gainers" else []

    async def option_chain(self, key, strikes_around_atm=4):
        return chain(put_bid=self.put_bid, put_ask=self.put_bid + 0.5)


@pytest.fixture(autouse=True)
def offline(monkeypatch, tmp_path):
    """No network in tests: empty results calendar, no rupee quote, no day-mode file."""
    monkeypatch.setattr(watcher.news, "results_calendar", lambda: {"TECHM": RESULTS})
    monkeypatch.setattr(watcher, "usdinr_change", lambda: None)
    monkeypatch.setattr(watcher.daymode, "PATH", tmp_path / "day_mode.json")
    monkeypatch.setattr(watcher.daymode.load, "__defaults__", (tmp_path / "day_mode.json",))
    watcher._daily.clear()


RESULTS = []
NOW = datetime(2026, 10, 16, 11, 0, tzinfo=IST)


def signals(fake, trades=None):
    trades = [] if trades is None else trades
    asyncio.run(watcher.scan(fake, trades, NOW, CFG))
    return trades


def test_fresh_news_behind_the_move_blocks_the_fade(capsys):
    news = [{"title": "TechM wins $1bn deal - 16 Oct, 2026", "sentiment": "positive"}]
    assert signals(FakeIndMoney(headlines=news)) == []


def test_results_day_blocks(capsys, monkeypatch):
    monkeypatch.setattr(watcher.news, "results_calendar", lambda: {"TECHM": [NOW.date()]})
    assert signals(FakeIndMoney()) == []


def test_sector_wide_move_lowers_score(capsys):
    signals(FakeIndMoney(sector_chg=0.3))
    calm = json.loads(capsys.readouterr().out.split(" ", 1)[1])["decision_score"]
    signals(FakeIndMoney(sector_chg=4.0))
    sector_wide = json.loads(capsys.readouterr().out.split(" ", 1)[1])["decision_score"]
    assert calm - sector_wide == 20  # loses the +5 "stock-specific" and takes -15 "with its sector"


def test_no_trade_day_mode(capsys, tmp_path):
    (tmp_path / "day_mode.json").write_text(json.dumps({"date": "2026-10-16", "mode": "no_trade"}))
    assert signals(FakeIndMoney()) == []


def test_watcher_signals_then_exits(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(watcher, "TRADES", tmp_path / "paper_trades.csv")
    trades = []
    asyncio.run(watcher.scan(FakeIndMoney(), trades, datetime(2026, 10, 16, 11, 0, tzinfo=IST), CFG))
    out = capsys.readouterr().out
    assert out.startswith("SIGNAL ") and "TECHM-27-OCT-1800-PUT" in out
    payload = json.loads(out.split(" ", 1)[1])
    assert "No fresh news: likely an overreaction" in payload["news_and_macro"]
    assert payload["forecast"]["basis"] and payload["day_mode"] == "normal"
    assert payload["crowd"] == {"oi_type": "long build-up", "would_score": -15, "would_block": False}
    assert trades[0]["oi_type"] == "long build-up"  # observe mode: logged, not scored
    assert trades[0]["entry_ask"] == 50.1 and trades[0]["status"] == "OPEN"

    # Same contract is not signalled twice in a day.
    asyncio.run(watcher.scan(FakeIndMoney(), trades, datetime(2026, 10, 16, 11, 5, tzinfo=IST), CFG))
    assert capsys.readouterr().out == "" and len(trades) == 1

    # Bid rises above target -> EXIT with a profit after charges.
    target = trades[0]["target_bid"]
    asyncio.run(watcher.manage_open_trades(FakeIndMoney(put_bid=target + 0.1), trades,
                                           datetime(2026, 10, 16, 11, 30, tzinfo=IST), CFG))
    assert capsys.readouterr().out.startswith("EXIT ")
    assert trades[0]["status"] == "TARGET" and trades[0]["net_pnl"] > 0
    watcher.save_trades(trades)
    assert watcher.load_trades()[0]["status"] == "TARGET"
