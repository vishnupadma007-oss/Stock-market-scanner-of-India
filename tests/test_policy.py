from agents import policy


def hits(headline):
    return {i["symbol"]: (i["direction"], i["strength"]) for i in policy.assess(headline)}


def test_irdai_commission_caps_hit_policybazaar_hardest():
    h = hits("IRDAI proposes commission caps and clawback for mis-selling in 'Recalibrating Economics of Insurance Distribution'")
    assert h["POLICYBZR"] == (-1, 3) and h["HDFCBANK"] == (-1, 1)


def test_rbi_rate_cut_winners_and_losers():
    h = hits("RBI cuts repo rate by 25 bps to 5.25%, monetary policy committee votes 5-1")
    assert h["BAJFINANCE"] == (1, 2) and h["DLF"] == (1, 2) and h["MARUTI"] == (1, 1) and h["SBIN"] == (-1, 1)


def test_other_policy_moves():
    assert hits("US raises H-1B visa fee to $100,000")["INFY"] == (-1, 2)
    assert hits("GST Council cuts GST on small cars and two-wheelers to 18%")["MARUTI"] == (1, 2)
    assert hits("Government cuts customs duty on gold to 6%")["TITAN"] == (1, 1)
    assert hits("Government hikes import duty on gold")["TITAN"] == (-1, 1)
    assert hits("SEBI bars Paytm from onboarding new clients")["PAYTM"] == (-1, 3)
    assert hits("USFDA issues warning letter to Sun Pharma's Halol plant")["SUNPHARMA"] == (-1, 3)
    assert hits("Sensex rises 300 points led by Infosys") == {}


def test_policy_items_feed_the_analyzer():
    item = {"id": "n1", "time": "2026-10-21 10:00:00", "source": "ET", "headline": "RBI cuts repo rate by 25 bps", "url": ""}
    out = policy.to_intel(item, policy.assess(item["headline"]))
    baj = next(i for i in out if i["symbols"] == ["BAJFINANCE"])
    assert baj["kind"] == "policy" and baj["sentiment"] == 0.67 and baj["impact"] == 2


def test_negation_talk_and_false_alarms():
    assert hits("Visa curbs not targeted at India, says Rubio")["INFY"] == (1, 1)  # relief, not a hit
    assert hits("RBI may need to raise repo rate to 6.25%: SBI MF")["BAJFINANCE"] == (-1, 1)
    assert hits("RBI hikes repo rate to 5.5%; rules out rate cuts in near term")["BAJFINANCE"] == (-1, 2)
    assert "BHARTIARTL" not in hits("Hotel tariffs in Delhi top Rishikesh")
    assert hits("Airtel, Jio raise mobile tariffs by 15%")["BHARTIARTL"] == (1, 2)
    assert hits("Bajaj Finance launches term loans as RBI weighs revolving credit ban")["BAJFINANCE"] == (-1, 2)


def test_delay_or_softening_is_mild_relief():
    h = hits("PB Fintech: IRDAI Open To Extending Feedback Period On Distribution Reforms Paper")
    assert h["POLICYBZR"] == (1, 1)
    assert hits("FIDC to represent NBFCs' case to IRDAI for gradual reset of insurance commissions")["POLICYBZR"] == (1, 1)
    assert hits("IRDAI proposes commission caps on insurance distribution")["POLICYBZR"] == (-1, 3)  # the original blow


def test_one_policy_story_from_two_feeds_is_one_source():
    from datetime import datetime
    from agents import analyzer
    out = []
    for feed in ("Google: India macro", "Google: regulators & policy"):
        item = {"id": f"n-{feed}", "time": "2026-10-22 11:53:25", "source": feed,
                "headline": "RBI hikes repo rate by 25 bps", "url": ""}
        out += policy.to_intel(item, policy.assess(item["headline"]))
    v = analyzer.stock_view("BAJAJFINSV", out, datetime(2026, 10, 22, 12, 0))
    assert v["sources"] == ["Policy rules"] and not v["strong"]


def test_economists_expectations_are_talk():
    assert hits("RBI MPC minutes: Economists expect repo rate hike in December")["BAJFINANCE"] == (-1, 1)


def test_one_policy_story_from_two_feeds_counts_once_in_the_score():
    from datetime import datetime
    from agents import analyzer
    out = []
    for feed in ("Google: India macro", "Google: regulators & policy"):
        item = {"id": f"n-{feed}", "time": "2026-10-22 20:55:25", "source": feed,
                "headline": "Hawkish Turn: RBI raises rates as crude, yields and outflows hit rupee - Forbes India", "url": ""}
        out += policy.to_intel(item, policy.assess(item["headline"]))
    once = [i for i in out if i["source"].endswith("India macro)")]
    now = datetime(2026, 10, 23, 9, 0)
    assert analyzer.stock_view("BAJFINANCE", out, now)["score"] == analyzer.stock_view("BAJFINANCE", once, now)["score"]


def test_many_articles_about_one_policy_event_count_once():
    from datetime import datetime
    from agents import analyzer
    heads = ["RBI raises repo rate by 25 basis points to 5.50%", "Hawkish Turn: RBI raises rates as crude hits rupee",
             "RBI Repo Rate Hike Puts India's Housing Recovery Under Pressure"]
    out = []
    for n, h in enumerate(heads):
        item = {"id": f"n{n}", "time": f"2026-10-2{1 + n} 10:00:00", "source": "Google: India macro", "headline": h, "url": ""}
        out += policy.to_intel(item, policy.assess(h))
    dlf = [i for i in out if i["symbols"] == ["DLF"]]
    assert len(dlf) == 3
    kept = analyzer._one_per_story(dlf)
    assert len(kept) == 1 and kept[0]["time"].startswith("2026-10-23")  # the latest of the strongest
