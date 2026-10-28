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
    pick_contract = watcher.IndMoney.pick_contract
    _pick_month = watcher.IndMoney._pick_month

    def __init__(self, put_bid=49.6, headlines=(), sector_chg=0.3):
        self.put_bid, self.headlines, self.sector_chg = put_bid, list(headlines), sector_chg

    async def crude_key(self):
        return "CRUDE"

    async def commodity_keys(self, names):
        return {"crude oil": "CRUDE", "copper": "COPPER"}

    async def day_changes(self, keys):
        calm = ("CRUDE", "COPPER", watcher.NIFTY_KEY, watcher.VIX_KEY)  # the market itself stays calm
        return {k: (0.4 if k in calm else self.sector_chg) for k in keys}

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


def test_movers_news_guard_skips_results_day(tmp_path, monkeypatch, capsys):
    # News votes off (the movers team's normal setting), guard on: a results filing today stops the trade.
    monkeypatch.setattr(watcher, "GUARD_LOG", tmp_path / "guard.csv")
    cfg = {**CFG, "teams": {"movers": {"news_votes": False, "news_guard": True}}}
    watcher._daily.update(date=NOW.date().isoformat(), filings={"TECHM": [
        {"category": "RESULTS", "time": "2026-10-16 10:05:00", "text": "financial results"}]})
    trades = []
    asyncio.run(watcher.scan(FakeIndMoney(), trades, NOW, cfg))
    assert trades == [] and "SIGNAL" not in capsys.readouterr().out
    assert "Results out today" in (tmp_path / "guard.csv").read_text()
    watcher._daily["filings"] = {}
    asyncio.run(watcher.scan(FakeIndMoney(), trades, NOW, cfg))
    assert len(trades) == 1  # without the news, the same chart trades


def test_expiry_week_falls_back_to_next_month():
    from datetime import date
    from agents.indmoney import needs_next_month
    fb = {"days": 7, "min_premium": 5.0, "max_spread_pct": 2.0}
    near = {**chain(), "expiry_list": ["20261027", "20261123"]}
    good = pick_option(near, "gainer", "ITM1")
    assert not needs_next_month(good, near, date(2026, 10, 22), fb)          # fine contract: keep it
    cheap = {**good, "ask": 1.85}
    assert needs_next_month(cheap, near, date(2026, 10, 22), fb)             # expiry week + too cheap
    assert not needs_next_month(cheap, near, date(2026, 10, 12), fb)         # not expiry week yet
    assert needs_next_month({**good, "spread_pct": 6.3}, near, date(2026, 10, 22), fb)  # gap too wide
    assert not needs_next_month(cheap, near, date(2026, 10, 22), {**fb, "enabled": False})

    class TwoMonths(FakeIndMoney):
        calls = []

        async def option_chain(self, key, strikes_around_atm=4, expiry=None):
            self.calls.append(expiry)
            if expiry == "20261123":
                c = chain()
                for row in c["option_chain_data"]:
                    row["put_data"]["slug"] = row["put_data"]["slug"].replace("27-oct", "23-nov")
                return {**c, "selected_expiry": "20261123", "expiry_list": ["20261027", "20261123"]}
            c = chain(put_bid=40.0, put_ask=50.1)  # this month: 20% gap
            return {**c, "expiry_list": ["20261027", "20261123"]}

    im = TwoMonths()
    opt = asyncio.run(im.pick_contract("K", "gainer", {**CFG, "expiry_fallback": fb}, date(2026, 10, 22)))
    assert opt["contract"].startswith("TECHM-23-NOV") and opt["rolled_from"].startswith("TECHM-27-OCT")
    assert im.calls == [None, "20261123"]
    # Two weeks before expiry the same wide gap is left to the usual checks: no extra call.
    im.calls.clear()
    opt = asyncio.run(im.pick_contract("K", "gainer", {**CFG, "expiry_fallback": fb}, date(2026, 10, 12)))
    assert opt["contract"].startswith("TECHM-27-OCT") and im.calls == [None]


