import asyncio
from datetime import date, datetime
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

import watcher
from agents import spurt
from agents.config import load_config

IST = ZoneInfo("Asia/Kolkata")


def days_of_candles(today_volume_x=3.0, today_move=0.3, n_days=12):
    """`n_days` sessions of 5-minute candles at Rs 1,000; on the last day volume runs at
    `today_volume_x` times normal and the price drifts `today_move` % up by 10:00."""
    frames = []
    for i, day in enumerate(pd.bdate_range(end="2026-10-28", periods=n_days)):
        idx = pd.date_range(f"{day.date()} 09:15", f"{day.date()} 15:25", freq="5min", tz=IST)
        last = i == n_days - 1
        close = np.full(len(idx), 1000.0)
        if last:
            close = 1000.0 * (1 + np.minimum(np.arange(len(idx)), 9) * today_move / 900)
        vol = np.full(len(idx), 1000.0 * (today_volume_x if last else 1.0))
        frames.append(pd.DataFrame({"Open": np.r_[close[0], close[:-1]], "High": close + 0.5,
                                    "Low": np.r_[close[0], close[:-1]] - 0.5, "Close": close, "Volume": vol}, index=idx))
    return pd.concat(frames)


def test_quiet_spurt_fires_on_heavy_volume_and_a_small_move():
    sig = spurt.first_signal(spurt.prepare(days_of_candles()), date(2026, 10, 28))
    assert sig and sig["direction"] == "up" and sig["volume_x"] >= 1.5 and 0.2 <= sig["move_pct"] <= 0.5


def test_quiet_spurt_needs_the_volume_and_a_small_move():
    day = date(2026, 10, 28)
    assert spurt.first_signal(spurt.prepare(days_of_candles(today_volume_x=1.0)), day) is None  # usual volume
    assert spurt.first_signal(spurt.prepare(days_of_candles(today_move=0.05)), day) is None    # no move yet
    assert spurt.first_signal(spurt.prepare(days_of_candles(today_move=3.0)), day) is None     # already ran


class Live:
    def __init__(self, move=0.35):
        self.move = move

    async def quotes(self, keys, segments=None):
        return {k: {"entity_stats": {"day_change_percentage": self.move, "live_price": 1003.5}} for k in keys}

    async def candles(self, key, interval, lookback):
        d = days_of_candles(n_days=6)
        walk = 1000.0 * np.exp(np.cumsum(np.random.default_rng(7).normal(0, 0.003, len(d))))
        return d.assign(Close=walk, Open=np.r_[walk[0], walk[:-1]], High=walk * 1.002, Low=walk * 0.998)

    async def pick_contract(self, key, side, cfg, today, budget=None):
        return {"contract": "TCS-23-NOV-1000-CALL", "derivative_id": "D1", "ask": 20.0, "bid": 19.8,
                "est_premium": 20.0, "lot_size": 100, "delta": 0.55, "gamma": 0.004, "theta_day": -0.4,
                "spread_pct": 1.0, "expiry": date(2026, 11, 23), "spot": 1003.5}


def setup(now, move_pct=0.35):
    watcher._daily.clear()
    watcher.reset_daily(now.date().isoformat())
    watcher._stock_keys["TCS"] = "K"
    watcher._daily["spurt_signals"] = {"TCS": {
        "time": pd.Timestamp(now.replace(minute=now.minute - 5)), "direction": "up", "volume_x": 2.1,
        "move_pct": move_pct, "price": 1003.5}}


def test_fresh_spurt_is_confirmed_live_and_bought_with_a_10pct_target(capsys):
    now = datetime(2026, 10, 29, 10, 30, tzinfo=IST)
    setup(now)
    cfg = {**load_config(), "capital": 30000}
    trades = []
    c = {**watcher.NEWS_DEFAULTS, **watcher.team_cfg(cfg, "news")}
    assert asyncio.run(watcher.spurt_entries(Live(), trades, now, cfg, c, set()))
    t = trades[0]
    assert t["strategy"] == "quiet-spurt" and watcher.team_of(t) == "spurt" and t["side"] == "loser"
    assert float(t["target_bid"]) >= 20.0 * 1.10  # a 10% net target, not 1%
    assert "SIGNAL" in capsys.readouterr().out
    # Handled once: the next round does not buy it again.
    assert not asyncio.run(watcher.spurt_entries(Live(), trades, now, cfg, c, set()))


