"""News Guard: the movers (technical) team borrows the news team's knowledge as a safety brake.

The movers team still chooses its trades from the chart alone. Before it buys, this agent looks
at what the news team has already collected for the stock (NSE filings, policy impacts, the Data
Analyzer's forecast) and blocks the trade when serious news is against it, so the team moves on
to another stock. Example: when IRDAI proposed insurance commission caps, PB Fintech fell 36% in
a day; a "top loser bouncing" CALL there would have been a trap.

It never adds points; it only says SKIP for a reason. No extra INDmoney calls: it reads the
shared intelligence log and today's filings.

    side "gainer": we buy a PUT expecting a fade   -> good news strongly behind the stock blocks it
    side "loser":  we buy a CALL expecting a bounce -> bad news strongly behind the fall blocks it
"""
from datetime import datetime

from . import analyzer

REGULATORY = ("REGULATORY",)


def check(symbol: str, side: str, items: list[dict], filings: list[dict], now: datetime,
          cfg: dict | None = None) -> dict:
    """{"block": bool, "points": 0, "notes": [...]} as a decision extra."""
    against = "down" if side == "loser" else "up"  # news direction that fights the reversal
    today = now.strftime("%Y-%m-%d")
    reasons = []

    for f in filings:
        if not str(f.get("time", "")).startswith(today):
            continue
        if f.get("category") == "RESULTS":
            reasons.append("Results out today: results-day moves are large and their direction unpredictable")
        elif f.get("category") in REGULATORY:
            reasons.append(f"Regulatory filing today: {str(f.get('text', ''))[:90]}")

    own = [i for i in items if symbol in i.get("symbols", []) and str(i.get("time", "")).startswith(today)]
    for i in own:
        if i.get("kind") == "policy" and i.get("impact", 0) >= 2:
            direction = "up" if i["sentiment"] > 0 else "down"
            if direction == against:
                reasons.append(f"Policy {'hit' if against == 'down' else 'boost'}: {i['headline'][:110]}")
        if i.get("kind") == "filing" and i.get("category") == "REGULATORY" and not any("Regulatory" in r for r in reasons):
            reasons.append(f"Regulatory action: {i['headline'][:100]}")

    # Only causes count, not headlines that describe the move itself ("IT stocks on fire, rally 15%"):
    # top gainers and losers always have those. Causes = filings, concalls, policy impacts and
    # major news (fraud, raid, probe, default, ban...).
    causes = [i for i in items if i.get("kind") != "news" or i.get("impact", 0) >= 3]
    view = analyzer.stock_view(symbol, causes, now, cfg)
    if view["strong"] and view["direction"] == against:
        top = "; ".join(view.get("reasons", [])[:1])
        reasons.append(f"Strong news {against} ({view['confidence']}%): {top[:100]}")

    if reasons:
        return {"block": True, "points": 0, "notes": [f"News Guard: skip, {r}" for r in reasons[:3]]}
    return {"block": False, "points": 0, "notes": []}
