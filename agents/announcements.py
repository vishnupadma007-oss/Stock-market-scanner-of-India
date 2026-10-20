"""NSE Announcements agent: reads NSE's live corporate-filings feed and pulls the numbers out
of results filings.

Every listed company must file results, ratings, orders, mergers, regulatory actions and
management changes with NSE within minutes, so this feed is the earliest reliable source of
company news. It is read from NSE directly (not INDmoney), about once a minute.

    python -m agents.announcements recent TECHM        # today's material filings for a stock
    python -m agents.announcements results <pdf-url>   # key figures + highlights of a results filing
    python -m agents.announcements overnight           # F&O filings since the last session's close
"""
import io
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta

import requests
from urllib.parse import quote

FEED = "https://www.nseindia.com/api/corporate-announcements?index=equities"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.nseindia.com/",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
}

_session = None


def get_nse_session() -> requests.Session:
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers.update(HEADERS)
        try:
            _session.get("https://www.nseindia.com", timeout=10)
        except Exception:
            pass
    return _session


# NSE filing category ("desc") or text -> our category. Order matters: first match wins.
CATEGORIES = [
    ("RESULTS", r"financial result|outcome of board meeting.*result|integrated filing.*financ"),
    ("RATING", r"credit rating"),
    ("ORDER", r"bagging|receiving of orders|award.*(order|contract)|order win|contract"),
    ("DEAL", r"acquisition|amalgamation|merger|scheme of arrangement|demerger|buy ?back|"
             r"preferential issue|qualified institutions placement|\bqip\b|fund raising"),
    ("REGULATORY", r"action\(s\) (taken|initiated)|order(s)? passed|penalty|show cause|"
                   r"search|raid|litigation|dispute|insolvency"),
    ("MANAGEMENT", r"resignation|cessation|appointment of (md|ceo|managing|chief)"),
    ("GUIDANCE", r"press release|investor presentation|business update|operational update"),
]
ROUTINE = r"newspaper|trading window|loss of share|duplicate share|certificate under|" \
          r"closure of trading|shareholders meeting|record date|analysts/institutional"


def classify(row: dict) -> str | None:
    text = f"{row.get('desc', '')} {row.get('attchmntText', '')}".lower()
    if re.search(r"outcome of board meeting", text) and "financial result" in text:
        return "RESULTS"
    if re.search(ROUTINE, text):
        return None
    for name, pattern in CATEGORIES:
        if re.search(pattern, text):
            return name
    return None


def fetch_feed(symbol: str | None = None, start=None, end=None) -> list[dict]:
    """All filings (optionally for one symbol) between two dates; today's by default."""
    start, end = start or datetime.now().date(), end or datetime.now().date()
    url = FEED + f"&from_date={start:%d-%m-%Y}&to_date={end:%d-%m-%Y}" + (f"&symbol={quote(symbol)}" if symbol else "")
    session = get_nse_session()
    try:
        resp = session.get(url, timeout=20)
        if resp.status_code in (401, 403):
            # Refresh session
            session.get("https://www.nseindia.com", timeout=10)
            resp = session.get(url, timeout=20)
        resp.raise_for_status()
        rows = resp.json()
        return rows if isinstance(rows, list) else []
    except Exception:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        rows = resp.json()
        return rows if isinstance(rows, list) else []


def material(rows: list[dict], universe: set[str], since: str = "") -> list[dict]:
    """Material filings for our stocks, newest last. `since` is a 'YYYY-MM-DD HH:MM:SS' cut-off."""
    out = []
    for r in rows:
        cat = classify(r)
        if cat and r.get("symbol") in universe and r.get("sort_date", "") > since:
            out.append({"seq_id": r["seq_id"], "time": r["sort_date"], "symbol": r["symbol"],
                        "category": cat, "subject": r.get("desc", ""),
                        "text": r.get("attchmntText", "")[:300], "pdf": r.get("attchmntFile", "")})
    return sorted(out, key=lambda x: x["time"])


