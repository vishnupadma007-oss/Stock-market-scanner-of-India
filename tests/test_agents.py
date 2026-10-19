from datetime import date, datetime

import numpy as np
import pandas as pd
import pytest

from agents.chart_reader import read_chart
from agents.config import load_config
from agents.costs import exit_for_net_target, round_trip_charges
from agents.decision import decide
from agents.options import monthly_expiry, suggest_contract
from agents.regime import assess
from agents.risk import hit_probability, plan

CFG = load_config()


def intraday(path):
    """Two sessions of 5-min candles following the given price path for the second day."""
    idx = []
    for day in ("2026-10-15", "2026-10-16"):
        idx += list(pd.date_range(f"{day} 09:15", periods=len(path), freq="5min", tz="Asia/Kolkata"))
    closes = np.r_[np.full(len(path), path[0]), path]
    opens = np.r_[closes[0], closes[:-1]]
    return pd.DataFrame({"Open": opens, "High": np.maximum(opens, closes) * 1.001,
                         "Low": np.minimum(opens, closes) * 0.999, "Close": closes,
                         "Volume": np.full(len(closes), 1000.0)}, index=pd.DatetimeIndex(idx))


PROFILE = {"dist_sma20_atr": 0, "chg_1w": 0}
SPIKE_THEN_FADE = np.r_[np.linspace(100, 110, 20), np.linspace(110, 105, 20)]
STILL_RISING = np.linspace(100, 110, 40)


def test_chart_reader_sees_fading_gainer():
    assert read_chart(intraday(SPIKE_THEN_FADE), PROFILE, "gainer")["score"] >= 60
    assert read_chart(intraday(STILL_RISING), PROFILE, "gainer")["score"] < 40


def test_chart_reader_mirrors_for_losers():
    crash_then_bounce = 210 - SPIKE_THEN_FADE
    assert read_chart(intraday(crash_then_bounce), PROFILE, "loser")["score"] >= 60
    assert read_chart(intraday(210 - STILL_RISING), PROFILE, "loser")["score"] < 40


def test_net_target_clears_charges():
    rates = CFG["charges"]
    t = exit_for_net_target(20.0, 500, 1.0, rates)
    assert t["net_profit"] >= 0.01 * 20 * 500 - 1
    assert t["gross_move_pct"] > 1.0  # charges mean a gross move above 1% is needed
    c = round_trip_charges(20.0, t["exit_premium"], 500, rates)
    assert c["brokerage"] == 40


def test_expiry_is_last_tuesday_and_rolls():
    assert monthly_expiry(date(2026, 10, 1), 3) == date(2026, 10, 27)
    assert monthly_expiry(date(2026, 10, 26), 3) == date(2026, 11, 24)


def test_contract_side():
    put = suggest_contract("SBIN", 812, "gainer", 0.25, 750, CFG, date(2026, 10, 16))
    call = suggest_contract("SBIN", 812, "loser", 0.25, 750, CFG, date(2026, 10, 16))
    assert put["type"] == "PE" and put["strike"] == 820  # one strike ITM for puts
    assert call["type"] == "CE" and call["strike"] == 800
    assert put["est_premium"] > 0 and -1 < put["delta"] < 0


def test_regime_uptrend_blocks_shorting_gainers():
    close = pd.Series(np.linspace(22000, 26000, 60))
    mkt = assess(pd.DataFrame({"Close": close}), pd.DataFrame({"Close": [14.0]}), CFG)
    assert mkt["trend"] == "up" and not mkt["gainers_ok"] and mkt["losers_ok"]
    high_vix = assess(pd.DataFrame({"Close": close}), pd.DataFrame({"Close": [30.0]}), CFG)
    assert high_vix["no_trade"]


@pytest.mark.parametrize("hour,allowed", [(9, False), (11, True), (14, False)])
def test_risk_entry_window(hour, allowed):
    option = {"est_premium": 20.0, "lot_size": 750, "delta": -0.55}
    r = plan(option, 0, datetime(2026, 10, 16, hour, 40), {**CFG, "capital": 100000})
    assert r["allowed"] is allowed
    assert r["target_premium"] > 20.0 and "emergency_exit" not in r


def test_hit_probability_forecast():
    # A move of one typical hour's swing, with an hour left, is hit about 32% of the time.
    assert hit_probability(1.0, 1 / 60 ** 0.5, 60) == pytest.approx(0.317, abs=0.01)
    assert hit_probability(0.5, 0.2, 120) > hit_probability(2.0, 0.2, 120)
    assert hit_probability(1.0, 0.2, 0) == 0.0


def test_low_forecast_blocks_trade():
    option = {"est_premium": 20.0, "lot_size": 750, "delta": -0.55}
    big = {**CFG, "capital": 100000}  # one 750-lot at ₹20 = ₹15,000
    calm = plan(option, 0, datetime(2026, 10, 16, 14, 20), big, sigma_per_min=0.01)
    assert not calm["allowed"] and calm["hit_probability"] < 60
    lively = plan(option, 0, datetime(2026, 10, 16, 11, 0), big, sigma_per_min=0.5)
    assert lively["allowed"] and lively["hit_probability"] >= 60


def test_decision_respects_regime_and_ai_veto():
    risk = {"allowed": True, "blocks": []}
    mkt = {"gainers_ok": True, "losers_ok": False, "threshold_adj": 0}
    chart = {"score": 80}
    assert decide("gainer", mkt, chart, risk, None, CFG)["verdict"] == "TRADE"
    assert decide("loser", mkt, chart, risk, None, CFG)["verdict"] == "SKIP"
    veto = {"verdict": "SKIP", "confidence": 90, "reason": "results-driven move"}
    assert decide("gainer", mkt, chart, risk, veto, CFG)["verdict"] == "SKIP"


def test_sides_setting_switches_off_gainers():
    close = pd.Series(np.full(60, 25000.0))
    mkt = assess(pd.DataFrame({"Close": close}), None, {**CFG, "sides": ["loser"]})
    assert not mkt["gainers_ok"] and mkt["losers_ok"]


def test_lot_too_big_for_10k_is_blocked():
    option = {"est_premium": 20.0, "lot_size": 750, "delta": -0.55}
    r = plan(option, 0, datetime(2026, 10, 16, 11, 0), CFG)  # ₹10,000 capital
    assert not r["allowed"] and "One lot costs ₹15,000" in r["blocks"][0]
