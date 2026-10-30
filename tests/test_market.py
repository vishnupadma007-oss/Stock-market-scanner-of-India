from datetime import datetime

from agents import intel, market

NOW = datetime(2026, 10, 21, 11, 0)


def item(headline, t="2026-10-21 10:30:00"):
    return intel.make_item(id=headline[:20], time=t, source="ET", kind="news", headline=headline)


def test_themes_and_why():
    items = [item("Sensex tanks 800 points as FIIs pull out Rs 5,000 crore"),
             item("Crude oil jumps 4% after attack on Gulf tanker"),
             item("RBI keeps repo rate unchanged, warns on inflation")]
    assert "flows" in market.theme_of(items[0]["headline"])
    assert {"geopolitical", "commodities"} <= set(market.theme_of(items[1]["headline"]))
    ctx = market.context(items, NOW, nifty_pct=-1.1, vix=16.2, vix_pct=8.0)
    assert ctx["trend"] == "sliding" and "geopolitical" in ctx["drivers"]
    assert ctx["notes"][0] == "Nifty -1.10% (sliding)"


def test_headwind_blocks_trades_against_a_strong_market():
    bad = {"nifty_pct": -1.2, "mood": "negative", "mood_tone": -0.4}
    assert market.headwind(bad, "up") and market.headwind(bad, "down") is None
    good = {"nifty_pct": 1.0, "mood": "positive", "mood_tone": 0.3}
    assert market.headwind(good, "down") and market.headwind(good, "up") is None
    assert market.headwind({"nifty_pct": -0.3, "mood": "negative", "mood_tone": -0.4}, "up") is None
