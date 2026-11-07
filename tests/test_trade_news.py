from datetime import datetime

from agents import trade_news as tn

TRADE = {"date": "2026-11-02", "opened": "10:00", "symbol": "PNB", "side": "loser", "notes": "",
         "target_bid": "10.00", "entry_ask": "9.00"}
NOW = datetime(2026, 11, 2, 11, 0)
CFG = {"use_ai": False}


def item(t, headline, sentiment, impact=3, symbols=("PNB",), kind="news", scope="stock", category=""):
    return {"time": f"2026-11-02 {t}:00", "headline": headline, "sentiment": sentiment, "impact": impact,
            "symbols": list(symbols), "kind": kind, "scope": scope, "category": category, "sectors": [],
            "source": "test"}


def test_news_before_entry_is_ignored():
    assert tn.check(TRADE, [item("09:30", "PNB fraud probe", -1)], NOW, cfg=CFG)["action"] == "hold"


def test_bad_own_news_after_entry_exits_a_call():
    assert tn.check(TRADE, [item("10:30", "PNB fraud probe", -1)], NOW, cfg=CFG)["action"] == "exit"


def test_regulatory_filing_exits():
    it = item("10:30", "RBI penalty on PNB", 0, impact=2, kind="filing", category="REGULATORY")
    assert tn.check(TRADE, [it], NOW, cfg=CFG)["action"] == "exit"


def test_bad_news_for_the_stock_is_good_for_a_put():
    put = {**TRADE, "side": "gainer"}
    assert tn.check(put, [item("10:30", "PNB fraud probe", -1)], NOW, cfg=CFG)["action"] == "raise"


def test_raise_only_once_and_on_the_tick():
    assert tn.check({**TRADE, "notes": "news target raised to 10.45"}, [item("10:30", "PNB wins", 1)],
                    NOW, cfg=CFG)["action"] == "hold"
    assert tn.raised_target(TRADE, {"raise_pct": 5}) == 10.45


def test_market_news_off_by_default_in_config_but_shock_exits():
    mk = item("10:30", "War escalates", -1, symbols=(), scope="global")
    assert tn.check(TRADE, [mk], NOW, cfg={**CFG, "market_impact": 99})["action"] == "hold"
    assert tn.check(TRADE, [], NOW, "crash", CFG)["action"] == "exit"
    assert tn.check({**TRADE, "side": "gainer"}, [], NOW, "crash", CFG)["action"] == "hold"
