"""Shared intelligence log: every information agent (NSE filings, concalls, news) writes items
here in one format, and the Data Analyzer reads them.

Item: {id, time, source, kind, scope, symbols, sectors, category, headline, sentiment, impact, url}
  scope     "stock" | "sector" | "market" (India) | "global"
  sentiment -1 (bad) .. +1 (good) for the stocks/sectors/market it is about
  impact    1 minor, 2 notable, 3 major

Tone is read with a finance word list: quick and free, but it misses sarcasm and context.
The analyzer only acts on agreement between several items or on one major item, and Claude
reviews strong forecasts before any trade.
"""
import json
import re
from datetime import datetime
from pathlib import Path

DIR = Path(__file__).resolve().parent.parent / "journal" / "intel"

# How headlines name our companies (symbol -> names used in the press).
ALIASES = {
    "RELIANCE": ["reliance industries", "ril", "reliance jio", "jio platforms", "reliance retail"],
    "HDFCBANK": ["hdfc bank"], "ICICIBANK": ["icici bank"], "INFY": ["infosys"], "TCS": ["tcs", "tata consultancy"],
    "SBIN": ["sbi", "state bank of india"], "AXISBANK": ["axis bank"], "KOTAKBANK": ["kotak mahindra bank", "kotak bank"],
    "BHARTIARTL": ["bharti airtel", "airtel"], "LT": ["larsen & toubro", "larsen and toubro", "l&t"],
    "ITC": ["itc"], "HINDUNILVR": ["hindustan unilever", "hul"], "BAJFINANCE": ["bajaj finance"],
    "BAJAJFINSV": ["bajaj finserv"], "MARUTI": ["maruti suzuki", "maruti"], "M&M": ["mahindra & mahindra", "mahindra and mahindra", "m&m"],
    "SUNPHARMA": ["sun pharma", "sun pharmaceutical"], "TITAN": ["titan company", "titan"],
    "ULTRACEMCO": ["ultratech cement", "ultratech"], "WIPRO": ["wipro"], "HCLTECH": ["hcl tech", "hcltech", "hcl technologies"],
    "TECHM": ["tech mahindra", "techm"], "PERSISTENT": ["persistent systems"], "COFORGE": ["coforge"],
    "MPHASIS": ["mphasis"], "ADANIENT": ["adani enterprises"], "ADANIPORTS": ["adani ports"],
    "TATASTEEL": ["tata steel"], "JSWSTEEL": ["jsw steel"], "HINDALCO": ["hindalco", "novelis"], "VEDL": ["vedanta"],
    "SAIL": ["sail", "steel authority"], "NMDC": ["nmdc"], "NATIONALUM": ["nalco", "national aluminium"],
    "ONGC": ["ongc", "oil and natural gas"], "NTPC": ["ntpc"], "POWERGRID": ["power grid"], "COALINDIA": ["coal india"],
    "BPCL": ["bpcl", "bharat petroleum"], "IOC": ["indian oil", "ioc"], "GAIL": ["gail"], "TATAPOWER": ["tata power"],
    "DLF": ["dlf"], "INDUSINDBK": ["indusind bank"], "BANKBARODA": ["bank of baroda"], "PNB": ["punjab national bank", "pnb"],
    "CANBK": ["canara bank"], "IDFCFIRSTB": ["idfc first bank"], "FEDERALBNK": ["federal bank"], "AUBANK": ["au small finance", "au bank"],
    "SHRIRAMFIN": ["shriram finance"], "CHOLAFIN": ["cholamandalam"], "MUTHOOTFIN": ["muthoot finance"],
    "RECLTD": ["rec ltd", "rec limited"], "PFC": ["power finance corporation", "pfc"], "BEL": ["bharat electronics", "bel"],
    "HAL": ["hindustan aeronautics", "hal"], "BHEL": ["bhel", "bharat heavy electricals"], "TRENT": ["trent", "zudio"],
    "ETERNAL": ["eternal", "zomato", "blinkit"], "PAYTM": ["paytm", "one97"], "POLICYBZR": ["policybazaar", "pb fintech"],
    "DIXON": ["dixon technologies", "dixon"], "CIPLA": ["cipla"], "DRREDDY": ["dr reddy", "dr. reddy"], "DIVISLAB": ["divi's", "divis lab"],
    "LUPIN": ["lupin"], "APOLLOHOSP": ["apollo hospitals"], "EICHERMOT": ["eicher motors", "royal enfield"],
    "HEROMOTOCO": ["hero motocorp"], "BAJAJ-AUTO": ["bajaj auto"], "TVSMOTOR": ["tvs motor"], "ASIANPAINT": ["asian paints"],
    "NESTLEIND": ["nestle india"], "BRITANNIA": ["britannia"], "GRASIM": ["grasim"],
}