# ---------------------------------------------------------------- results figures

_NUM = r"\(?-?[\d,]+(?:\.\d+)?\)?"


def _numbers(line: str) -> list[float]:
    """The figures after a row's label. Drops serial numbers and formulas like '(9 - 10)'."""
    line = re.sub(r"\(\s*\d+\s*[-+]\s*\d+(\s*[-+]\s*\d+)*\s*\)", " ", line)
    label_end = re.search(r"[A-Za-z][A-Za-z\s/()&,.-]*[A-Za-z)]", line)
    tokens = line[label_end.end() if label_end else 0:].split()
    # Scanned filings can misread digits ("4,2so.n"): only trust a row whose first three
    # figures (quarter, previous quarter, year-ago quarter) all read as clean numbers.
    if len(tokens) < 3 or not all(re.fullmatch(_NUM, t) for t in tokens[:3]):
        return []
    vals = []
    for tok in tokens[:3]:
        neg = tok.startswith("(") or tok.startswith("-")
        try:
            vals.append(float(tok.strip("()-").replace(",", "")) * (-1 if neg else 1))
        except ValueError:
            return []
    return vals


ROWS = {
    "revenue": r"^\s*(\d+\s+|[a-z]\)\s*|\(?[ivx]+\)\s*)?(total )?revenue from operations|"
               r"^\s*(\d+\s+)?interest earned",
    "profit": r"^\s*(\d+\s+|[a-z]\)\s*|\(?[ivx]+\)\s*)?(net )?profit\s*/?\s*(\(loss\)\s*)?"
              r"(after tax|for the (period|quarter))",
}


def figures_from_text(text: str) -> dict:
    """First results table in the filing (usually consolidated): current quarter, previous
    quarter and the same quarter last year, with QoQ and YoY growth."""
    out = {}
    for key, pattern in ROWS.items():
        for line in text.splitlines():
            if re.search(pattern, line, re.I):
                nums = _numbers(line)
                if len(nums) >= 3:
                    cur, prev_q, prev_y = nums[:3]
                    out[key] = {
                        "quarter": cur,
                        "prev_quarter": prev_q,
                        "year_ago": prev_y,
                        "qoq_pct": round((cur / prev_q - 1.0) * 100.0, 1) if prev_q and prev_q != 0 else None,
                        "yoy_pct": round((cur / prev_y - 1.0) * 100.0, 1) if prev_y and prev_y != 0 else None,
                    }
                    break
    return out


def highlights(text: str, limit: int = 12) -> list[str]:
    """Lines from the press release that state growth ('up 23% YoY', 'declined', 'margin')."""
    keep = []
    for line in text.splitlines():
        s = " ".join(line.split())
        if 15 < len(s) < 200 and "%" in s and re.search(
                r"\b(yoy|qoq|y-o-y|q-o-q|year[- ]on[- ]year|growth|grew|up|down|declin\w*|margin|guidance)\b",
                s, re.I):
            keep.append(s)
        if len(keep) >= limit:
            break
    return keep


def pdf_text(url: str) -> str:
    session = get_nse_session()
    resp = session.get(url, timeout=90)
    resp.raise_for_status()
    with tempfile.NamedTemporaryFile(suffix=".pdf") as f:
        f.write(resp.content)
        f.flush()
        try:
            return subprocess.run(["pdftotext", "-layout", f.name, "-"], capture_output=True,
                                  text=True, timeout=120).stdout
        except FileNotFoundError:  # no poppler: fall back to pypdf
            import pypdf
            return "\n".join(p.extract_text() or "" for p in pypdf.PdfReader(io.BytesIO(resp.content)).pages)


def results_summary(url: str) -> dict:
    text = pdf_text(url)
    return {"figures": figures_from_text(text), "highlights": highlights(text)}