def test_movers_scan_stops_for_a_fresh_news_idea():
    watcher.news_pending.set()
    trades = []
    asyncio.run(watcher.scan(FakeIndMoney(), trades, NOW, CFG, yield_to_news=True))
    assert trades == []  # stopped before the first stock: the news team goes first
    watcher.news_pending.clear()
    assert len(signals(FakeIndMoney())) == 1  # same market without a pending idea: trades as usual


def test_lag_seconds():
    assert watcher.lag_seconds({"time": "2026-10-23 10:00:00"}, datetime(2026, 10, 23, 10, 0, 25, tzinfo=IST)) == 25
    assert watcher.lag_seconds({}, NOW) is None


def test_day_before_expiry_always_rolls():
    from datetime import date
    from agents.indmoney import needs_next_month
    near = {**chain(), "expiry_list": ["20261027", "20261123"]}
    good = pick_option(near, "gainer", "ITM1")
    fb = {"days": 7, "min_premium": 5.0, "max_spread_pct": 2.0, "always_days": 2}
    assert needs_next_month(good, near, date(2026, 10, 26), fb)        # expiry tomorrow: roll even a fine contract
    assert not needs_next_month(good, near, date(2026, 10, 22), fb)    # 5 days left and fine: keep it


def test_implied_volatility_and_live_greeks_enrichment():
    from datetime import date
    from agents import indmoney, options
    bs = options.black_scholes(1800.0, 1800.0, 15 / 365.0, 0.065, 0.28, is_call=True)
    iv = options.implied_volatility(bs.price, 1800.0, 1800.0, 15 / 365.0, 0.065, is_call=True)
    assert abs(iv - 0.28) < 0.005

    opt = indmoney.pick_option(chain(), "gainer", "ITM1", today=date(2026, 10, 16))
    assert opt is not None
    assert opt["gamma"] > 0 and opt["theta_day"] < 0 and opt["vega"] > 0 and opt["iv_used"] > 0

    # Crossed book (ask < bid) must be rejected
    crossed = chain(put_bid=51.0, put_ask=50.1)
    assert indmoney.pick_option(crossed, "gainer", "ITM1") is None


def test_results_gap_belongs_to_news_team_everywhere():
    import review
    trade = {"date": "2026-10-26", "status": "OPEN", "strategy": "results-gap", "entry_ask": "20", "qty": "500", "net_pnl": ""}
    assert watcher.team_of(trade) == "news"
    assert watcher.has_open([trade], "news") and not watcher.has_open([trade], "movers")
    s = pd.Series(["reversal", "results", "intel", "results-gap"])
    assert list(review.team_of(s)) == ["movers", "news", "news", "news"]


def test_save_trades_preserves_concurrent_verdicts_and_external_trades(tmp_path, monkeypatch):
    trades_file = tmp_path / "paper_trades.csv"
    monkeypatch.setattr(watcher, "TRADES", trades_file)

    row1 = {f: "" for f in watcher.FIELDS}
    row1.update(date="2026-10-26", opened="10:00", symbol="TCS", contract="TCS-PUT", status="OPEN",
                qty="500", entry_ask="40", target_bid="40.6")
    watcher.save_trades([row1])

    # Simulate cycle() loading initial trades
    loaded = watcher.load_trades()
    baseline = {watcher._trade_key(r) for r in loaded}

    # Meanwhile on disk: Claude adds claude_verdict to row1 AND paper_trade.py appends row2
    row1_disk = {**row1, "claude_verdict": "TRADE", "notes": "Confirmed by Claude"}
    row2_disk = {f: "" for f in watcher.FIELDS}
    row2_disk.update(date="2026-10-26", opened="10:01", symbol="INFY", contract="INFY-CALL", status="OPEN",
                     qty="400", entry_ask="25", target_bid="25.4", strategy="results")
    watcher.save_trades([row1_disk, row2_disk])

    # Now cycle() finishes and saves its in-memory `loaded` list (where row1 has empty claude_verdict and row2 is absent)
    loaded[0]["status"] = "TARGET"
    loaded[0]["exit_bid"] = "40.7"
    watcher.save_trades(loaded, baseline_keys=baseline)

    final = watcher.load_trades()
    assert len(final) == 2
    assert final[0]["status"] == "TARGET" and final[0]["claude_verdict"] == "TRADE"
    assert final[1]["symbol"] == "INFY" and final[1]["contract"] == "INFY-CALL"


