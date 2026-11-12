import json
from datetime import date, datetime

import numpy as np
import pandas as pd

import watcher
from agents import expectations, intel


def closes(values, end="2026-10-20"):
    idx = pd.bdate_range(end=end, periods=len(values))
    return pd.DataFrame({"Close": values}, index=idx)


def test_run_up_measures_against_nifty_before_the_event():
    stock = closes(np.r_[np.full(20, 100.0), np.linspace(100, 115, 6), 130.0])  # last candle is event day
    nifty = closes(np.full(27, 20000.0))
    run = expectations.run_up(stock, nifty, date(2026, 10, 20))
    assert run["stock_5d"] == 15.0 and run["vs_nifty_5d"] == 15.0  # event-day jump left out
    assert expectations.day_move(stock, date(2026, 10, 20)) == round((130 / 115 - 1) * 100, 2)
    assert expectations.day_move(stock, date(2026, 10, 21)) is None


def test_assess_labels():
    hot = expectations.assess({"vs_nifty_20d": 17.7}, {"stories": 6, "tone": 1.0}, {"upside_pct": -6.4, "target": 1665})
    assert hot["priced_in"] == 80 and hot["label"] == "largely priced in" and "clear beat" in hot["bar"]
    assert expectations.assess({"vs_nifty_20d": 6}, {}, {})["label"] == "partly priced in"
    cold = expectations.assess({"vs_nifty_20d": -12}, {"stories": 5, "tone": -0.5}, {"upside_pct": 25, "target": 900})
    assert cold["priced_in"] == -70 and cold["label"] == "pessimism priced in"
    assert expectations.assess({}, {}, {})["label"] == "not priced in"


def test_analysts_from_indmoney_details():
    d = {"analyst_forecast": {"target_price": {"mean": 1665, "high": 1951, "upside_per": -6.41, "num_analysts": 39},
                              "consensus": {"buy_per": 58.97}}}
    assert expectations.analysts(d) == {"upside_pct": -6.41, "target": 1665, "high": 1951, "analysts": 39, "buy_pct": 58.97}
    assert expectations.analysts({}) == {}


def test_reaction_and_forecast_adjustment():
    assert "sell the news" in expectations.reaction("strong", -2.0)
    assert "relief" in expectations.reaction("weak", 1.5)
    assert expectations.reaction("strong", 2.0) is None
    view = {"direction": "up", "confidence": 70}
    hot = {"priced_in": 60, "label": "largely priced in", "bar": "needs a clear beat"}
    assert expectations.adjust_forecast(view, hot)["confidence"] == 45
    assert expectations.adjust_forecast({"direction": "down", "confidence": 70}, hot)["confidence"] == 70
    assert expectations.adjust_forecast(view, {"error": "x"}) == view


def test_hype_counts_news_before_the_event(monkeypatch, tmp_path):
    monkeypatch.setattr(intel, "DIR", tmp_path)
    tmp_path.mkdir(exist_ok=True)
    items = [intel.make_item(id=f"n{i}", time=f"2026-10-1{i} 10:00:00", source="ET", kind="news",
                             headline="Tech Mahindra shares surge on deal win") for i in range(5, 9)]
    items.append(intel.make_item(id="late", time="2026-10-20 16:00:00", source="ET", kind="news",
                                 headline="Tech Mahindra shares jump after results"))
    with open(tmp_path / "2026-10-18.jsonl", "w") as f:
        f.write("\n".join(json.dumps(i) for i in items))
    h = expectations.hype("TECHM", datetime(2026, 10, 20, 15, 0))
    assert h["stories"] == 4 and h["tone"] == 1.0


def test_forecast_event_carries_priced_in(monkeypatch, capsys):
    watcher._daily.clear()
    watcher.reset_daily("2026-10-21")
    view = {"symbol": "TECHM", "strong": True, "direction": "up", "confidence": 80, "score": 3.0}
    monkeypatch.setattr(watcher.analyzer, "recent_items", lambda now: [])
    monkeypatch.setattr(watcher.analyzer, "stock_view", lambda s, items, now, cfg: view if s == "TECHM" else {"strong": False})
    monkeypatch.setattr(watcher.analyzer, "market_mood", lambda items, now: {"mood": 0.1})
    monkeypatch.setattr(watcher, "check_expectations",
                        lambda s, now, v=None: {"priced_in": 80, "label": "largely priced in", "bar": "needs a clear beat"})
    watcher.run_analyzer({"universe": ["TECHM", "TCS"]}, datetime(2026, 10, 21, 11, 0))
    kind, body = capsys.readouterr().out.strip().split(" ", 1)
    payload = json.loads(body)
    assert kind == "FORECAST" and payload["confidence"] == 55
    assert payload["priced_in"]["label"] == "largely priced in" and "priced_in_note" in payload


SNAP = {"TECHM": {"pe": 28.6, "forward_pe": 19.9, "peg": 1.86, "profit_growth": 0.325},
        "INFY": {"pe": 15.4}, "TCS": {"pe": 18.0}, "WIPRO": {"pe": 17.0}, "HCLTECH": {"pe": 20.0},
        "HDFCBANK": {"pe": 15.6, "pb": 1.87}, "ICICIBANK": {"pb": 2.9}, "AXISBANK": {"pb": 1.9},
        "KOTAKBANK": {"pb": 2.6}, "PAYTM": {"pe": -20.0, "pb": 3.0}}


def test_valuation_against_sector_peers():
    from agents import valuation
    techm = valuation.assess("TECHM", SNAP)
    assert techm["label"] == "expensive vs peers" and techm["rich"] == 30 and techm["metric"] == "P/E"
    assert "forward P/E 19.9" in techm["notes"][0] and "profit growth +32%" in techm["notes"][0]
    hdfc = valuation.assess("HDFCBANK", SNAP)  # lenders on price-to-book
    assert hdfc["metric"] == "P/B" and hdfc["rich"] == -15
    assert valuation.assess("NESTLEIND", SNAP)["label"] == "unknown"
    assert valuation.assess("INFY", SNAP)["rich"] <= -15


def test_valuation_extra_observe_and_score():
    from agents import valuation
    rich = {"rich": 30, "label": "expensive vs peers", "notes": ["Valuation: P/E 28.6"]}
    watch = valuation.as_extra(rich, "gainer", {})
    assert watch["points"] == 0 and watch["would_score"] == 5 and watch["notes"][0].startswith("(observe)")
    scored = valuation.as_extra(rich, "loser", {"valuation": {"mode": "score"}})
    assert scored["points"] == -5  # buying a CE on an expensive faller argues against the bounce


def test_valuation_feeds_priced_in():
    base = expectations.assess({"vs_nifty_20d": 6}, {}, {})
    rich = expectations.assess({"vs_nifty_20d": 6}, {}, {}, {"rich": 30, "notes": ["Valuation: expensive"]})
    assert rich["priced_in"] == base["priced_in"] + 15 and "Valuation: expensive" in rich["notes"]