def score_results(figures: dict) -> dict:
    """Rough read of the numbers alone: +ve = strong quarter, -ve = weak. Markets react to results
    versus expectations, so this is only a first read; Claude checks expectations and the price."""
    rev, pat = figures.get("revenue", {}), figures.get("profit", {})
    score, notes = 0, []
    for name, row, weight in (("Profit", pat, 2), ("Revenue", rev, 1)):
        yoy, qoq = row.get("yoy_pct"), row.get("qoq_pct")
        if yoy is None:
            continue
        notes.append(f"{name} {yoy:+.1f}% YoY, {qoq:+.1f}% QoQ" if qoq is not None else f"{name} {yoy:+.1f}% YoY")
        if yoy >= 15:
            score += 2 * weight
        elif yoy >= 5:
            score += weight
        elif yoy <= -10:
            score -= 2 * weight
        elif yoy < 0:
            score -= weight
        if qoq is not None and qoq < -5:
            score -= weight
    view = "strong" if score >= 4 else "good" if score >= 2 else "weak" if score <= -3 else "mixed"
    return {"score": score, "view": view, "notes": notes}


def to_intel(item: dict) -> dict:
    """A material filing as an intelligence-log item for the Data Analyzer."""
    from . import intel
    text = f"{item['subject']} {item['text']}".lower()
    cat = item["category"]
    if cat == "RESULTS":
        view = (item.get("read") or {}).get("view", "mixed")
        mood, impact = {"strong": 1.0, "good": 0.5, "mixed": 0.0, "weak": -1.0}.get(view, 0.0), 3
    elif cat == "RATING":
        mood = 0.7 if re.search(r"upgrad|positive", text) else -0.7 if re.search(r"downgrad|negative|watch", text) else 0.0
        impact = 2
    elif cat == "ORDER":
        mood, impact = 0.6, 2
    elif cat == "REGULATORY":
        mood, impact = -0.7, 3
    elif cat == "MANAGEMENT":
        mood, impact = (-0.5, 2) if re.search(r"\b(ceo|md|managing director|cfo|chief)\b", text) else (-0.2, 1)
    else:  # DEAL, GUIDANCE: direction unclear from the filing title alone
        mood, impact = intel.tone(text), 2
    # A results filing read later (first read failed) gets its own id, so the real view is logged.
    view_tag = f"-{item['read']['view']}" if cat == "RESULTS" and (item.get("read") or {}).get("view") not in (None, "unread") else ""
    return intel.make_item(id=f"filing-{item['seq_id']}{view_tag}", time=item["time"], source="NSE filing", kind="filing",
                           symbols=[item["symbol"]], category=cat, sentiment=mood, impact=impact,
                           headline=f"{item['symbol']} {cat.lower()}: {item['text'][:200]}", url=item["pdf"])


def main(argv: list[str]) -> None:
    import json
    cmd = argv[1] if len(argv) > 1 else ""
    if cmd == "recent":
        today = datetime.now().strftime("%Y-%m-%d")
        for item in material(fetch_feed(argv[2]), {argv[2]}, since=today):
            print(json.dumps(item))
    elif cmd == "overnight":
        from .config import load_config
        from .holidays import previous_trading_day
        today = datetime.now().date()
        prev = previous_trading_day(today - timedelta(days=1))
        universe = set(load_config()["universe"])
        for item in material(fetch_feed(start=prev, end=today), universe, since=f"{prev} 15:30:00"):
            if item["category"] == "RESULTS" and item["pdf"].endswith(".pdf"):
                try:
                    figures = results_summary(item["pdf"])
                    item.update(figures, read=score_results(figures["figures"]))
                except Exception as e:
                    item["read"] = {"view": "unread", "notes": [type(e).__name__]}
            print(json.dumps(item))
    elif cmd == "results":
        summary = results_summary(argv[2])
        summary["read"] = score_results(summary["figures"])
        print(json.dumps(summary, indent=1))
    else:
        print(__doc__)


if __name__ == "__main__":
    main(sys.argv)
