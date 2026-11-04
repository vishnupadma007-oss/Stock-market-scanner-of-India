"""Shock-day guard for the movers (technical) team.

On a news shock the whole market runs one way: "US-Iran war ends" lifts everything, a war or a
policy surprise sinks everything. Betting on reversals then is a trap: fading top gainers fights
a market-wide rally, buying bouncing losers catches falling knives in a crash.

This layer looks at the whole market, not one stock:
  - Nifty's move today (and the opening gap)
  - India VIX's jump (fear) or collapse (relief)
  - breadth: how many sector indices are moving the same way
  - shock news: several big macro headlines (war, ceasefire, peace deal, attack, rate surprise...)
    in the last few hours, from the news team's log

Verdict:
  "normal"  nothing to do
  "rally"   no fading of gainers (no PUTs); buying CALLs with the tide is still allowed
  "crash"   no bounce trades on losers (no CALLs); PUTs with the tide are still allowed
  "extreme" the movers team stands aside until the market settles

Backtest note (6 months to Oct 2026): on ordinary +-1% Nifty days the reversals did fine, so
the thresholds are set for genuine shocks only (about 1.5% and up with confirming signs).
"""
import re
from datetime import datetime

from . import analyzer

SHOCK_NEWS = r"\bwar\b|ceasefire|cease-fire|truce|peace (deal|talks|agreement)|attack|missile|strike[sd]? on|invasion|" \
             r"sanction|emergency|crash|plunge|surge|soar|rate (cut|hike)|surprise|default|lockdown|pandemic|" \
             r"nuclear|tariff|escalat|de-escalat|hostilit"

DEFAULTS = {
    "move_pct": 1.5,          # Nifty move that, with confirmation, makes a shock day
    "extreme_pct": 2.5,       # Nifty move at which the movers team stands aside
    "vix_jump_pct": 12.0,     # VIX up this much = fear shock; down this much = relief shock
    "breadth_share": 0.8,     # share of sector indices moving the same way (>= 0.5%) to call it market-wide
    "news_hours": 3.0,        # how far back to look for shock headlines
    "news_count": 3,          # big macro headlines of the same tone needed to confirm
}


def shock_news(items: list[dict], now: datetime, hours: float) -> dict:
    """Big macro headlines (global/market scope) of the last `hours`, by tone."""
    now = now.replace(tzinfo=None)
    recent = [i for i in items if i.get("scope") in ("global", "market") and i.get("kind") == "news"
              and analyzer.market_hours_between(datetime.strptime(i["time"][:19], "%Y-%m-%d %H:%M:%S"), now) <= hours
              and re.search(SHOCK_NEWS, i["headline"], re.I) and abs(i.get("sentiment", 0)) >= 0.5]
    good = [i for i in recent if i["sentiment"] > 0]
    bad = [i for i in recent if i["sentiment"] < 0]
    return {"good": len(good), "bad": len(bad),
            "top": [i["headline"][:120] for i in sorted(recent, key=lambda i: -abs(i["sentiment"]))[:3]]}


def assess(nifty_pct: float | None, vix_pct: float | None, sectors: dict, items: list[dict], now: datetime,
           cfg: dict | None = None) -> dict:
    c = {**DEFAULTS, **((cfg or {}).get("shock") or {})}
    if nifty_pct is None:
        return {"state": "normal", "notes": []}
    moves = [v for k, v in sectors.items() if k != "Market" and v is not None]
    up_share = sum(v >= 0.5 for v in moves) / len(moves) if moves else 0.0
    down_share = sum(v <= -0.5 for v in moves) / len(moves) if moves else 0.0
    news = shock_news(items, now, c["news_hours"])
    direction = 1 if nifty_pct > 0 else -1
    confirms = []
    if (up_share if direction > 0 else down_share) >= c["breadth_share"]:
        confirms.append(f"{(up_share if direction > 0 else down_share) * 100:.0f}% of sectors moving the same way")
    if vix_pct is not None and (vix_pct >= c["vix_jump_pct"] if direction < 0 else vix_pct <= -c["vix_jump_pct"]):
        confirms.append(f"India VIX {vix_pct:+.1f}%")
    if (news["good"] if direction > 0 else news["bad"]) >= c["news_count"]:
        confirms.append(f"{news['good'] if direction > 0 else news['bad']} big {'good' if direction > 0 else 'bad'} macro headlines")
    fear = vix_pct is not None and abs(vix_pct) >= 2 * c["vix_jump_pct"]

    if abs(nifty_pct) >= c["extreme_pct"] or (abs(nifty_pct) >= c["move_pct"] and fear):
        state = "extreme"
    elif abs(nifty_pct) >= c["move_pct"] and confirms:
        state = "rally" if direction > 0 else "crash"
    else:
        return {"state": "normal", "notes": [], "news": news}
    what = {"extreme": "market-wide shock: the movers team stands aside",
            "rally": "market-wide rally: no fading of gainers (PUTs)",
            "crash": "market-wide fall: no bounce trades on losers (CALLs)"}[state]
    notes = [f"Shock day ({what}): Nifty {nifty_pct:+.2f}%" + (f"; {', '.join(confirms)}" if confirms else "")]
    if news["top"]:
        notes.append("Shock news: " + " | ".join(news["top"][:2]))
    return {"state": state, "notes": notes, "news": news,
            "gainers_ok": state == "crash", "losers_ok": state == "rally"}
