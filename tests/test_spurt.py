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
    assert t["strategy"] == "quiet-spurt" and watcher.team_of(t) == "news" and t["side"] == "loser"
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
