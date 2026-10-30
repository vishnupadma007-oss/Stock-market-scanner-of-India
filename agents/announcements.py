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
import os
import re
import subprocess
import sys
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import quote

import requests

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
    ("GUIDANCE", r"press release|investor presentation|business update|operational update|shareholders?'? letter"),
]
ROUTINE = r"newspaper|trading window|loss of share|duplicate share|certificate under|" \
          r"closure of trading|shareholders meeting|record date|analysts/institutional"


def classify(row: dict) -> str | None:
    text = f"{row.get('desc', '')} {row.get('attchmntText', '')}".lower()
    if re.search(r"outcome of board meeting", text) and "financial result" in text:
        return "RESULTS"
    if re.search(r"outcome of board meeting", text):
        # Some companies title results only "Outcome of board meeting dated ..." (ETERNAL, 21 Oct):
        # the watcher opens the PDF to see whether it holds results.
        return "BOARD"
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


_LEAD = r"^\s*(\d+\s*[.)]?\s+|[a-z]\)\s*|\(?[ivxl]+\)?[.)]?\s+)?"  # serial: "1 ", "a)", "(iv)", "IX "
# Companies name the same rows differently; the first match in the filing wins (usually the
# first results table on the first pages).
ROWS = {
    "revenue": _LEAD + r"((total )?revenue from operations|(total )?income from operations|"
                       r"(net )?sales\s*/?\s*income from operations|net sales|interest earned)",
    "profit": _LEAD + r"(net )?profit\s*/?\s*(\(?loss\)?\s*)?(from ordinary activities\s*)?(after (tax|taxation)|"
                      r"for the (period|quarter|year)|attributable to (the )?(owners|equity|shareholders))",
}


OCR_FIXES = str.maketrans({"o": "0", "O": "0", "D": "0", "l": "1", "I": "1", "|": "1", "i": "1",
                           "S": "5", "s": "5", "B": "8", "g": "9", "Z": "2", "z": "2"})


def clean_ocr_numbers(line: str) -> str:
    """Fix typical OCR digit errors inside number-like tokens: '24, 138' -> '24,138', '1o5' -> '105'.
    Only tokens that are mostly digits are touched, so labels stay as they are."""
    line = re.sub(r"[\[\]|_{}‘’“”;•·*]", lambda m: ")" if m.group() == "}" else " ", line)  # table lines, bullets, OCR noise
    line = re.sub(r"(?<=[A-Za-z])(\(\d{1,3}\)\)?)+", " ", line)  # row references glued to the label: "TAX(10)(71)"
    line = re.sub(r"(\d),\s+(\d{3})\b", r"\1,\2", line)
    line = re.sub(r"(\d,\d{2})\s(\d)\b(?![,.]\d)", r"\1\2", line)  # "20,21 1" -> "20,211"
    line = re.sub(r"(\d,\d)\s(\d{2})\b(?![,.]\d)", r"\1\2", line)
    out = []
    for tok in line.split(" "):
        core = tok.strip("()-")
        if len(core) >= 2 and sum(ch.isdigit() for ch in core) >= 0.6 * len(core):
            tok = tok.translate(OCR_FIXES)
        out.append(tok)
    return " ".join(out)


def plausible(key: str, nums: list[float]) -> bool:
    """Reject misread rows: a quarter's revenue is never 3x its neighbours; profit (same sign)
    rarely 10x. Catches OCR errors like '24,138 / 2,021 / 1'."""
    vals = [abs(n) for n in nums]
    if min(vals) == 0:
        return key == "profit"
    if key == "revenue":
        return max(vals) / min(vals) <= 3
    same_sign = all(n > 0 for n in nums) or all(n < 0 for n in nums)
    return not same_sign or max(vals) / min(vals) <= 10


def change_pct(cur: float, base: float) -> float | None:
    """% change measured against the size of the base, so a loss turning into a profit reads as a
    rise (-264 -> +169 is +164%, not -164%)."""
    return round((cur - base) / abs(base) * 100.0, 1) if base else None


def _row(key: str, lines: list[str], start: int = 0) -> tuple[int, dict] | None:
    for i in range(start, len(lines)):
        if re.search(ROWS[key], lines[i], re.I):
            nums = _numbers(lines[i])
            if len(nums) >= 3 and plausible(key, nums[:3]):
                cur, prev_q, prev_y = nums[:3]
                return i, {"quarter": cur, "prev_quarter": prev_q, "year_ago": prev_y,
                           "qoq_pct": change_pct(cur, prev_q), "yoy_pct": change_pct(cur, prev_y)}
    return None


def _extract_table(lines: list[str], start: int = 0) -> dict:
    out = {}
    rev = _row("revenue", lines, start)
    if rev:
        out["revenue"] = rev[1]
    prof = _row("profit", lines, rev[0] + 1 if rev else start) or (_row("profit", lines, start) if rev else None)
    if prof:
        out["profit"] = prof[1]
    return out


