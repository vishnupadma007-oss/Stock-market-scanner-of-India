from agents import sector_results as sr


def figs(rev_yoy, rev_qoq, pat_yoy, pat_qoq):
    return {"revenue": {"yoy_pct": rev_yoy, "qoq_pct": rev_qoq}, "profit": {"yoy_pct": pat_yoy, "qoq_pct": pat_qoq}}


def test_seasonal_cement_is_read_on_yoy_only():
    # Monsoon quarter: down sharply vs April-June, but up vs last year's monsoon quarter.
    r = sr.score(figs(12, -15, 20, -30), "ULTRACEMCO")
    assert r["view"] == "strong" and "monsoon" in r["how_read"]


def test_non_seasonal_qoq_slide_still_counts():
    assert sr.score(figs(12, -15, 20, -30), "NESTLEIND")["score"] < sr.score(figs(12, -15, 20, -30), "ULTRACEMCO")["score"] \
        or sr.profile("NESTLEIND")["season"]


def test_it_is_read_on_the_sequential_trend():
    weak_qoq = sr.score(figs(10, -1.0, 12, -4), "INFY")  # good YoY, but the quarter shrank
    assert weak_qoq["view"] in ("weak", "mixed") and "QoQ" in weak_qoq["how_read"]
    assert sr.score(figs(6, 3.0, 8, 5), "TCS")["view"] == "strong"


def test_sector_kpis_are_pulled_out():
    text = "Net Interest Income grew 12% YoY to Rs 31,000 crore\nNIM at 3.4%\nGross NPA 1.3%\nThe board met today"
    assert sr.kpi_lines(text, "HDFCBANK") == ["Net Interest Income grew 12% YoY to Rs 31,000 crore", "NIM at 3.4%", "Gross NPA 1.3%"]
    assert sr.kpi_lines("Constant currency revenue growth 1.8% QoQ\nTCV of deal wins $2.1 bn", "INFY")[0].startswith("Constant")