def test_spurt_that_ran_off_or_reversed_is_skipped():
    now = datetime(2026, 10, 29, 10, 30, tzinfo=IST)
    cfg = {**load_config(), "capital": 30000}
    c = {**watcher.NEWS_DEFAULTS, **watcher.team_cfg(cfg, "news")}
    for live_move in (1.6, -0.3):
        setup(now)
        trades = []
        assert not asyncio.run(watcher.spurt_entries(Live(live_move), trades, now, cfg, c, set()))
        assert trades == []


def test_old_spurt_is_not_traded():
    now = datetime(2026, 10, 29, 11, 30, tzinfo=IST)
    setup(now)
    watcher._daily["spurt_signals"]["TCS"]["time"] = pd.Timestamp(datetime(2026, 10, 29, 10, 0, tzinfo=IST))
    cfg = {**load_config(), "capital": 30000}
    c = {**watcher.NEWS_DEFAULTS, **watcher.team_cfg(cfg, "news")}
    assert not asyncio.run(watcher.spurt_entries(Live(), [], now, cfg, c, set()))


def test_nse_live_page_and_live_signal():
    payload = {"total": {"data": [
        {"symbol": "TCS", "series": "EQ", "pchange": 0.31, "previousClose": 1000.0, "lastPrice": 1003.1,
         "totalTradedVolume": 12.0, "totalTradedValue": 120.12},   # 12 lakh shares, Rs 120.12 crore
        {"symbol": "XYZ", "series": "EQ", "pchange": 2.0, "previousClose": 10, "lastPrice": 10.2,
         "totalTradedVolume": 1.0, "totalTradedValue": 0.1}]}}
    rows = spurt.parse_nse(payload, {"TCS"})
    r = rows["TCS"]
    assert set(rows) == {"TCS"} and r["volume"] == 1.2e6 and r["vwap"] == 1001.0
    curve = spurt.usual_curve(days_of_candles(), date(2026, 10, 28))
    usual = spurt.usual_now(curve, 60)  # 10:15: 12 candles of 1,000 shares
    assert 11000 <= usual <= 13000
    sig = spurt.live_signal(r, 1002.0, usual / 100, 60)  # far above the usual volume
    assert sig["direction"] == "up" and sig["volume_x"] >= 1.5
    assert spurt.live_signal(r, 1004.0, usual / 100, 60) is None   # last 5 minutes went down
    assert spurt.live_signal(r, 1002.0, r["volume"], 60) is None   # usual volume


def test_spurt_with_agreeing_news_aims_for_15pct_under_its_own_label(monkeypatch):
    now = datetime(2026, 10, 29, 10, 30, tzinfo=IST)
    setup(now)
    monkeypatch.setattr(watcher.analyzer, "stock_view", lambda *a, **k: {
        "strong": True, "direction": "up", "confidence": 80, "reasons": ["Order win"]})
    cfg = {**load_config(), "capital": 30000}
    c = {**watcher.NEWS_DEFAULTS, **watcher.team_cfg(cfg, "news")}
    trades = []
    assert asyncio.run(watcher.spurt_entries(Live(), trades, now, cfg, c, set()))
    t = trades[0]
    assert t["strategy"] == "quiet-spurt-news" and watcher.team_of(t) == "news"
    assert float(t["target_bid"]) >= 20.0 * 1.15 and "target 15% net" in t["notes"]