def test_square_off_fallback_when_bid_is_missing(capsys):
    class ZeroBidAtClose(FakeIndMoney):
        async def quotes(self, keys, segments=None):
            return {k: {"entity_stats": {"bid_price": 0.0, "live_price": 47.5}} for k in keys}

    trades = [{f: "" for f in watcher.FIELDS} | {
        "date": "2026-10-16", "opened": "11:00", "symbol": "TECHM", "contract": "TECHM-27-OCT-1800-PUT",
        "derivative_id": "P1800", "qty": "600", "entry_ask": "50.1", "target_bid": "50.85", "status": "OPEN"
    }]
    asyncio.run(watcher.manage_open_trades(ZeroBidAtClose(), trades, datetime(2026, 10, 16, 15, 21, tzinfo=IST), CFG))
    assert trades[0]["status"] == "SQUARED_OFF"
    assert trades[0]["exit_bid"] == 47.5


def test_movers_same_symbol_loss_cooldown():
    now = datetime(2026, 10, 16, 11, 0, tzinfo=IST)
    cfg = {**CFG, "capital": 200000, "teams": {"movers": {"news_votes": True}}}
    trades = [{f: "" for f in watcher.FIELDS} | {
        "date": "2026-10-16", "opened": "10:00", "symbol": "TECHM", "side": "gainer",
        "contract": "TECHM-27-OCT-1780-PUT", "status": "SQUARED_OFF", "net_pnl": "-1200",
        "entry_ask": "38.0", "qty": "600", "strategy": "reversal"
    }]
    asyncio.run(watcher.scan(FakeIndMoney(), trades, now, cfg))
    assert len(trades) == 1  # TECHM gainer skipped after earlier loss on same symbol+side today


def test_news_team_respects_daymode_and_vix_panic(tmp_path, monkeypatch):
    from tests.test_teams import FakeIndMoney as FakeNewsIM, NOW as TEAM_NOW, idea
    day_file = tmp_path / "day_mode.json"
    monkeypatch.setattr(watcher.daymode, "PATH", day_file)
    monkeypatch.setattr(watcher.daymode.load, "__defaults__", (day_file,))

    # 1. Avoid list blocks TECHM
    day_file.write_text(json.dumps({"date": TEAM_NOW.date().isoformat(), "mode": "normal", "avoid": ["TECHM"]}))
    idea("up")
    trades = []
    asyncio.run(watcher.news_team(FakeNewsIM(move=1.2), trades, TEAM_NOW, {**CFG, "capital": 200000}))
    assert trades == []

    # 2. VIX panic blocks news team
    day_file.write_text(json.dumps({"date": TEAM_NOW.date().isoformat(), "mode": "normal", "avoid": []}))

    class HighVixIM(FakeNewsIM):
        async def quotes(self, keys, segments=None):
            q = await super().quotes(keys, segments)
            q[watcher.VIX_KEY] = {"entity_stats": {"live_price": 28.5, "day_change_percentage": 18.0}}
            return q

    idea("up")
    trades = []
    asyncio.run(watcher.news_team(HighVixIM(move=1.2), trades, TEAM_NOW, {**CFG, "capital": 200000, "max_vix": 22}))
    assert trades == []


