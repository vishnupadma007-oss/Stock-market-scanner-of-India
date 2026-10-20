from datetime import date

import numpy as np
import pandas as pd

from agents import daymode, macro, news
from agents.config import load_config
from agents.decision import decide
from agents.forecast import reversal_target
from agents.risk import plan
from tests.test_agents import SPIKE_THEN_FADE, intraday

CFG = load_config()
DAY = date(2026, 10, 16)


def test_macro_sector_and_crude():
    with_sector = macro.assess("TCS", "loser", -3.0, -2.5, None, None, CFG)
    assert with_sector["points"] == -15 and "sector" in with_sector["notes"][0]
    own_move = macro.assess("TCS", "loser", -3.0, -0.2, None, None, CFG)
    assert own_move["points"] == 5
    # BPCL fell while crude spiked: crude says keep falling, so a CE bounce trade is penalised.
    assert macro.assess("BPCL", "loser", -3.0, -0.2, 3.0, None, CFG)["points"] == 5 - 20
    # Rupee weakening helps IT: a PE on a rising IT stock fights that.
    assert macro.assess("INFY", "gainer", 3.0, 0.2, None, 0.6, CFG)["points"] == 5 - 10


def test_news_results_and_headlines():
    flat = intraday(np.full(40, 100.0))
    r = news.assess("SBIN", "loser", -3.0, DAY, [], {"SBIN": [date(2026, 10, 15)]}, flat, CFG)
    assert r["block"]  # results yesterday evening
    r = news.assess("SBIN", "loser", -3.0, DAY, [], {"SBIN": [date(2026, 10, 19)]}, flat, CFG)
    assert not r["block"] and r["points"] == -10 + 5  # results Monday (next session) + no news
    bad = [{"title": "SBIN hit by RBI penalty - 16 Oct, 2026", "sentiment": "negative"}]
    r = news.assess("SBIN", "loser", -3.0, DAY, bad, {}, flat, CFG)
    assert r["news_driven"] and r["points"] == -25
    old = [{"title": "SBIN old story - 01 Oct, 2026", "sentiment": "negative"}]
    assert news.assess("SBIN", "loser", -3.0, DAY, old, {}, flat, CFG)["points"] == 5
    assert news.headline_date("x - 18 Oct, 2026") == date(2026, 10, 18)


def test_volume_spike_is_sudden_pressure():
    df = intraday(np.r_[np.full(37, 100.0), [99.0, 98.0, 97.0]])
    df.iloc[-3:, df.columns.get_loc("Volume")] = 10_000
    r = news.assess("SBIN", "loser", -3.0, DAY, [], {}, df, CFG)
    assert any("Sudden pressure" in n for n in r["notes"])


def test_forecast_levels():
    df = intraday(np.r_[np.linspace(100, 110, 20), np.linspace(110, 108, 20)])
    f = reversal_target(df, 100.0, "gainer")
    assert f["basis"] in ("VWAP", "38% retracement") and f["level"] < 108
    faded = reversal_target(intraday(np.r_[np.linspace(100, 110, 20), np.linspace(110, 101, 20)]), 100.0, "gainer")
    assert faded["level"] is None  # already below VWAP and the retracement


def test_forecast_target_mode_aims_higher():
    option = {"est_premium": 20.0, "lot_size": 750, "delta": -0.55}
    fc = {"level": 100.0, "move": 4.0, "basis": "VWAP"}
    fixed = plan(option, 0, pd.Timestamp("2026-10-16 11:00", tz="Asia/Kolkata").to_pydatetime(), CFG, forecast=fc)
    aimed = plan(option, 0, pd.Timestamp("2026-10-16 11:00", tz="Asia/Kolkata").to_pydatetime(),
                 {**CFG, "target_mode": "forecast"}, forecast=fc)
    assert aimed["target_premium"] > fixed["target_premium"] and fixed["forecast_premium"] > 20


def test_decision_uses_extras():
    mkt = {"gainers_ok": True, "losers_ok": True, "threshold_adj": 0}
    risk = {"allowed": True, "blocks": []}
    assert decide("loser", mkt, {"score": 70}, risk, None, CFG, [{"points": -25, "notes": ["news"]}])["verdict"] == "WATCH"
    assert decide("loser", mkt, {"score": 90}, risk, None, CFG, [{"points": 0, "notes": ["results"], "block": True}])["verdict"] == "SKIP"


def test_day_mode(tmp_path):
    p = tmp_path / "d.json"
    assert daymode.load(DAY, p)["mode"] == "normal"
    p.write_text('{"date": "2026-10-16", "mode": "careful", "avoid": ["BPCL"]}')
    day = daymode.load(DAY, p)
    applied = daymode.apply(CFG, day)
    assert day["avoid"] == ["BPCL"] and applied["min_chart_score"] == CFG["min_chart_score"] + 10
    assert applied["max_trades_per_day"] == CFG["max_trades_per_day"]
    assert daymode.load(date(2026, 10, 17), p)["mode"] == "normal"  # stale file ignored


def test_psychology_oi_types_and_modes():
    from agents import psychology
    assert psychology.oi_type(3, 5, 2) == "long build-up"
    assert psychology.oi_type(3, -5, 2) == "short covering"
    assert psychology.oi_type(-3, 5, 2) == "short build-up"
    assert psychology.oi_type(-3, -5, 2) == "long unwinding"
    assert psychology.oi_type(-3, 1, 2) == "no clear OI change"
    score = {**CFG, "psychology": {"mode": "score"}}
    # Loser bouncing after holders gave up: good. Loser with fresh shorts piling in: bad.
    assert psychology.assess("loser", 100, -3, -5, None, None, None, None, score)["points"] == 10
    assert psychology.assess("loser", 100, -3, 5, None, None, None, None, score)["points"] == -15
    at_low = psychology.assess("loser", 100, -3, None, 150, 99.5, None, None, score)
    assert at_low["points"] == -10 and "52-week low" in at_low["notes"][0]
    assert psychology.assess("gainer", 100, 9, None, None, None, 101, None, score)["block"]
    observed = psychology.assess("loser", 100, -3, 5, None, None, None, None, CFG)  # default: observe
    assert observed["points"] == 0 and observed["would_score"] == -15 and observed["notes"][0].startswith("(observe)")



def test_holidays_and_expiry():
    from agents import holidays
    from agents.options import monthly_expiry
    assert holidays.holiday_name(date(2026, 10, 20)) == "Dussehra"
    assert holidays.holiday_name(date(2026, 10, 24)) == "Weekend"
    assert holidays.is_trading_day(date(2026, 10, 21))
    # Results "yesterday" skips the holiday: on Wed 21 Oct the previous session is Mon 19 Oct.
    assert news.previous_session(date(2026, 10, 21)) == date(2026, 10, 19)
    # Last Tuesday of Nov 2026 (24th) is a holiday, so stock options expire on Mon 23 Nov.
    assert monthly_expiry(date(2026, 11, 2), 3) == date(2026, 11, 23)
