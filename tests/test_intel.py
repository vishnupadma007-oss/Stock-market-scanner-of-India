from datetime import datetime

from agents import analyzer, intel, newsfeed
from agents.config import load_config

CFG = load_config()
NOW = datetime(2026, 10, 21, 11, 0)


def item(headline, t="2026-10-21 10:30:00", source="Economic Times", kind="news", **kw):
    return intel.make_item(id=headline[:20], time=t, source=source, kind=kind, headline=headline, **kw)


def test_linking_and_tone():
    i = item("Brokerages back ICICI Bank on strong Q2 earnings, see HDFC Bank recovery ahead")
    assert i["symbols"] == ["HDFCBANK", "ICICIBANK"] and i["scope"] == "stock" and i["sentiment"] > 0
    assert item("SBI data breach probe: hackers allegedly access accounts")["sentiment"] < 0
    assert item("Brent crude jumps as OPEC extends supply cuts")["scope"] == "global"
    assert item("A Cold War missile base in Kansas has a silo")["scope"] == ""  # not finance
    assert item("Sensex tumbles 876 points as FIIs sell")["scope"] == "market"
    assert item("Pharma stocks rally on USFDA approvals")["sectors"] == ["Pharma"]
    assert item("Tata Steel faces probe over fraud")["impact"] == 3


def test_rss_parsing():
    xml = """<rss><channel><item><title>Infosys shares jump 5% after deal win</title>
             <link>https://x</link><pubDate>Wed, 21 Oct 2026 05:00:00 GMT</pubDate></item></channel></rss>"""
    [i] = newsfeed.parse(xml, "Test")
    assert i["symbols"] == ["INFY"] and i["time"] == "2026-10-21 10:30:00" and i["sentiment"] > 0


def test_analyzer_needs_agreement_and_fades_old_news():
    good = [item("Infosys shares jump on strong results", source="ET"),
            item("Infosys rallies after big deal win", source="Mint"),
            item("Infosys beats estimates, brokerages upgrade", source="CNBC-TV18")]
    v = analyzer.stock_view("INFY", good, NOW, CFG)
    assert v["direction"] == "up" and v["strong"] and len(v["sources"]) == 3
    one = analyzer.stock_view("INFY", good[:1], NOW, CFG)
    assert not one["strong"]  # one ordinary headline is not enough
    old = [dict(i, time="2026-10-20 09:00:00") for i in good]
    assert abs(analyzer.stock_view("INFY", old, NOW, CFG)["score"]) < abs(v["score"])  # news fades


def test_market_noise_does_not_swamp_a_stock():
    gloom = [item(f"Sensex falls as FIIs sell, day {n}", source=f"S{n}") for n in range(300)]
    filing = intel.make_item(id="f1", time="2026-10-21 10:00:00", source="NSE filing", kind="filing",
                             headline="TCS results: profit up 20%", symbols=["TCS"], sentiment=1.0, impact=3)
    v = analyzer.stock_view("TCS", gloom + [filing], NOW, CFG)
    assert v["direction"] == "up" and v["strong"]  # 300 gloomy market headlines are averaged, not summed


def test_analyzer_voice_in_trade_decision():
    up = {"direction": "up", "confidence": 70, "reasons": ["x"]}
    assert analyzer.as_extra(up, "loser", CFG)["points"] == 10     # CE on a loser, news says up
    assert analyzer.as_extra(up, "gainer", CFG)["points"] == -20   # PE on a gainer, news says up
    assert analyzer.as_extra({**up, "confidence": 10}, "gainer", CFG)["points"] == 0


def test_analyzer_accepts_ist_aware_time():
    from zoneinfo import ZoneInfo
    v = analyzer.stock_view("INFY", [item("Infosys shares jump on strong results")],
                            NOW.replace(tzinfo=ZoneInfo("Asia/Kolkata")), CFG)
    assert v["direction"] in ("up", "neutral")


def test_tone_negation_and_hedging():
    assert intel.tone("Company does not expect growth this year") < 0
    assert intel.tone("Margins did not decline despite costs") > 0
    assert intel.tone("Profit jumps on strong demand") == 1.0
    hedged = intel.tone("Profit may rise if demand could improve amid uncertain headwinds")
    assert 0 < hedged < 1.0
