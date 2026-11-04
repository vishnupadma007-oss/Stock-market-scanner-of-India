"""Concall agent: earnings calls, analyst and investor meets of our F&O companies.

From NSE's filings feed it tracks scheduled meets (so we know when management will talk) and,
when a transcript is filed, reads management's commentary: guidance, demand, margins, orders.
The tone of those lines goes to the intelligence log for the Data Analyzer.
"""
import re

from . import intel
from .announcements import pdf_text

MEET = r"analysts?/institutional investor meet|con\.? ?call|conference call|earnings call|investor meet"
TRANSCRIPT = r"transcript"
GUIDANCE_WORDS = r"\b(guidance|outlook|expect\w*|going forward|next (quarter|year)|fy2\d|demand|margin\w*|" \
                 r"order book|pipeline|deal wins?|headwinds?|tailwinds?|visibility|growth)\b"


def is_meet(row: dict) -> bool:
    return bool(re.search(MEET, f"{row.get('desc', '')} {row.get('attchmntText', '')}", re.I))


def commentary(text: str, limit: int = 25) -> list[str]:
    """Management's forward-looking sentences from a transcript."""
    sentences = re.split(r"(?<=[.!?])\s+", " ".join(text.split()))
    picked = [s for s in sentences if 40 < len(s) < 400 and re.search(GUIDANCE_WORDS, s, re.I)]
    return picked[:limit]


def items_from_rows(rows: list[dict], universe: set[str], read_transcripts: bool = True) -> list[dict]:
    out = []
    for r in rows:
        sym = r.get("symbol")
        if sym not in universe or not is_meet(r):
            continue
        text = r.get("attchmntText", "")
        base = dict(id=f"concall-{r['seq_id']}", time=r.get("sort_date", ""), source="NSE concall",
                    kind="concall", symbols=[sym], url=r.get("attchmntFile", ""))
        if re.search(TRANSCRIPT, text, re.I) and read_transcripts and base["url"].endswith(".pdf"):
            try:
                lines = commentary(pdf_text(base["url"]))
            except Exception:
                lines = []
            mood = intel.tone(" ".join(lines)) if lines else 0.0
            summary = " | ".join(lines[:3]) if lines else text
            out.append(intel.make_item(**base, category="CONCALL_TRANSCRIPT", sentiment=mood, impact=2,
                                       headline=f"{sym} concall transcript: {summary}"))
        else:
            out.append(intel.make_item(**base, category="CONCALL_SCHEDULED", sentiment=0.0, impact=1,
                                       headline=f"{sym}: {text}"))
    return out