SECTOR_WORDS = {
    "IT": r"\bit (stocks|sector|services|companies)\b|\binfotech\b|\btech stocks\b|h-1b|outsourcing",
    "Bank": r"\bbank(s|ing)? (stocks|sector)\b|\bnbfcs?\b|\blenders?\b|private banks|bank nifty",
    "PSU Bank": r"\bpsu banks?\b|public sector banks",
    "Auto": r"\bauto (stocks|sector|sales)\b|\bautomakers?\b|\bev\b|car sales|two-wheeler",
    "Pharma": r"\bpharma(ceutical)?s?\b|\bdrugmakers?\b|usfda|\bfda\b",
    "Metal": r"\bmetal (stocks|prices)\b|\bsteel\b|\baluminium\b|\bcopper\b|\bzinc\b|iron ore",
    "Energy": r"\boil marketing\b|\bomcs?\b|\brefiner(s|ies)\b|\bpower (stocks|sector|demand)\b|\bcrude\b",
    "FMCG": r"\bfmcg\b|consumer (goods|staples|demand)|rural demand",
    "Realty": r"\brealty\b|real estate|housing sales",
}

MARKET_WORDS = r"\bnifty\b|\bsensex\b|dalal street|indian (stocks|shares|equities|markets?)|\bfiis?\b|\bfpis?\b|" \
               r"\brbi\b|repo rate|\brupee\b|india('s)? (gdp|inflation|cpi|wpi)|\bsebi\b|budget"
GLOBAL_WORDS = r"\bfed\b|federal reserve|wall street|\bopec\b|\bbrent\b|crude oil|sanctions?|\bwar\b|ceasefire|" \
               r"tariffs?|china|middle east|\biran\b|\bisrael\b|russia|ukraine|treasury yields?|dollar index|recession"
# A global story only counts if it is about markets or the economy ("Cold War missile base" is not).
FINANCE_WORDS = r"stocks?|shares|markets?|\boil\b|crude|brent|econom\w+|rates?|yields?|trade|tariffs?|" \
                r"dollar|gold|inflation|prices?|investors?|nasdaq|dow|s&p|nikkei|exports?|imports?|supply|demand"

POSITIVE = r"\b(surge[sd]?|soar(s|ed)?|jump(s|ed)?|rall(y|ies|ied)|gain(s|ed)?|rise[sn]?|rose|climb(s|ed)?|" \
           r"record high|beat(s)?|outperform\w*|upgrade[sd]?|strong|robust|boost(s|ed)?|win(s)?|bag(s|ged)?|" \
           r"order(s)? worth|approval|approved|expan\w+|profit (up|rises|jumps)|buy rating|ceasefire|eases?|cut(s)? rates?|" \
           r"growth|grows?|grew|improv\w+)\b"
NEGATIVE = r"\b(plunge[sd]?|slump(s|ed)?|crash(es|ed)?|tumble[sd]?|sink(s)?|sank|fall(s|en)?|fell|drop(s|ped)?|" \
           r"slide[sd]?|decline[sd]?|miss(es|ed)?|downgrade[sd]?|weak|warn(s|ing)?|probe|raid(s|ed)?|penalt(y|ies)|" \
           r"fraud|ban(s|ned)?|default(s|ed)?|resign(s|ed|ation)?|loss(es)?|cut(s)? (guidance|forecast|target)|" \
           r"sell rating|war|attack(s|ed)?|sanction(s|ed)?|tariff hike|slowdown|recession|outflows?|hike(s|d)? rates?)\b"
