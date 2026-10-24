"""Sector Results analyst: how to read a quarter for each kind of business.

A flat "profit up 20%" read misses how sectors work:
  - Seasonal businesses (cement in the monsoon quarter, autos and retail around festivals, power
    in summer, consumer goods around the rural harvest) are judged against the SAME quarter last
    year; comparing with the previous quarter mostly shows the season.
  - IT services and telecom are judged on the sequential trend (quarter on quarter), the way
    their investors and managements track them.
  - Each sector has the few numbers the market actually trades on (NIM and bad loans for banks,
    constant-currency growth and deal wins for IT, EBITDA per tonne for cement and steel, ARPU for
    telecom, same-store growth for retail...). These are pulled out of the filing and press
    release so Claude can judge them; machine reading of these lines is approximate.
"""
import re

from .sectors import sector_of

# Finer groups than the sector indices: how the market reads each business.
GROUPS = {
    "bank": ["HDFCBANK", "ICICIBANK", "AXISBANK", "KOTAKBANK", "INDUSINDBK", "IDFCFIRSTB", "FEDERALBNK", "AUBANK",
             "SBIN", "BANKBARODA", "PNB", "CANBK"],
    "nbfc": ["BAJFINANCE", "BAJAJFINSV", "SHRIRAMFIN", "CHOLAFIN", "MUTHOOTFIN", "RECLTD", "PFC"],
    "fintech": ["PAYTM", "POLICYBZR"],
    "it": ["INFY", "TCS", "WIPRO", "HCLTECH", "TECHM", "PERSISTENT", "COFORGE", "MPHASIS"],
    "auto": ["MARUTI", "M&M", "EICHERMOT", "HEROMOTOCO", "BAJAJ-AUTO", "TVSMOTOR"],
    "cement": ["ULTRACEMCO", "GRASIM"],
    "metal": ["TATASTEEL", "JSWSTEEL", "HINDALCO", "VEDL", "SAIL", "NMDC", "NATIONALUM", "COALINDIA"],
    "oil_gas": ["RELIANCE", "ONGC", "BPCL", "IOC", "GAIL"],
    "power": ["NTPC", "POWERGRID", "TATAPOWER"],
    "fmcg": ["ITC", "HINDUNILVR", "NESTLEIND", "BRITANNIA", "ASIANPAINT"],
    "pharma": ["SUNPHARMA", "CIPLA", "DRREDDY", "DIVISLAB", "LUPIN"],
    "hospital": ["APOLLOHOSP"],
    "telecom": ["BHARTIARTL"],
    "retail": ["TRENT", "TITAN", "ETERNAL"],
    "realty": ["DLF"],
    "capital_goods": ["LT", "BHEL", "HAL", "BEL", "DIXON", "ADANIENT", "ADANIPORTS"],
}
GROUP_OF = {s: g for g, members in GROUPS.items() for s in members}

