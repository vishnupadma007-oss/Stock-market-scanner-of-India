import json
from datetime import date, datetime
from zoneinfo import ZoneInfo

import numpy as np

import paper_trade
import watcher
from agents import announcements, commodities, news
from agents.config import load_config
from tests.test_agents import intraday

IST = ZoneInfo("Asia/Kolkata")
CFG = load_config()


def filing(symbol, desc, text, seq="1", t="2026-10-21 11:05:00", pdf="x.pdf"):
    return {"symbol": symbol, "desc": desc, "attchmntText": text, "seq_id": seq, "sort_date": t,
            "attchmntFile": pdf}


def test_classify_real_filing_shapes():
    assert announcements.classify(filing("TECHM", "Outcome of Board Meeting",
        "Tech Mahindra Limited has submitted to the Exchange, the financial results for the period ended September 30")) == "RESULTS"
    assert announcements.classify(filing("YESBANK", "Credit Rating", "informed the Exchange about Credit Rating")) == "RATING"
    assert announcements.classify(filing("RECLTD", "Scheme of Arrangement", "Scheme of Arrangement")) == "DEAL"
    assert announcements.classify(filing("BEL", "Bagging/Receiving of orders/contracts", "orders worth Rs 500 crore")) == "ORDER"
    assert announcements.classify(filing("X", "Copy of Newspaper Publication", "Copy of Newspaper Publication")) is None
    assert announcements.classify(filing("X", "Record Date", "Record date for dividend")) is None


def test_material_filters_universe_and_date():
    rows = [filing("TECHM", "Credit Rating", "Credit Rating", seq="2"),
            filing("SMALLCO", "Credit Rating", "Credit Rating", seq="3"),
            filing("TECHM", "Credit Rating", "Credit Rating", seq="4", t="2026-10-19 10:00:00")]
    out = announcements.material(rows, {"TECHM"}, since="2026-10-21")
    assert [x["seq_id"] for x in out] == ["2"]


# Layout copied from TECHM's Q2 FY27 filing (pdftotext -layout).
TECHM = """
   1    Revenue from Operations                                                           161,802          157,119          139,949           318,921
  11    Profit after tax (9 - 10)                                                          16,097           14,863           12,017            30,960
        • Revenue ₹ 16,180 crores; up 3.0% QoQ, up 15.6% YoY
        • Bonus ratio 1:1, i.e. one (1) new fully paid-up Bonus Equity Share
"""


def test_results_figures_and_read():
    f = announcements.figures_from_text(TECHM)
    assert f["revenue"]["yoy_pct"] == 15.6 and f["revenue"]["qoq_pct"] == 3.0
    assert f["profit"]["quarter"] == 16097 and f["profit"]["yoy_pct"] == 34.0
    assert announcements.score_results(f)["view"] == "strong"
    assert announcements.highlights(TECHM) == ["• Revenue ₹ 16,180 crores; up 3.0% QoQ, up 15.6% YoY"]
    loss = announcements.figures_from_text("  9 Net Profit / (Loss) for the period   (1,200)   300   900")
    assert loss["profit"]["quarter"] == -1200 and announcements.score_results(loss)["view"] in ("weak", "mixed")


def test_commodities_agent():
    up = commodities.assess("HINDALCO", "gainer", {"aluminium": 2.5, "copper": 0.3}, CFG)
    assert up["points"] == -20 and "Aluminium" in up["notes"][0]  # PE on HINDALCO while aluminium rallies
    assert commodities.assess("HINDALCO", "loser", {"aluminium": 2.5}, CFG)["points"] == 0
    shock = commodities.shocks({"crude oil": -4.2, "gold": 0.5}, CFG)
    assert shock == [{"commodity": "crude oil", "change_pct": -4.2, "stocks_affected": ["ASIANPAINT", "BPCL", "IOC", "ONGC"]}]


