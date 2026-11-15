from agents import adr_team as A

BASE = {"adr_pct": {"INFY": 0.3, "WIPRO": -0.2, "HDFCBANK": 0.1, "ICICIBANK": 0.4, "DRREDDY": 0.0},
        "adr_vol_x": {}, "nifty_gap_pct": 0.1, "vix_pct": 0, "brent_pct": 0.5, "usdinr_pct": 0.1}


def test_regimes():
    assert A.classify_regime("INFY", BASE)["regime"] == 4
    macro = A.classify_regime("INFY", {**BASE, "nifty_gap_pct": -1.6})
    assert macro["regime"] == 1 and macro["direction"] == "down" and macro["trigger"] == "gap"
    assert A.classify_regime("INFY", {**BASE, "brent_pct": 5.0})["trigger"] == "oil-fx"
    sector = {**BASE, "adr_pct": {**BASE["adr_pct"], "INFY": 2.0, "WIPRO": 1.8}}
    assert A.classify_regime("WIPRO", sector)["regime"] == 2 and A.classify_regime("HDFCBANK", sector)["regime"] == 4
    stock = {**BASE, "adr_pct": {**BASE["adr_pct"], "DRREDDY": -3.0}, "adr_vol_x": {"DRREDDY": 2.2}}
    g = A.classify_regime("DRREDDY", stock)
    assert g["regime"] == 3 and g["direction"] == "down"
    assert A.classify_regime("DRREDDY", {**stock, "adr_vol_x": {"DRREDDY": 1.0}})["regime"] == 0


def test_fade_decision_follows_the_backtest():
    stock = {"regime": 3, "direction": "down", "why": "ADR -3%"}
    assert A.fade_decision("DRREDDY", stock, None)["direction"] == "up"
    macro = {"regime": 1, "direction": "up", "trigger": "gap", "why": "gap"}
    assert A.fade_decision("INFY", macro, -0.4)["direction"] == "down"      # first hour already turned down
    assert A.fade_decision("INFY", macro, +0.4) is None                     # still running with the gap
    assert A.fade_decision("INFY", {**macro, "trigger": "oil-fx"}, -0.4) is None
    assert A.fade_decision("INFY", {"regime": 4, "direction": None}, 0.1) is None


def test_implied_price_and_signal():
    assert round(A.implied_nse_price(60.0, 90.0, 3), 1) == 1800.0
    assert A.expected_gap_pct(1.0, 0.2) == 1.2
    sig = A.generate_trade_signal("INFY", {"regime": 3, "name": "stock catalyst", "direction": "up", "why": "x"}, 1502.0, step=20)
    assert sig["option"] == "CE" and sig["strike"] == 1500
