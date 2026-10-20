"""Valuation agent: is the stock cheap or expensive against its sector peers?

INDmoney has no P/E or P/B, so the figures come from Yahoo Finance once a day (morning brief,
or the watcher's first information cycle) and are saved to journal/valuations/<date>.json.

Banks and finance companies are valued on price-to-book (P/B), everyone else on trailing P/E.
Each stock is compared with the median of its sector peers in our F&O list; PEG (P/E divided
by profit growth) and forward P/E (analysts' next-year earnings) are shown as context.

How it is used:
  - Expectations agent: an expensive stock already holds good news, a cheap one bad news.
  - Scanner (observe mode until paper trades prove it): a fading gainer that is expensive, or a
    bouncing loser that is cheap, agrees with the reversal; the opposite argues against it.

    python -m agents.valuation              # refresh today's snapshot and print the table
    python -m agents.valuation TECHM        # one stock vs its peers
"""
import json
import statistics
import sys
import time
from datetime import date
from pathlib import Path

from .sectors import sector_of

DIR = Path(__file__).resolve().parent.parent / "journal" / "valuations"
BOOK_VALUED = {"Bank", "PSU Bank"}  # lenders: price-to-book, not P/E

DEFAULTS = {
    "mode": "observe",      # "observe" (notes only) or "score" (points count in the decision)
    "agree_points": 5,      # expensive gainer fading / cheap loser bouncing
    "against_points": -5,   # cheap gainer fading / expensive loser bouncing
}
YAHOO_FIELDS = {"pe": "trailingPE", "forward_pe": "forwardPE", "pb": "priceToBook", "peg": "pegRatio",
                "roe": "returnOnEquity", "profit_growth": "earningsGrowth", "revenue_growth": "revenueGrowth",
                "dividend_yield": "dividendYield", "price": "currentPrice"}


def fetch(symbol: str) -> dict:
    import yfinance as yf
    info = yf.Ticker(f"{symbol}.NS").info
    out = {k: info.get(v) for k, v in YAHOO_FIELDS.items()}
    return {k: round(v, 3) if isinstance(v, float) else v for k, v in out.items()}


def path_for(day: date) -> Path:
    return DIR / f"{day.isoformat()}.json"


def snapshot(universe: list[str], day: date | None = None, refresh: bool = False) -> dict[str, dict]:
    """Today's valuation figures for every stock (read from the saved file when it exists)."""
    day = day or date.today()
    p = path_for(day)
    if p.exists() and not refresh:
        return json.loads(p.read_text())
    snap = {}
    for symbol in universe:
        try:
            snap[symbol] = fetch(symbol)
        except Exception:
            continue  # a missing stock just gets no valuation view
        time.sleep(0.5)  # be gentle with Yahoo
    if snap:
        DIR.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(snap, indent=0))
    return snap


def _metric(symbol: str, figures: dict) -> tuple[str, float | None]:
    name = "pb" if sector_of(symbol) in BOOK_VALUED else "pe"
    value = figures.get(name)
    return name, value if isinstance(value, (int, float)) and value > 0 else None


def assess(symbol: str, snap: dict[str, dict]) -> dict:
    """{label, rich (-30 cheap .. +30 expensive), metric, value, peer_median, notes}."""
    figures = snap.get(symbol)
    if not figures:
        return {"label": "unknown", "rich": 0, "notes": []}
    name, value = _metric(symbol, figures)
    sector = sector_of(symbol)
    peers = [v for s, f in snap.items() if s != symbol and sector_of(s) == sector
             for n, v in [_metric(s, f)] if v is not None]
    tag = "P/B" if name == "pb" else "P/E"
    if value is None:
        return {"label": "loss-making / no P/E" if name == "pe" else "unknown", "rich": 0, "metric": tag,
                "notes": [f"Valuation: no meaningful {tag}"]}
    if len(peers) < 2:
        return {"label": "no peer group", "rich": 0, "metric": tag, "value": value,
                "notes": [f"Valuation: {tag} {value:.1f} (too few sector peers to compare)"]}
    median = statistics.median(peers)
    ratio = value / median
    if ratio >= 1.5:
        label, rich = "expensive vs peers", 30
    elif ratio >= 1.2:
        label, rich = "richer than peers", 15
    elif ratio <= 0.67:
        label, rich = "cheap vs peers", -30
    elif ratio <= 0.83:
        label, rich = "cheaper than peers", -15
    else:
        label, rich = "in line with peers", 0
    group = sector if sector != "Market" else "other F&O stocks"
    note = f"Valuation: {tag} {value:.1f} vs {group} median {median:.1f} ({label})"
    extra = []
    if name == "pe" and figures.get("forward_pe"):
        extra.append(f"forward P/E {figures['forward_pe']:.1f}")
    if figures.get("peg"):
        extra.append(f"PEG {figures['peg']:.2f}")
    if figures.get("profit_growth") is not None:
        extra.append(f"profit growth {figures['profit_growth'] * 100:+.0f}%")
    if extra:
        note += "; " + ", ".join(extra)
    return {"label": label, "rich": rich, "metric": tag, "value": value, "peer_median": round(median, 2),
            "notes": [note]}


def as_extra(view: dict, side: str, cfg: dict) -> dict:
    """Decision extra for a reversal trade. gainer = buy PE expecting a fade, loser = buy CE."""
    c = {**DEFAULTS, **(cfg.get("valuation") or {})}
    points = 0
    if view.get("rich", 0) >= 15:
        points = c["agree_points"] if side == "gainer" else c["against_points"]
    elif view.get("rich", 0) <= -15:
        points = c["agree_points"] if side == "loser" else c["against_points"]
    observe = c["mode"] != "score"
    notes = view.get("notes", [])
    return {"points": 0 if observe else points, "block": False,
            "notes": [f"(observe) {n}" for n in notes] if observe else notes,
            "label": view.get("label", "unknown"), "would_score": points}


def main(argv: list[str]) -> None:
    from .config import load_config
    universe = load_config()["universe"]
    snap = snapshot(universe, refresh=len(argv) == 1)
    symbols = [a.upper() for a in argv[1:]] or universe
    for s in symbols:
        print(s, json.dumps(assess(s, snap)))


if __name__ == "__main__":
    main(sys.argv)
