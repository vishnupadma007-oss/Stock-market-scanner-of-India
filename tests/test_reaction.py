from datetime import datetime

import numpy as np
import pandas as pd

from agents import reaction


def daily(closes, opens=None, start="2026-09-01"):
    idx = pd.bdate_range(start, periods=len(closes))
    closes = np.asarray(closes, float)
    opens = closes if opens is None else np.asarray(opens, float)
    return pd.DataFrame({"Open": opens, "High": np.maximum(opens, closes) * 1.01,
                         "Low": np.minimum(opens, closes) * 0.99, "Close": closes}, index=idx)


def test_reaction_day_and_measure():
    days = pd.bdate_range("2026-10-12", periods=5)  # Mon 12 .. Fri 16
    assert reaction.reaction_day(datetime(2026, 10, 14, 17, 0), days) == (days[3], "after close")
    assert reaction.reaction_day(datetime(2026, 10, 14, 13, 0), days) == (days[2], "during market")
    assert reaction.reaction_day(datetime(2026, 10, 14, 8, 0), days) == (days[2], "before open")
    closes = [100.0] * 25 + [110.0]
    opens = [100.0] * 25 + [105.0]
    stock, nifty = daily(closes, opens), daily([20000.0] * 26)
    filed = datetime.combine(stock.index[24].date(), datetime.min.time()).replace(hour=17)
    r = reaction.measure(stock, nifty, filed)
    assert r["gap_pct"] == 5.0 and r["close_pct"] == 10.0 and r["excess_close_pct"] == 10.0


def test_surprise_is_against_own_trend():
    qs = [{"figures": {"profit": {"yoy_pct": g}, "revenue": {"yoy_pct": 10}}} for g in (30, 32, 28, 30, 15)]
    q = reaction.add_surprises(qs)[-1]
    assert q["profit_surprise"] == -15.0  # usually +30%, now +15%: a disappointment


def test_fit_and_predict_learn_the_direction():
    rng = np.random.default_rng(1)
    n = 200
    df = pd.DataFrame({"symbol": rng.choice(["A", "B"], n), "profit_surprise": rng.normal(0, 20, n),
                       "revenue_surprise": rng.normal(0, 5, n), "runup_20d": rng.normal(0, 5, n),
                       "when": "after close"})
    df["excess_close_pct"] = 0.1 * df["profit_surprise"] - 0.2 * df["runup_20d"] + rng.normal(0, 2, n)
    df["excess_gap_pct"] = 0.6 * df["excess_close_pct"]
    df["close_pct"], df["gap_pct"] = df["excess_close_pct"], df["excess_gap_pct"]
    model = reaction.fit(df)
    assert abs(model["targets"]["excess_close_pct"]["coef"]["profit_surprise"] - 0.1) < 0.03
    beat = reaction.predict("A", {"profit_surprise": 20, "revenue_surprise": 0, "runup_20d": 0}, model)
    miss = reaction.predict("A", {"profit_surprise": -20, "revenue_surprise": 0, "runup_20d": 0}, model)
    assert beat["expected_close_pct"] > 1 > -1 > miss["expected_close_pct"]
    assert beat["chance_up_pct"] > 70 and miss["chance_up_pct"] < 30
    lo, hi = beat["close_range_pct"]
    assert lo < beat["expected_close_pct"] < hi
