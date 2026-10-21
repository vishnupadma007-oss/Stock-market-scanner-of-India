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
CFG = {**load_config(), "capital": 200000, "strike_choice": "ITM1",  # one TECHM lot (~₹30k) must fit the per-trade budget
       "teams": {"movers": {"news_votes": True}}}  # these tests cover the news votes too


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

    async def commodity_keys(self, names):
        return {"crude oil": "CRUDE", "copper": "COPPER"}

    async def day_changes(self, keys):
        return {k: (0.4 if k in ("CRUDE", "COPPER") else self.sector_chg) for k in keys}

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

    async def quotes(self, keys, segments=None):
        return {k: {"entity_stats": {"bid_price": self.put_bid, "ask_price": self.put_bid + 0.5}} for k in keys}


@pytest.fixture(autouse=True)
def offline(monkeypatch, tmp_path):
    """No network in tests: empty results calendar, no rupee quote, no day-mode file."""
    monkeypatch.setattr(watcher.news, "results_calendar", lambda: {"TECHM": RESULTS})
    monkeypatch.setattr(watcher, "usdinr_change", lambda: None)
    monkeypatch.setattr(watcher.daymode, "PATH", tmp_path / "day_mode.json")
    monkeypatch.setattr(watcher.daymode.load, "__defaults__", (tmp_path / "day_mode.json",))
    monkeypatch.setattr(watcher.intel, "DIR", tmp_path / "intel")
    watcher._daily.clear()
    watcher._daily_candles.clear()


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
    watcher._daily.pop("changes_at")  # sector moves are cached for 10 minutes; force a refresh
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


def test_account_reinvests_profit_and_reserves_open_trades():
    rows = [{"status": "TARGET", "net_pnl": "120", "entry_ask": "10", "qty": "500"},
            {"status": "SQUARED_OFF", "net_pnl": "-20", "entry_ask": "8", "qty": "500"},
            {"status": "OPEN", "net_pnl": "", "entry_ask": "12", "qty": "500"}]
    value, free = watcher.account(rows, {"capital": 10000})
    assert value == 10100 and free == 10100 - 6000


def test_incomplete_chain_rows_are_skipped():
    broken = chain()
    del broken["option_chain_data"][1]["put_data"]["slug"]
    assert pick_option(broken, "gainer", "ITM1") is None
    assert pick_option({"entity_details": {"live_price": 1790}, "option_chain_data": chain()["option_chain_data"]},
                       "gainer", "ATM") is None  # no expiry in the reply


def test_one_bad_stock_does_not_stop_the_scan(capsys):
    class Broken(FakeIndMoney):
        async def option_chain(self, key, strikes_around_atm=4):
            raise KeyError("selected_expiry")
    assert signals(Broken()) == []
    assert "ERROR" in capsys.readouterr().out


def test_busy_desk_holds_new_setups(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(watcher, "HELD", tmp_path / "held.csv")
    trades = [{"date": "2026-10-16", "contract": "OTHER", "status": "OPEN"}]
    asyncio.run(watcher.scan(FakeIndMoney(), trades, NOW, CFG, hold=True))
    assert capsys.readouterr().out == ""  # no SIGNAL, so Claude is not woken
    assert len(trades) == 1  # nothing new opened
    held = (tmp_path / "held.csv").read_text()
    assert "TECHM-27-OCT-1800-PUT" in held
    asyncio.run(watcher.scan(FakeIndMoney(), trades, NOW, CFG, hold=True))
    assert (tmp_path / "held.csv").read_text() == held  # recorded once per day


def test_leaf_errors_unwraps_groups():
    from agents.indmoney import RateLimited
    group = ExceptionGroup("outer", [ExceptionGroup("inner", [RateLimited("limit", 120)]), KeyError("stocks")])
    leaves = watcher.leaf_errors(group)
    assert isinstance(leaves[0], RateLimited) and leaves[0].retry_after == 120 and isinstance(leaves[1], KeyError)


def test_rate_limit_reply_raises():
    from types import SimpleNamespace
    from agents.indmoney import RateLimited, _parse
    reply = SimpleNamespace(is_error=False, content=[], structured_content={"result": json.dumps(
        {"error": "rate_limit_exceeded", "message": "500 calls per hour", "retry_after_seconds": 1339})})
    with pytest.raises(RateLimited) as e:
        _parse(reply)
    assert e.value.retry_after == 1339


def test_call_budget_counts_rolling_hour(tmp_path, monkeypatch):
    import time as t
    from agents import indmoney
    monkeypatch.setattr(indmoney, "USAGE_FILE", tmp_path / "usage.json")
    indmoney.record_call("get_indian_stocks_movers")  # costs 2
    indmoney.record_call("get_indian_stocks_ohlc")
    assert indmoney.calls_last_hour() == 3
    rows = json.loads((tmp_path / "usage.json").read_text())
    rows[0][0] = t.time() - 3700  # older than an hour drops out
    (tmp_path / "usage.json").write_text(json.dumps(rows))
    assert indmoney.calls_last_hour() == 1


def test_calls_are_paced_evenly():
    import time as t
    from agents import indmoney
    indmoney.set_hourly_budget(36000)  # 0.1 s per call
    indmoney._pace["next"] = 0.0
    async def three():
        for cost in (1, 2, 1):
            await indmoney._wait_turn(cost)
    start = t.monotonic()
    asyncio.run(three())
    assert t.monotonic() - start >= 0.29  # 1 + 2 units after the first call
    indmoney.set_hourly_budget(450)


class TwoGainers(FakeIndMoney):
    async def movers(self, category, limit):
        return [{"symbol": "TECHM", "ind_key": "INDS01469", "price": 1790, "change_pct": 8.48},
                {"symbol": "WIPRO", "ind_key": "INDS00999", "price": 1790, "change_pct": 8.0}] \
            if category == "top-gainers" else []


def test_one_scan_opens_at_most_one_trade(tmp_path, monkeypatch, capsys):
    # 21 Oct: WIPRO and TCS were both opened in one scan, using twice the team's capital.
    monkeypatch.setattr(watcher, "HELD", tmp_path / "held.csv")
    trades = []
    asyncio.run(watcher.scan(TwoGainers(), trades, NOW, {**CFG, "universe": [*CFG["universe"], "WIPRO"]}))
    assert len(trades) == 1
    assert capsys.readouterr().out.count("SIGNAL") == 1


def test_details_calls_cost_one_per_instrument(tmp_path, monkeypatch):
    from agents import indmoney
    monkeypatch.setattr(indmoney, "USAGE_FILE", tmp_path / "usage.json")
    indmoney.record_call("get_indian_stocks_details", 17)
    indmoney.record_call("get_indian_stocks_movers")
    assert indmoney.calls_last_hour() == 19