def test_risk_liquidity_vetoes_and_second_order_moves():
    from agents import risk
    opt = {"est_premium": 3.5, "lot_size": 1000, "delta": -0.5, "gamma": 0.015, "theta_day": -1.2}
    r = risk.plan(opt, 0, datetime(2026, 10, 16, 11, 0), {**CFG, "capital": 100000, "min_premium": 5.0, "max_spread_pct": 2.0},
                  spread_pct=2.8)
    assert not r["allowed"]
    assert any("minimum" in b for b in r["blocks"]) and any("spread" in b for b in r["blocks"])
    assert r["gamma_adjusted_move"] <= r["underlying_move"]
    assert r["theta_adjusted_move"] >= r["underlying_move"]
    assert r["reward_to_cost_ratio"] > 0


def test_chart_reader_climax_absorption_and_momentum_fade():
    from agents import chart_reader, momentum
    df = intraday(SPIKE_THEN_FADE)
    today_idx = df[df.index.date == df.index[-1].date()].index
    peak_ts = today_idx[19]
    df.loc[peak_ts, "High"] = 112.0
    df.loc[peak_ts, "Close"] = 109.5
    df.loc[peak_ts, "Volume"] = 5000.0
    res = chart_reader.read_chart(df, {"dist_sma20_atr": 0, "chg_1w": 0}, "gainer")
    assert any("Climax volume absorption" in s[0] for s in res["signals"])

    from tests.test_teams import _candles
    bad_candle = _candles(2500, green=True)
    bad_candle.iloc[-1, bad_candle.columns.get_loc("High")] = 105.0
    bad_candle.iloc[-1, bad_candle.columns.get_loc("Close")] = 100.1
    book = {"NSE": {"total_bid_qty": 30000, "total_ask_qty": 10000}}
    assert not momentum.early_signals(bad_candle, book, "up")["ok"]


def test_consolidated_results_preferred_over_standalone():
    from agents import announcements
    filing_text = """
    Statement of Standalone Financial Results for the Quarter Ended September 30, 2026
    1 Revenue from operations      10,000    9,800    9,500
    2 Net Profit after tax          1,000      950      900

    Statement of Consolidated Financial Results for the Quarter Ended September 30, 2026
    1 Revenue from operations      45,000   42,000   36,000
    2 Net Profit after tax          5,400    4,800    4,000
    """
    figs = announcements.figures_from_text(filing_text)
    assert figs["revenue"]["quarter"] == 45000 and figs["profit"]["quarter"] == 5400


def test_top_nifty_gainers_roundup_and_review_risk_summary(tmp_path):
    import review
    from agents import intel
    i = intel.make_item(id="k1", time="2026-10-26 10:00:00", source="MC", kind="news",
                        headline="Kotak Mahindra Bank stock jumps 2%, among top Nifty gainers after Q2 results")
    assert i["sentiment"] == 0.0

    df = pd.DataFrame({
        "date": ["2026-10-21", "2026-10-22"], "opened": ["10:00", "11:00"], "closed": ["10:30", "15:20"],
        "symbol": ["INFY", "PNB"], "side": ["gainer", "loser"], "contract": ["C1", "C2"],
        "entry_ask": [30.0, 5.0], "exit_bid": [30.6, 4.0], "qty": [500, 1000],
        "spread_pct": [0.8, 1.2], "hit_probability": [90, 75], "chart_score": [80, 70],
        "status": ["TARGET", "SQUARED_OFF"], "net_pnl": [600.0, -1000.0], "net_pct": [2.0, -20.0],
        "hit": [True, False], "claude_verdict": ["TRADE", "SKIP"], "strategy": ["reversal", "results-gap"],
        "oi_type": ["long build-up", ""]
    })
    txt = review.review(df, "2026-10-22", "2026-10-18")
    assert "Profit factor 0.60" in txt and "break-even hit rate" in txt and "max drawdown" in txt