def test_parse_nse_reads_numbers_with_units():
    from agents.spurt import parse_nse
    row = {"symbol": "PNB", "series": "EQ", "lastPrice": "1,101.5", "previousClose": 1100, "pchange": "0.14",
           "totalTradedVolume": "472.67 L", "totalTradedValue": "52.1 Cr"}
    out = parse_nse({"total": {"data": [row]}}, {"PNB"})["PNB"]
    assert out["volume"] == 472.67e5 and out["price"] == 1101.5
    assert abs(out["vwap"] - 52.1 * 100 / 472.67) < 0.01
    plain = parse_nse({"total": {"data": [{**row, "totalTradedVolume": 472.67, "totalTradedValue": 52.1}]}}, {"PNB"})
    assert plain["PNB"]["volume"] == out["volume"]


class Gapped(Live):
    """TCS opened 2.5% down at 975.6 (prev close 1000), fell to 970, now 985: a 1.5% recovery past the open."""
    def __init__(self, live=985.0):
        self.live = live

    async def quotes(self, keys, segments=None):
        return {k: {"entity_stats": {"day_open": 975.6, "day_low": 970.0, "day_high": 986.0, "live_price": self.live,
                                     "prev_close": 1000.0, "day_change_percentage": -1.5}} for k in keys}


def gap_setup(monkeypatch, now):
    watcher._daily.clear()
    watcher.reset_daily(now.date().isoformat())
    watcher._stock_keys["TCS"] = "K"
    monkeypatch.setattr(watcher.preopen, "load", lambda kind, day: {"TCS": {"gap_pct": -2.4}} if kind == "preopen" else None)
    monkeypatch.setattr(watcher.news, "results_calendar", lambda: {})
    monkeypatch.setattr(watcher.analyzer, "recent_items", lambda now: [])
    monkeypatch.setattr(watcher.daymode, "load", lambda day: {"mode": "normal", "avoid": []})


def test_gap_recovery_buys_the_bounce_on_the_preopen_team(monkeypatch, capsys):
    now = datetime(2026, 11, 4, 9, 31, tzinfo=IST)
    gap_setup(monkeypatch, now)
    cfg = {**load_config(), "capital": 30000}
    trades = []
    assert asyncio.run(watcher.gap_recovery_entries(Gapped(), trades, now, cfg))
    t = trades[0]
    assert t["strategy"] == "gap-recovery" and watcher.team_of(t) == "preopen" and t["side"] == "loser"  # a CALL


def test_gap_recovery_skips_a_gap_that_holds(monkeypatch, capsys):
    now = datetime(2026, 11, 4, 9, 31, tzinfo=IST)
    gap_setup(monkeypatch, now)
    trades = []
    assert not asyncio.run(watcher.gap_recovery_entries(Gapped(live=972.0), trades, now, {**load_config(), "capital": 30000}))
    assert not asyncio.run(watcher.gap_recovery_entries(Gapped(), trades, now.replace(hour=10, minute=30),
                                                        {**load_config(), "capital": 30000}))  # outside the window
    assert trades == []


def test_pure_spurt_news_quarantine():
    now = datetime(2026, 11, 4, 10, 0, tzinfo=IST)
    res, reason = spurt.check_news_quarantine('BRITANNIA', now, {}, [], [], {'BRITANNIA': ['2026-11-04']})
    assert res is True and 'Results due today' in reason

    res, reason = spurt.check_news_quarantine('TCS', now, {}, [], [], {'BRITANNIA': ['2026-11-04']})
    assert res is False and 'Zero news' in reason


def test_pure_spurt_preopen_and_fo_activity():
    # Pre-open calm check
    ok, _ = spurt.check_preopen_profile('VOLTAS', {'VOLTAS': {'gap_pct': 2.5}}, max_gap_pct=1.0)
    assert not ok
    ok, _ = spurt.check_preopen_profile('TITAN', {'TITAN': {'gap_pct': 0.3}}, max_gap_pct=1.0)
    assert ok

    # F&O Activity check
    act = {'TCS': {'kind': 'long build-up', 'oi_pct': 4.5}}
    ok, _ = spurt.check_fo_activity('TCS', 'up', act)
    assert ok
    ok, _ = spurt.check_fo_activity('TCS', 'down', act)
    assert not ok


