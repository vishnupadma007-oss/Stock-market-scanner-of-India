from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from agents import probability as pa
from agents.config import load_config

IST = ZoneInfo("Asia/Kolkata")


def _option(strike=100.0, kind="CE"):
    return {"type": kind, "strike": strike, "expiry": date(2026, 11, 24), "iv_used": 0.3}


def test_ncdf_matches_math_erf():
    import math
    for x in (-3, -1, 0, 0.5, 2.5):
        assert abs(float(pa._ncdf(np.array([x]))[0]) - 0.5 * (1 + math.erf(x / math.sqrt(2)))) < 1e-6


def test_monte_carlo_easy_target_hits_more_often_than_hard_one():
    cfg = load_config()
    now = datetime(2026, 11, 2, 10, 0, tzinfo=IST)
    rets = np.random.default_rng(0).normal(0, 0.003, 2000)
    entry = float(pa.bs_price(100.0, 100.0, 22 / 365, 0.065, 0.3, True))
    easy = pa.monte_carlo(_option(), 100.0, entry, entry * 1.03, 100, now, now.replace(hour=15, minute=20), rets, cfg, n=500, seed=1)
    hard = pa.monte_carlo(_option(), 100.0, entry, entry * 1.5, 100, now, now.replace(hour=15, minute=20), rets, cfg, n=500, seed=1)
    assert 0 <= hard["prob"] < easy["prob"] <= 1
    assert easy["worst5_pct"] <= easy["median_pct"]


def test_monte_carlo_needs_enough_data_and_time():
    cfg = load_config()
    now = datetime(2026, 11, 2, 15, 18, tzinfo=IST)
    assert pa.monte_carlo(_option(), 100, 5, 6, 100, now, now.replace(minute=20), np.zeros(100), cfg) is None
    assert pa.monte_carlo(_option(), 100, 5, 6, 100, now.replace(hour=10), now.replace(minute=20), np.zeros(5), cfg) is None


def _trades(n=120, seed=0):
    rng = np.random.default_rng(seed)
    rows = []
    for _ in range(n):
        vx = rng.uniform(1.5, 4)
        rows.append({"opened": f"{rng.integers(9, 15):02d}:{rng.integers(0, 60):02d}", "volume_x": vx,
                     "move_pct": rng.uniform(0.2, 0.5), "side": "loser" if rng.random() < .5 else "gainer",
                     "sigma_ratio": rng.uniform(.5, 2), "hit": rng.random() < (0.4 + 0.15 * (vx - 1.5))})
    df = pd.DataFrame(rows)
    return df.assign(**pd.DataFrame([pa.features(r) for r in rows]))


def test_learned_score_picks_up_a_real_pattern():
    model = pa.fit(_trades(400))
    weak = pa.ml_score(model, pa.features({"opened": "10:00", "volume_x": 1.6, "move_pct": .3, "side": "loser"}))
    strong = pa.ml_score(model, pa.features({"opened": "10:00", "volume_x": 3.9, "move_pct": .3, "side": "loser"}))
    assert strong > weak


def test_base_rate_shrinks_to_overall_when_few_trades_match():
    model = {"overall": 0.6, "buckets": {}, "mu": [0] * 5, "sd": [1] * 5, "w": [0] * 6}
    assert pa.base_rate(model, pa.features({"opened": "10:00"})) == 0.6


def test_assess_approves_above_cut_and_rejects_below():
    tr = _trades(200)
    model = pa.set_cut(pa.fit(tr), tr.to_dict("records"))
    reps = [pa.assess(r, None, model) for r in tr.to_dict("records")]
    share = np.mean([not r["approved"] for r in reps])
    assert 0.2 < share < 0.45  # about the weakest third
    assert all(r["rejection_reason"] for r in reps if not r["approved"])


def test_assess_without_any_data_approves():
    assert pa.assess({"opened": "10:00"}, None, None)["approved"]


def test_sigma_ratio_is_one_on_an_ordinary_day():
    idx = pd.date_range("2026-10-01 09:15", periods=75 * 25, freq="5min", tz=IST)
    idx = idx[(idx.time >= datetime(2000, 1, 1, 9, 15).time()) & (idx.time <= datetime(2000, 1, 1, 15, 25).time())]
    px = 100 * np.exp(np.cumsum(np.random.default_rng(3).normal(0, 0.002, len(idx))))
    intra = pd.DataFrame({"Close": px}, index=idx)
    now = idx[-1].to_pydatetime()
    assert 0.6 < pa.sigma_ratio(intra, now) < 1.6