def test_preopen_and_volume_spurt_ideas_generation(tmp_path, monkeypatch):
    from agents import preopen
    preopen_mock = {
        "TECHM": {"iep": 1820.0, "gap_pct": 1.68, "prev_close": 1790.0, "buy_sell_ratio": 1.85, "volume": 50000},
        "INFY": {"iep": 1180.0, "gap_pct": -1.80, "prev_close": 1201.6, "buy_sell_ratio": 0.55, "volume": 45000},
    }
    spurts_mock = {
        "WIPRO": {"symbol": "WIPRO", "volume_x": 3.8, "change_pct": 2.1},
    }
    monkeypatch.setattr(preopen, "load", lambda kind, day: preopen_mock if kind == "preopen" else spurts_mock)
    monkeypatch.setattr(watcher, "IDEAS", tmp_path / "ideas.csv")
    watcher._daily.clear()
    now = datetime(2026, 10, 27, 9, 20, tzinfo=IST)
    watcher.reset_daily(now.date().isoformat())

    c = {**watcher.NEWS_DEFAULTS, "preopen_rule": True, "spurt_rule": True}
    universe = {"TECHM", "INFY", "WIPRO"}
    watcher.preopen_early_ideas(now, c, set(), universe)
    watcher.volume_spurt_ideas(now, c, set(), universe)

    ideas = watcher._daily.get("ideas", {})
    assert "TECHM" in ideas and ideas["TECHM"]["direction"] == "up" and ideas["TECHM"]["source"] == "preopen"
    assert "INFY" in ideas and ideas["INFY"]["direction"] == "down" and ideas["INFY"]["source"] == "preopen"
    assert "WIPRO" in ideas and ideas["WIPRO"]["direction"] == "up" and ideas["WIPRO"]["source"] == "spurt"


def test_news_team_dynamic_forecast_target_replaces_one_percent():
    from tests.test_teams import FakeIndMoney as FakeNewsIM, NOW as TEAM_NOW, idea
    idea("up", confidence=85)
    # Set an expected move of 3.5%
    watcher._daily["ideas"]["TECHM"]["expected_move_pct"] = 3.5
    trades = []
    cfg_news = {**CFG, "capital": 200000, "teams": {**CFG.get("teams", {}), "news": {
        **watcher.NEWS_DEFAULTS, "capital": 200000, "target_mode": "forecast", "forecast_capture": 0.6
    }}}
    asyncio.run(watcher.news_team(FakeNewsIM(move=1.2), trades, TEAM_NOW, cfg_news))
    assert len(trades) == 1
    t = trades[0]
    # At 3.5% move on ₹1790 spot, underlying move is ~₹62.65, so option aim is well above the ₹50.85 1% target!
    assert float(t["target_bid"]) > 52.0
    assert float(t["target_bid"]) > float(t["entry_ask"]) * 1.02


def test_news_guard_counts_results_filed_after_last_close():
    from agents import news_guard
    now = datetime(2026, 10, 27, 12, 0, tzinfo=IST)
    evening = [{"category": "RESULTS", "time": "2026-10-26 16:37:19", "text": "results"}]
    assert news_guard.check("RECLTD", "loser", [], evening, now)["block"]
    midday = [{"category": "RESULTS", "time": "2026-10-26 11:00:00", "text": "results"}]
    assert not news_guard.check("RECLTD", "loser", [], midday, now)["block"]


def test_repeated_errors_show_again_with_a_count(monkeypatch, capsys):
    t = [1000.0]
    monkeypatch.setattr(watcher.clock, "time", lambda: t[0])
    watcher._errors_seen.clear(); watcher._errors_count.clear()
    for step in range(5):
        watcher.emit("ERROR", {"error": "MCPError: boom"})
        t[0] += 200
    out = capsys.readouterr().out.strip().splitlines()
    assert len(out) == 2 and '"repeats": 2' in out[1]  # shown at 0 s and 600 s; two hidden between