MAJOR = r"\b(fraud|raid|probe|default|war|attack|sanction|crash|plunge|record high|rate (cut|hike)|ban)\w*"


NEGATORS = r"\b(not|no|never|without|unlikely|neither|nor|hardly|fail(s|ed)? to|didn't|doesn't|don't|won't|isn't|wasn't)\b"
# Loughran-McDonald style uncertainty / weak-modal words: hedged good news counts for less.
UNCERTAIN = r"\b(may|might|could|uncertain\w*|volatil\w+|unclear|subject to|risks?|challeng\w+|headwinds?|" \
            r"cautious\w*|approximately|depend\w*|tentative\w*)\b"


def _negated(text: str, start: int) -> bool:
    """A negation word in the three words before a match flips it ("does not expect growth")."""
    before = text[:start].split()[-3:]
    return bool(re.search(NEGATORS, " ".join(before), re.I))


def tone(text: str) -> float:
    """-1..+1 from finance word lists, with negation handling and a discount for hedged language."""
    pos = neg = 0
    for pattern, sign in ((POSITIVE, 1), (NEGATIVE, -1)):
        for m in re.finditer(pattern, text, re.I):
            if (sign > 0) != _negated(text, m.start()):
                pos += 1
            else:
                neg += 1
    if pos == neg:
        return 0.0
    score = (pos - neg) / (pos + neg)
    hedges = len(re.findall(UNCERTAIN, text, re.I))
    if score > 0 and hedges:
        score *= max(0.4, 1 - 0.2 * hedges)  # good news full of "may" and "could" counts for less
    return round(score, 2)


def symbols_in(text: str) -> list[str]:
    t = f" {text.lower()} "
    return sorted(s for s, names in ALIASES.items()
                  if any(re.search(rf"(?<![a-z0-9]){re.escape(n)}(?![a-z0-9])", t) for n in names))


def sectors_in(text: str) -> list[str]:
    return sorted(s for s, pattern in SECTOR_WORDS.items() if re.search(pattern, text, re.I))


def make_item(*, id: str, time: str, source: str, kind: str, headline: str, url: str = "",
              symbols: list[str] | None = None, category: str = "", sentiment: float | None = None,
              impact: int | None = None) -> dict:
    symbols = symbols if symbols is not None else symbols_in(headline)
    sectors = sectors_in(headline)
    # Sector tags are kept whatever the scope, so "Brent jumps" counts for global mood and energy stocks.
    scope = "stock" if symbols else \
        "global" if re.search(GLOBAL_WORDS, headline, re.I) and re.search(FINANCE_WORDS, headline, re.I) else \
        "market" if re.search(MARKET_WORDS, headline, re.I) else "sector" if sectors else ""
    if impact is None:
        impact = 3 if re.search(MAJOR, headline, re.I) else 2 if scope in ("global", "market") else 1
    return {"id": id, "time": time, "source": source, "kind": kind, "scope": scope, "symbols": symbols,
            "sectors": sectors, "category": category, "headline": headline[:300],
            "sentiment": tone(headline) if sentiment is None else sentiment, "impact": impact, "url": url}


def path_for(day: str) -> Path:
    return DIR / f"{day}.jsonl"


def append(items: list[dict], seen: set[str]) -> list[dict]:
    """Add new items (skipping ids already seen and items about nothing we track)."""
    new = [i for i in items if i["id"] not in seen and i["scope"]]
    if new:
        DIR.mkdir(parents=True, exist_ok=True)
        with open(path_for(datetime.now().date().isoformat()), "a") as f:
            for item in new:
                seen.add(item["id"])
                f.write(json.dumps(item) + "\n")
    return new


def load(*days: str) -> list[dict]:
    items = []
    for day in days:
        p = path_for(day)
        if p.exists():
            items += [json.loads(line) for line in p.read_text().splitlines() if line.strip()]
    return items