def figures_from_text(text: str) -> dict:
    """First results table in the filing (preferring Consolidated over Standalone when both
    exist and Consolidated has complete revenue + profit): current quarter, previous quarter
    and the same quarter last year, with QoQ and YoY growth. Profit is read from the same table
    as revenue (the first profit row after the revenue row), so a summary table elsewhere is
    not mixed in."""
    lines = [clean_ocr_numbers(l) if re.search(r"\d", l) else l for l in text.splitlines()]
    # Prefer Consolidated financial results when a filing contains Standalone first and Consolidated second
    for idx, line in enumerate(lines):
        if re.search(r"\bconsolidated\b.*(financial results|statement of)", line, re.I):
            cons = _extract_table(lines, idx)
            if "revenue" in cons and "profit" in cons:
                return cons
            break
    return _extract_table(lines, 0)


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


def _download(url: str) -> bytes:
    resp = get_nse_session().get(url, timeout=90)
    resp.raise_for_status()
    return resp.content


def _text_layer(pdf: bytes) -> str:
    with tempfile.NamedTemporaryFile(suffix=".pdf") as f:
        f.write(pdf)
        f.flush()
        try:
            return subprocess.run(["pdftotext", "-layout", f.name, "-"], capture_output=True,
                                  text=True, timeout=120).stdout
        except FileNotFoundError:  # no poppler: fall back to pypdf
            import pypdf
            return "\n".join(p.extract_text() or "" for p in pypdf.PdfReader(io.BytesIO(pdf)).pages)


def ocr_text(pdf: bytes, pages: int = 6, dpi: int = 300) -> str:
    """Read scanned pages with Tesseract OCR (results tables are on the first few pages)."""
    with tempfile.TemporaryDirectory() as d:
        src = Path(d) / "in.pdf"
        src.write_bytes(pdf)
        subprocess.run(["pdftoppm", "-r", str(dpi), "-gray", "-f", "1", "-l", str(pages), str(src), str(Path(d) / "p")],
                       check=True, timeout=300, capture_output=True)
        # All pages at once; the shared slots keep the whole program to one OCR per CPU core.
        with ThreadPoolExecutor(max_workers=pages) as pool:
            return "\n".join(pool.map(_ocr_page, sorted(Path(d).glob("p*.pgm"))))


# Tesseract is CPU-bound: one single-threaded OCR per core, shared by every reader thread
# (the watcher's 10 results readers, the history rebuild's workers), so more pages queue instead
# of slowing each other down. A bigger machine gets more slots automatically.
OCR_SLOTS = threading.BoundedSemaphore(max(2, os.cpu_count() or 4))


def _ocr_page(img: Path) -> str:
    with OCR_SLOTS:
        # psm 6: one uniform block, keeps table rows on one line; keep the spaces between columns
        return subprocess.run(["tesseract", str(img), "-", "--psm", "6", "-c", "preserve_interword_spaces=1"],
                              capture_output=True, text=True, timeout=120,
                              env={**os.environ, "OMP_THREAD_LIMIT": "1"}).stdout


def pdf_text(url: str, ocr: bool = True) -> str:
    """Text of a filing. Scanned filings (no text layer, or a garbled one where the results rows
    cannot be read) are read with OCR instead."""
    pdf = _download(url)
    text = _text_layer(pdf)
    if not ocr or len(figures_from_text(text)) == 2:
        return text
    try:
        scanned = ocr_text(pdf)
    except (FileNotFoundError, subprocess.SubprocessError):
        return text  # no OCR tools installed
    return scanned if len(figures_from_text(scanned)) > len(figures_from_text(text)) else text + "\n" + scanned


RESULTS_TEXT = r"financial results|revenue from operations|statement of profit and loss"


def results_summary(url: str, symbol: str | None = None) -> dict:
    from .sector_results import kpi_lines
    text = pdf_text(url)
    figures = figures_from_text(text)
    if not figures and symbol and text.strip():
        # Our parser found no table (scanned or unusual layout): ask the AI helper, if a key is set (agents/ai_helper.py).
        from . import ai_helper
        from .config import load_config
        try:
            cfg = load_config()
            if ai_helper.available(cfg):
                figures = ai_helper.results_figures(text, symbol, cfg)
        except Exception:
            pass
    return {"figures": figures, "highlights": highlights(text),
            "kpis": kpi_lines(text, symbol) if symbol else [],
            "is_results": bool(re.search(RESULTS_TEXT, text, re.I))}


def score_results(figures: dict, symbol: str | None = None) -> dict:
    """First read of the numbers, the way the company's sector is read (see sector_results):
    +ve = strong quarter, -ve = weak. Markets react to results versus expectations, so this is
    only a first read; Claude checks expectations, the sector KPIs and the price."""
    from .sector_results import score
    return score(figures, symbol)


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
                    figures = results_summary(item["pdf"], item["symbol"])
                    item.update(figures, read=score_results(figures["figures"], item["symbol"]))
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
