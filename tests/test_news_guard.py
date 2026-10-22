from datetime import datetime

from agents import intel, news_guard, policy

NOW = datetime(2026, 9, 24, 11, 0)


def irdai_items():
    item = intel.make_item(id="n1", time="2026-09-24 09:20:00", source="ET", kind="news",
                           headline="IRDAI proposes commission caps and clawback for mis-selling; PolicyBazaar shares crash")
    return [item] + policy.to_intel(item, policy.assess(item["headline"]))


def test_policybazaar_bounce_is_blocked():
    # 24 Sep 2026: PB Fintech is a top loser; the chart shows a bounce, but IRDAI just hit its business.
    g = news_guard.check("POLICYBZR", "loser", irdai_items(), [], NOW)
    assert g["block"] and "Policy hit" in g["notes"][0]


def test_same_news_does_not_block_a_put():
    assert not news_guard.check("POLICYBZR", "gainer", irdai_items(), [], NOW)["block"]


def test_results_and_regulatory_filings_block_any_side():
    results = [{"category": "RESULTS", "time": "2026-09-24 12:30:00", "text": "financial results"}]
    assert news_guard.check("TCS", "gainer", [], results, NOW)["block"]
    order = [{"category": "REGULATORY", "time": "2026-09-24 10:00:00", "text": "SEBI order against the company"}]
    assert news_guard.check("TCS", "loser", [], order, NOW)["block"]
    yesterday = [{"category": "RESULTS", "time": "2026-09-23 16:30:00", "text": "financial results"}]
    assert not news_guard.check("TCS", "gainer", [], yesterday, NOW)["block"]


def test_quiet_stock_passes():
    assert news_guard.check("WIPRO", "gainer", irdai_items(), [], NOW) == {"block": False, "points": 0, "notes": []}


def test_headlines_describing_the_move_do_not_block():
    # 21 Oct: Infosys was a top gainer with "IT stocks on fire" headlines; the PUT made +Rs 620.
    hype = [intel.make_item(id=f"h{k}", time="2026-09-24 10:0%d:00" % k, source=src, kind="news",
                            headline=f"Infosys shares surge 3% as IT stocks rally, Jefferies bullish {k}")
            for k, src in enumerate(("ET", "Mint", "CNBC-TV18"))]
    assert not news_guard.check("INFY", "gainer", hype, [], NOW)["block"]
    fraud = hype + [intel.make_item(id="f", time="2026-09-24 10:30:00", source="ET", kind="news",
                                    headline="Infosys faces fraud probe in US, shares plunge")]
    assert news_guard.check("INFY", "loser", fraud, [], NOW)["block"]  # a real cause against a CALL