def test_pure_spurt_multiweek_context():
    idx = pd.bdate_range(end='2026-11-04', periods=30)
    close_exhausted = [100.0] * 24 + [102.0, 105.0, 108.0, 112.0, 115.0, 115.0]
    df_exhausted = pd.DataFrame({'Close': close_exhausted, 'High': close_exhausted, 'Low': close_exhausted}, index=idx)
    ok, reason, _ = spurt.check_multiweek_context(df_exhausted, 'up', date(2026, 11, 4))
    assert not ok and 'Exhaustion risk' in reason


def test_pure_spurt_option_limits():
    pure = spurt.PURE_DEFAULTS
    assert spurt.check_option_limits({"spread_pct": 0.8, "delta": 0.6}, pure) == ""
    assert "bid-ask" in spurt.check_option_limits({"spread_pct": 1.5, "delta": 0.6}, pure)
    assert "delta" in spurt.check_option_limits({"spread_pct": 0.8, "delta": -0.3}, pure)
    assert spurt.check_option_limits({"spread_pct": 0.8}, pure) == ""


def test_news_quarantine_ignores_routine_news():
    now = datetime(2026, 11, 5, 10, 0, tzinfo=IST)
    routine = [{"symbols": ["ITC"], "kind": "news", "impact": 1, "headline": "How ITC shares are performing"},
               {"symbols": ["ITC"], "kind": "concall", "impact": 2, "headline": "ITC concall transcript"}]
    assert spurt.check_news_quarantine("ITC", now, {}, [], routine, {})[0] is False
    big = routine + [{"symbols": ["ITC"], "kind": "news", "impact": 3, "headline": "ITC probe"}]
    assert spurt.check_news_quarantine("ITC", now, {}, [], big, {})[0] is True
    filing = [{"symbols": ["ITC"], "kind": "filing", "category": "RESULTS", "impact": 3, "headline": "Results"}]
    assert spurt.check_news_quarantine("ITC", now, {}, [], filing, {})[0] is True


def test_ai_spurt_context_prompt_and_log(tmp_path, monkeypatch):
    from agents import ai_helper
    items = [{"symbols": ["ITC"], "kind": "news", "impact": 1, "time": "2026-11-05 09:00", "headline": "ITC article"},
             {"symbols": [], "scope": "global", "kind": "news", "impact": 3, "time": "2026-11-05 08:00", "headline": "Midterm verdict"}]
    info = {"symbol": "ITC", "direction": "up", "move": 0.3, "volume_x": 2.0, **ai_helper.context_info("ITC", items, "up", "normal")}
    assert "ITC article" in info["own"] and "Midterm verdict" in info["market"]
    assert "ITC" in ai_helper.CONTEXT_PROMPT.format(**info)
    monkeypatch.setattr(ai_helper, "CONTEXT_LOG", tmp_path / "ctx.csv")
    monkeypatch.setattr(ai_helper, "ask", lambda *a, **k: '{"market_wide": true, "catalyst": "none", "take_it": "NO", "confidence": 70, "reason": "x"}')
    ai_helper.log_spurt_context(info, {"team": "spurt", "contract": "ITC-23-NOV-400-CALL"})
    assert "NO" in (tmp_path / "ctx.csv").read_text()


def test_puts_are_not_carried_when_switched_off():
    from datetime import date
    from agents import carry
    now = datetime(2026, 11, 6, 15, 20, tzinfo=IST)
    put = {"date": "2026-11-06", "symbol": "LT", "contract": "LT-23-NOV-4100-PUT"}
    call = {**put, "contract": "LT-23-NOV-4100-CALL"}
    cfg = {"enabled": True, "carry_puts": False}
    assert carry.should_carry(put, now, "spurt", [], None, date(2026, 11, 9), cfg) == (False, "PUTs are not carried")
    assert carry.should_carry(call, now, "spurt", [], None, date(2026, 11, 9), cfg)[0] is True
