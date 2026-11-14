"""News + Spurt team (user, 14 Nov 2026): the volume spurt gives the direction, the news says why.

Every quiet volume spurt (0.2-0.5% move, heavy volume, candle and VWAP its way) is checked against the
stock's own news since the previous session (the intelligence log: NSE filings, results, policy rules,
media), and gets one verdict:

- "against": a filing / results / policy item, or severe media news (impact 3+, strong tone), points the
  other way -> skip (the user's "severe bad news has to be avoided").
- "pending": results are due today and not yet out -> skip (a coin flip on the figures).
- "backed": a filing, results or policy item points the spurt's way -> trade at any time of the day
  (no 09:30-11:30 window, no Nifty-direction rule: the news is stock-specific), 15% target, or 10% when it
  looks priced in (the stock already ran 5%+ that way over the last 5 sessions).
- "none": no real catalyst -> the pure spurt rules apply (window, calm pre-open, OI, with the Nifty).

Media headlines alone never give a "backed" verdict: live, 95 plain media ideas were right only 44% of the
time, results filings 64% (journal/backtest_summary.md, 10 Nov). They are noted on the trade only.
"""
from datetime import datetime

CATALYST_KINDS = ("filing", "policy")
SEVERE_MEDIA_IMPACT = 3
SEVERE_MEDIA_TONE = 0.5
PRICED_IN_RUN_PCT = 5.0


def own_items(symbol: str, items: list[dict]) -> list[dict]:
    return [i for i in items if symbol in (i.get("symbols") or [])]


def classify(symbol: str, direction: str, items: list[dict], now: datetime,
             results_calendar: dict | None = None, run_5d_pct: float | None = None,
             overnight_note: dict | None = None) -> dict:
    """Verdict for a spurt `direction` ("up"/"down") on `symbol`; `items` = intel items since the previous session."""
    d = 1 if direction == "up" else -1
    own = own_items(symbol, items)
    today = now.date().isoformat()

    def head(i):
        return (i.get("headline") or i.get("category") or "")[:90]

    against, backed, media_for = [], [], []
    for i in own:
        tone = float(i.get("sentiment") or 0)
        impact = int(i.get("impact") or 0)
        if not tone:
            continue
        kind = i.get("kind", "")
        if kind in CATALYST_KINDS and impact >= 2:
            (backed if tone * d > 0 else against).append(i)
        elif kind == "news" and impact >= SEVERE_MEDIA_IMPACT and abs(tone) >= SEVERE_MEDIA_TONE:
            (media_for if tone * d > 0 else against).append(i)
    if against:
        i = against[0]
        return {"verdict": "against", "why": f"{i.get('kind')} against the spurt: {head(i)}", "target": None}
    results_out = any(i.get("category") == "RESULTS" for i in own)
    due = [str(x) for x in (results_calendar or {}).get(symbol, [])]
    if today in due and not results_out:
        return {"verdict": "pending", "why": "results due today, not out yet", "target": None}
    # Overnight picture vs the pre-open (agents/overnight.py). 2 years: after the open the overnight direction does not
    # carry on, and a gap already "priced in" drifts back a little (43% continue) -> a spurt WITH such a gap aims lower.
    on = overnight_note or {}
    gap_note, gap_priced = "", False
    if on.get("label"):
        gap_note = (f"; overnight forecast {on.get('expected_gap_pct', 0):+.1f}%, pre-open {on.get('preopen_gap_pct', 0):+.1f}%"
                    f" ({on['label']})")
        gap_priced = on["label"] == "priced in" and float(on.get("preopen_gap_pct") or 0) * d > 0
    if backed:
        i = max(backed, key=lambda x: (int(x.get("impact") or 0), abs(float(x.get("sentiment") or 0))))
        ran = run_5d_pct is not None and run_5d_pct * d >= PRICED_IN_RUN_PCT
        priced = ran or gap_priced
        why = f"{'results' if i.get('category') == 'RESULTS' else i.get('kind')} agree: {head(i)}" + gap_note
        if ran:
            why += f" (already ran {run_5d_pct:+.1f}% in 5 sessions: likely priced in, 10% target)"
        elif gap_priced:
            why += " (the opening gap already priced it in: 10% target)"
        return {"verdict": "backed", "why": why, "target": 10.0 if priced else 15.0, "priced_in": priced}
    note = f"media agrees (noted only): {head(media_for[0])}" if media_for else "no catalyst"
    return {"verdict": "none", "why": note + gap_note, "target": None}
