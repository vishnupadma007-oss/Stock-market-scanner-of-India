"""Market Context agent: how is Nifty moving, and why?

Before the news team trades, this agent sums up the outside environment from the intelligence
log (Indian business news, global and India macro feeds, NSE filings) and live index moves:

  geopolitical    wars, attacks, sanctions, border tension
  policy          RBI, SEBI, government, budget, taxes, tariffs, central banks abroad
  domestic        GDP, inflation, monsoon, rupee, fiscal numbers
  global markets  Wall Street, Asian markets, US yields
  commodities     crude, gold, metals
  flows           foreign (FII/FPI) and domestic (DII) investor money

For each theme it gives the tone (-1 bad .. +1 good for Indian stocks) and the top headlines,
so a trade can be checked against the market's mood: buying a CALL while Nifty is sliding on bad
news (or a PUT into a strong rally) fights the tide, and the news team skips it.

    python -m agents.market          # the market picture right now
"""
import re
import sys
from datetime import datetime

from . import analyzer

THEMES = {
    "geopolitical": r"\bwar\b|attack|missile|strike[sd]? on|sanction|ceasefire|tension|conflict|houthi|hezbollah|"
                    r"\biran\b|israel|russia|ukraine|taiwan|border|geopolit",
    "policy": r"\brbi\b|repo rate|monetary policy|\bsebi\b|government|cabinet|budget|\bgst\b|tax(es)?\b|tariff|"
              r"regulat|\bpolicy\b|\bfed\b|federal reserve|\becb\b|boj|rate (cut|hike)|ministry|\bban\b",
    "domestic": r"\bgdp\b|inflation|\bcpi\b|\bwpi\b|\biip\b|\bpmi\b|monsoon|fiscal|deficit|\brupee\b|india('s)? economy|"
                r"consumption|unemployment",
    "global markets": r"wall street|nasdaq|\bdow\b|s&p|asian (markets|stocks)|nikkei|hang seng|kospi|us stocks|"
                      r"treasury|global markets|european (markets|stocks)",
    "commodities": r"crude|brent|\boil\b|opec|\bgold\b|silver|copper|aluminium|steel prices|natural gas",
    "flows": r"\bfiis?\b|\bfpis?\b|\bdiis?\b|foreign (investors|funds|inflows|outflows)|outflow|inflow|selling by",
}


def theme_of(headline: str) -> list[str]:
    return [t for t, p in THEMES.items() if re.search(p, headline, re.I)]


def context(items: list[dict], now: datetime, nifty_pct: float | None = None, vix: float | None = None,
            vix_pct: float | None = None) -> dict:
    """The market picture: Nifty's move today, the news mood, and the drivers by theme."""
    rel = [i for i in items if i["scope"] in ("market", "global", "sector") and i.get("kind") == "news"]
    drivers = {}
    for theme in THEMES:
        hits = [i for i in rel if theme in theme_of(i["headline"])]
        if not hits:
            continue
        w = [analyzer._weight(i, now) for i in hits]
        tone = sum(i["sentiment"] * x for i, x in zip(hits, w)) / (sum(w) or 1)
        top = sorted(zip(hits, w), key=lambda p: -abs(p[0]["sentiment"]) * p[1])
        drivers[theme] = {"tone": round(tone, 2), "stories": len(hits),
                          "headlines": [i["headline"][:140] for i, _ in top[:2] if i["sentiment"]]}
    mood = analyzer.market_mood(items, now)
    if nifty_pct is None:
        trend = "unknown"
    else:
        trend = "rallying" if nifty_pct >= 0.8 else "rising" if nifty_pct >= 0.25 else \
            "sliding" if nifty_pct <= -0.8 else "falling" if nifty_pct <= -0.25 else "flat"
    worst = sorted((d for d in drivers.items() if d[1]["tone"] < 0), key=lambda d: d[1]["tone"])
    best = sorted((d for d in drivers.items() if d[1]["tone"] > 0), key=lambda d: -d[1]["tone"])
    why = (", ".join(t for t, _ in worst[:2]) if (nifty_pct or 0) < 0 else ", ".join(t for t, _ in best[:2])) or "no clear driver"
    notes = [f"Nifty {nifty_pct:+.2f}% ({trend})" if nifty_pct is not None else "Nifty move unknown",
             f"news mood {mood['mood']} ({mood['tone']:+.2f}); main drivers: {why}"]
    if vix is not None:
        notes.append(f"India VIX {vix:.1f}" + (f" ({vix_pct:+.1f}%)" if vix_pct is not None else ""))
    return {"nifty_pct": nifty_pct, "trend": trend, "mood": mood["mood"], "mood_tone": mood["tone"],
            "vix": vix, "drivers": drivers, "notes": notes}


def headwind(ctx: dict, direction: str, limit_pct: float = 0.8) -> str | None:
    """Why a trade fights the market, or None. Buying a CALL into a market down `limit_pct`% or more
    on bad news (or a PUT into an equally strong rally on good news) is skipped."""
    n = ctx.get("nifty_pct")
    if n is None:
        return None
    if direction == "up" and n <= -limit_pct and ctx["mood_tone"] < 0:
        return f"Market headwind: Nifty {n:+.2f}% on {ctx['mood']} news; a CALL fights the tide"
    if direction == "down" and n >= limit_pct and ctx["mood_tone"] > 0:
        return f"Market tailwind for buyers: Nifty {n:+.2f}% on {ctx['mood']} news; a PUT fights the tide"
    return None


def main(argv: list[str]) -> None:
    import json
    now = datetime.now()
    ctx = context(analyzer.recent_items(now), now)
    print(json.dumps(ctx, indent=1))


if __name__ == "__main__":
    main(sys.argv)