def test_news_agent_uses_nse_filings():
    flat = intraday(np.full(40, 100.0))
    res = news.assess("TCS", "loser", -3, date(2026, 10, 21), [], {}, flat, CFG,
                      filings=[{"category": "RESULTS", "time": "2026-10-21 10:05:00", "text": ""}])
    assert res["block"]
    order = news.assess("BEL", "gainer", 3, date(2026, 10, 21), [], {}, flat, CFG,
                        filings=[{"category": "ORDER", "time": "2026-10-21 10:05:00", "text": "orders worth Rs 500 crore"}])
    assert order["points"] == -15 + 5 and any("NSE filing" in n for n in order["notes"])


def test_poll_filings_emits_once(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(watcher, "FILINGS_LOG", tmp_path / "ann.csv")
    monkeypatch.setattr(watcher.intel, "DIR", tmp_path / "intel")
    rows = [filing("TCS", "Outcome of Board Meeting", "submitted the financial results for the quarter", seq="9",
                   t="2026-10-21 10:30:00", pdf="https://nse/x.pdf"),
            filing("BEL", "Credit Rating", "Credit Rating", seq="8", t="2026-10-21 10:20:00"),
            filing("PNB", "Action(s) taken or orders passed", "penalty imposed by RBI", seq="7", t="2026-10-21 10:10:00")]
    monkeypatch.setattr(watcher.announcements, "fetch_feed", lambda: rows)
    monkeypatch.setattr(watcher.announcements, "results_summary",
                        lambda url: {"figures": announcements.figures_from_text(TECHM), "highlights": []})
    watcher._daily.clear()
    now = datetime(2026, 10, 21, 10, 31, tzinfo=IST)
    watcher.poll_filings(CFG, now)
    lines = capsys.readouterr().out.strip().splitlines()
    # Major filing (regulatory) and results wake Claude; the routine rating only feeds the analyzer.
    assert [l.split(" ", 1)[0] for l in lines] == ["NEWS", "RESULT"]
    assert json.loads(lines[1].split(" ", 1)[1])["read"]["view"] == "strong"
    logged = [json.loads(l) for l in (tmp_path / "intel").glob("*.jsonl").__next__().read_text().splitlines()]
    assert {i["category"] for i in logged} == {"REGULATORY", "RATING", "RESULTS"}
    watcher.poll_filings(CFG, now)
    assert capsys.readouterr().out == ""  # nothing repeated
    assert watcher._daily["filings"]["TCS"][0]["category"] == "RESULTS"
    assert (tmp_path / "ann.csv").read_text().count("\n") == 4  # header + 3


def test_paper_trade_rules():
    open_row = [{"status": "OPEN"}]
    at = lambda h, m, d=21: datetime(2026, 10, d, h, m, tzinfo=IST)
    assert "closed" in paper_trade.check_rules([], at(11, 0, 20), CFG)  # Dussehra
    assert "window" in paper_trade.check_rules([], at(9, 30), CFG)
    assert "already open" in paper_trade.check_rules(open_row, at(11, 0), CFG)
    assert paper_trade.check_rules([], at(11, 0), CFG) is None


def test_scanned_misreads_are_not_trusted():
    # Real row from a scanned Bajaj Finance filing: "4,2so.n" is a misread figure.
    bad = "7    Profit after tax (5-6)     5,536.10      5,345.52         4,2so.n        10,881.62"
    good = "  Net profit for the period      10,881.62     8,383.85     8,455.00"
    f = announcements.figures_from_text(bad + "\n" + good)
    assert f["profit"]["quarter"] == 10881.62 and f["profit"]["year_ago"] == 8455.0
    assert announcements.figures_from_text(bad) == {}


def test_contract_expiry_from_name():
    from agents.indmoney import contract_expiry
    today = date(2026, 10, 20)
    assert contract_expiry("CRUDEOIL 19 Oct Fut", today) == date(2026, 10, 19)  # expired yesterday
    assert contract_expiry("CRUDEOIL 18 Nov Fut", today) == date(2026, 11, 18)
    assert contract_expiry("GOLD 05 Feb Fut", date(2026, 12, 20)) == date(2027, 2, 5)
