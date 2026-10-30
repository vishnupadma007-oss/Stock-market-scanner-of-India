"""Grok (xAI) helper: AI where Python's own rules fall short (user's plan, 30 Oct 2026).

Stage 2, live: read a results filing's figures when our parser cannot (scanned or unusual tables:
Maruti, Bajaj Auto, Vedanta in the week of 27 Oct). Grok gets the filing's text and returns revenue
and profit for this quarter, the previous quarter and the same quarter last year.
Stage 1, observe only: a TRADE / SKIP view with a reason on every SIGNAL, logged to
journal/grok_verdicts.csv. It never blocks a trade; Claude compares it with the outcomes in the
evening review, and it gets a say only if its calls beat the rules.

The key is read from XAI_API_KEY or ~/.config/xai/key (outside the repository, never committed).
Without a key everything here is skipped. A daily call cap keeps the xAI bill small.

    python -m agents.grok test        # one tiny call to check the key
"""
import csv
import json
import os
import re
import threading
from datetime import date, datetime
from pathlib import Path

import requests

URL = "https://api.x.ai/v1/responses"
KEY_FILE = Path.home() / ".config" / "xai" / "key"
VERDICTS = Path(__file__).resolve().parents[1] / "journal" / "grok_verdicts.csv"
DEFAULTS = {"enabled": True, "model": "grok-4", "max_calls_per_day": 80, "timeout": 60}
_calls = {"day": None, "n": 0}
_lock = threading.Lock()


def api_key() -> str | None:
    key = os.environ.get("XAI_API_KEY")
    if key:
        return key.strip()
    try:
        return KEY_FILE.read_text().strip() or None
    except OSError:
        return None


def save_key(key: str) -> None:
    KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
    KEY_FILE.write_text(key.strip())
    KEY_FILE.chmod(0o600)


def available(cfg: dict | None = None) -> bool:
    c = {**DEFAULTS, **((cfg or {}).get("grok") or {})}
    return bool(c["enabled"] and api_key())


def _budget(c: dict) -> bool:
    with _lock:
        today = date.today()
        if _calls["day"] != today:
            _calls.update(day=today, n=0)
        if _calls["n"] >= c["max_calls_per_day"]:
            return False
        _calls["n"] += 1
        return True


def ask(prompt: str, cfg: dict | None = None, system: str = "") -> str | None:
    """One call to Grok's Responses API; the reply's text, or None (no key, cap reached, error)."""
    c = {**DEFAULTS, **((cfg or {}).get("grok") or {})}
    key = api_key()
    if not c["enabled"] or not key or not _budget(c):
        return None
    messages = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": prompt}]
    r = requests.post(URL, headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                      json={"model": c["model"], "input": messages}, timeout=c["timeout"])
    r.raise_for_status()
    return output_text(r.json())


def output_text(payload: dict) -> str:
    """The text of a Responses API reply (output -> message -> content -> output_text)."""
    if payload.get("output_text"):
        return payload["output_text"]
    parts = []
    for item in payload.get("output") or []:
        for piece in item.get("content") or []:
            if piece.get("type") in ("output_text", "text") and piece.get("text"):
                parts.append(piece["text"])
    return "\n".join(parts)


def _json(text: str | None) -> dict | None:
    if not text:
        return None
    m = re.search(r"\{.*\}", text, re.S)
    try:
        return json.loads(m.group(0)) if m else None
    except ValueError:
        return None


FIGURES_PROMPT = """From this Indian listed company's quarterly results filing ({symbol}), give revenue from
operations and net profit (after tax, attributable to owners if shown) in Rs crore, CONSOLIDATED if both
consolidated and standalone are given, for: this quarter, the previous quarter, the same quarter last year.
Reply with JSON only: {{"revenue": [q, prev_q, year_ago], "profit": [q, prev_q, year_ago], "basis": "consolidated|standalone"}}.
Use null for a figure you cannot find. Do not guess.

FILING TEXT:
{text}"""


def results_figures(text: str, symbol: str, cfg: dict | None = None) -> dict:
    """Figures in the parser's format ({"revenue": {...}, "profit": {...}}), or {} if Grok cannot help."""
    from .announcements import change_pct
    data = _json(ask(FIGURES_PROMPT.format(symbol=symbol, text=text[:24000]), cfg))
    out = {}
    for key in ("revenue", "profit"):
        vals = (data or {}).get(key)
        if not isinstance(vals, list) or len(vals) != 3 or any(not isinstance(v, (int, float)) for v in vals):
            continue
        cur, prev_q, prev_y = (float(v) for v in vals)
        out[key] = {"quarter": cur, "prev_quarter": prev_q, "year_ago": prev_y,
                    "qoq_pct": change_pct(cur, prev_q), "yoy_pct": change_pct(cur, prev_y), "source": "grok"}
    return out


VERDICT_PROMPT = """You review paper trades on an Indian NSE F&O options desk (intraday, options bought only,
no stop-loss, square-off 15:20 IST). Our agents opened this trade; judge it with what is in the signal.
Reply with JSON only: {{"verdict": "TRADE" or "SKIP", "confidence": 0-100, "reason": "one sentence"}}.

SIGNAL:
{signal}"""


def log_verdict(signal: dict, cfg: dict | None = None) -> None:
    """Stage 1 (observe only): Grok's view of a SIGNAL, appended to journal/grok_verdicts.csv."""
    try:
        data = _json(ask(VERDICT_PROMPT.format(signal=json.dumps(signal, default=str)[:6000]), cfg)) or {}
    except Exception as e:  # never let the helper disturb trading
        data = {"verdict": "", "reason": f"error: {type(e).__name__}"}
    if not data:
        return
    new = not VERDICTS.exists()
    VERDICTS.parent.mkdir(exist_ok=True)
    with open(VERDICTS, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["date", "time", "team", "symbol", "contract", "verdict", "confidence", "reason"])
        w.writerow([date.today().isoformat(), datetime.now().strftime("%H:%M"), signal.get("team", ""),
                    signal.get("symbol", ""), signal.get("contract", ""), data.get("verdict", ""),
                    data.get("confidence", ""), str(data.get("reason", ""))[:300]])


def main(argv: list[str]) -> None:
    if len(argv) > 1 and argv[1] == "test":
        print("key found" if api_key() else "no key")
        print(ask('Reply with the JSON {"ok": true} only.', {"grok": {"max_calls_per_day": 1000}}))


if __name__ == "__main__":
    import sys
    main(sys.argv)
