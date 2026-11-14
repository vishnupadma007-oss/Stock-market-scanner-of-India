from datetime import datetime

from agents import newsspurt, overnight


def test_gap_labels():
    assert overnight.label(1.0, 1.4) == "priced in"
    assert overnight.label(1.0, 0.3) == "under-reacted"
    assert overnight.label(1.0, -0.8) == "opposite"
    assert overnight.label(1.0, 0.7) == "as expected"
    assert overnight.label(0.1, 0.2) == "as expected"


def test_predict_gap_uses_beta_and_oil():
    model = {"nifty": {"const": 0.0, "spx": 0.3, "brent": -0.02},
             "stocks": {"BPCL": {"const": 0.0, "beta": 1.0, "crude": -0.05, "resid_sd": 1.0}}}
    g = overnight.predict_gap("BPCL", model, spx=1.0, brent=4.0)
    assert round(g, 3) == round(0.3 - 0.08 - 0.2, 3)


def test_priced_in_gap_lowers_a_backed_spurt_target():
    now = datetime(2026, 11, 16, 10, 0)
    res = {"symbols": ["TCS"], "kind": "filing", "category": "RESULTS", "sentiment": 1.0, "impact": 3, "headline": "TCS results"}
    on = {"label": "priced in", "expected_gap_pct": 1.0, "preopen_gap_pct": 1.5}
    v = newsspurt.classify("TCS", "up", [res], now, overnight_note=on)
    assert v["verdict"] == "backed" and v["target"] == 10.0 and "priced in" in v["why"]
    assert newsspurt.classify("TCS", "up", [res], now, overnight_note={**on, "label": "under-reacted"})["target"] == 15.0