PROFILES = {
    # compare: which comparison leads ("yoy" for seasonal or lumpy businesses, "qoq" where the
    # sequential trend is what investors track). kpis: the lines worth pulling from the filing.
    "bank": {"compare": "yoy", "season": None,
             "kpis": r"\bnii\b|net interest income|\bnim\b|net interest margin|gross npa|\bgnpa\b|net npa|\bnnpa\b|"
                     r"credit cost|slippage|advances|loan growth|deposits?|\bcasa\b|provision"},
    "nbfc": {"compare": "yoy", "season": None,
             "kpis": r"\baum\b|assets under management|disbursement|\bnim\b|net interest income|credit cost|gross stage 3|"
                     r"\bgnpa\b|gross npa|customer franchise|cost of funds|loan losses"},
    "fintech": {"compare": "yoy", "season": None,
                "kpis": r"contribution margin|adjusted ebitda|premium|gmv|disbursement|take rate|insurance premium|"
                        r"core online|new initiatives|payment processing"},
    "it": {"compare": "qoq", "season": None,
           "kpis": r"constant currency|\bcc\b|deal wins?|\btcv\b|total contract value|ebit margin|operating margin|"
                   r"attrition|headcount|guidance|order book"},
    "auto": {"compare": "yoy", "season": "festive demand (Oct-Nov) and model launches move volumes between quarters",
             "kpis": r"volumes?|units|ebitda margin|realisation|realization|market share|exports?|ev\b"},
    "cement": {"compare": "yoy", "season": "the July-September monsoon quarter is always the weakest for cement demand",
               "kpis": r"volumes?|ebitda per tonne|ebitda/t|per tonne|realisation|realization|capacity utili[sz]ation|"
                       r"fuel cost|power and fuel"},
    "metal": {"compare": "yoy", "season": None,
              "kpis": r"ebitda per tonne|ebitda/t|per tonne|deliveries|sales volume|production|realisation|realization|"
                      r"net debt|coking coal|lme"},
    "oil_gas": {"compare": "yoy", "season": None,
                "kpis": r"\bgrm\b|gross refining margin|marketing margin|throughput|crude|production|realisation|"
                        r"o2c|digital services|retail|arpu|jio"},
    "power": {"compare": "yoy", "season": "summer (April-June) lifts power demand; the monsoon quarter is softer",
              "kpis": r"\bplf\b|plant load factor|generation|capacity|commissioned|regulated equity|units sold"},
    "fmcg": {"compare": "yoy", "season": "rural demand follows the harvest and monsoon; festive timing shifts quarters",
             "kpis": r"volume growth|underlying volume|\buvg\b|gross margin|ebitda margin|rural|urban|price growth"},
    "pharma": {"compare": "yoy", "season": None,
               "kpis": r"us (sales|business|generics)|north america|india (formulations|business)|r&d|ebitda margin|"
                       r"usfda|launches|specialty"},
    "hospital": {"compare": "yoy", "season": None,
                 "kpis": r"occupancy|\barpob\b|average revenue per (occupied )?bed|beds|pharmacy|digital"},
    "telecom": {"compare": "qoq", "season": None,
                "kpis": r"\barpu\b|average revenue per user|subscribers?|customer base|churn|data (usage|traffic)|"
                        r"ebitda margin|capex"},
    "retail": {"compare": "yoy", "season": "the October-December festive and wedding quarter is the biggest",
               "kpis": r"same[- ]store|\bsssg\b|like[- ]for[- ]like|store (count|additions)|stores|gmv|\bnov\b|"
                      r"orders|ebitda margin|footfall"},
    "realty": {"compare": "yoy", "season": "launches and bookings are lumpy: one big launch can swing a quarter",
               "kpis": r"pre[- ]?sales|bookings|sales bookings|collections|launches|net debt|cash flow"},
    "capital_goods": {"compare": "yoy", "season": "project execution peaks in January-March (year-end)",
                      "kpis": r"order (inflow|book|intake)|orders received|execution|ebitda margin|working capital"},
}
DEFAULT = {"compare": "yoy", "season": None, "kpis": r"ebitda margin|volume|guidance|order"}


def profile(symbol: str) -> dict:
    return {"group": GROUP_OF.get(symbol, sector_of(symbol).lower()), **PROFILES.get(GROUP_OF.get(symbol), DEFAULT)}


def kpi_lines(text: str, symbol: str, limit: int = 8) -> list[str]:
    """Lines from the filing / press release that state the sector's key numbers."""
    pattern = profile(symbol)["kpis"]
    keep = []
    for line in text.splitlines():
        s = " ".join(line.split())
        if 8 < len(s) < 220 and re.search(pattern, s, re.I) and re.search(r"\d", s):
            if s not in keep:
                keep.append(s)
        if len(keep) >= limit:
            break
    return keep


def score(figures: dict, symbol: str | None) -> dict:
    """Read the quarter the way the sector is read: seasonal businesses on YoY only (a QoQ drop
    is often just the season), IT/telecom with the sequential trend counting as much as YoY."""
    p = profile(symbol) if symbol else {**DEFAULT, "group": "unknown"}
    rev, pat = figures.get("revenue", {}), figures.get("profit", {})
    total, notes = 0, []
    for name, row, weight in (("Profit", pat, 2), ("Revenue", rev, 1)):
        yoy, qoq = row.get("yoy_pct"), row.get("qoq_pct")
        if yoy is None:
            continue
        notes.append(f"{name} {yoy:+.1f}% YoY, {qoq:+.1f}% QoQ" if qoq is not None else f"{name} {yoy:+.1f}% YoY")
        lead = qoq if p["compare"] == "qoq" and qoq is not None else yoy
        cuts = (4, 1.5, -3) if p["compare"] == "qoq" else (15, 5, -10)  # sequential growth runs smaller
        if lead >= cuts[0]:
            total += 2 * weight
        elif lead >= cuts[1]:
            total += weight
        elif lead <= cuts[2]:
            total -= 2 * weight
        elif lead < 0:
            total -= weight
        if p["compare"] == "yoy" and not p["season"] and qoq is not None and qoq < -5:
            total -= weight  # a sequential slide matters only where there is no season to explain it
    view = "strong" if total >= 4 else "good" if total >= 2 else "weak" if total <= -3 else "mixed"
    how = {"qoq": "read on the sequential (QoQ) trend, as this sector is tracked",
           "yoy": "read against the same quarter last year"}[p["compare"]]
    if p["season"]:
        how += f"; seasonal business: {p['season']}"
    return {"score": total, "view": view, "notes": notes, "sector": p["group"], "how_read": how}
