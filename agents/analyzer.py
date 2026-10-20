"""Data Analyzer: combines everything the information agents found into one view per stock.

For each stock it adds up the tone x importance of every item about it, its sector and the
market, with older items counting less (news fades within hours, filings within a day or two).
Several independent sources agreeing count for more than one loud headline.

Output per stock: direction (up / down / neutral), confidence 0-100, and the reasons.
Used three ways: as one more voice in every trade decision, as FORECAST events that wake
Claude when a stock's outlook turns strong, and in the morning brief.

    python -m agents.analyzer          # market mood + strongest forecasts right now
"""
import math
from datetime import datetime, timedelta

from . import intel
from .sectors import STOCK_SECTOR

HALF_LIFE_H = {"news": 3, "concall": 24, "filing": 24}
SCOPE_WEIGHT = {"stock": 1.0, "sector": 0.5, "market": 0.3, "global": 0.3}
DEFAULTS = {"forecast_score": 2.0, "min_sources": 2, "agree_points": 10, "against_points": -20}


def _weight(item: dict, now: datetime) -> float:
    try:
        age_h = (now - datetime.strptime(item["time"], "%Y-%m-%d %H:%M:%S")).total_seconds() / 3600
    except (KeyError, ValueError):
        age_h = 0
    return 0.5 ** (max(age_h, 0) / HALF_LIFE_H.get(item.get("kind"), 6))


def _mean_tone(items: list[dict], now: datetime) -> float:
    """Importance- and age-weighted average tone, -1..+1 (an average, so 300 headlines do not
    outweigh one company's results just by being many)."""
    weights = [i["impact"] * _weight(i, now) for i in items]
    total = sum(weights)
    return sum(i["sentiment"] * w for i, w in zip(items, weights)) / total if total else 0.0


def _top(items: list[dict], now: datetime, n: int) -> list[str]:
    ranked = sorted(items, key=lambda i: -abs(i["sentiment"]) * i["impact"] * _weight(i, now))
    return [i["headline"] for i in ranked[:n] if i["sentiment"]]


def market_mood(items: list[dict], now: datetime) -> dict:
    rel = [i for i in items if i["scope"] in ("market", "global")]
    tone = _mean_tone(rel, now)
    return {"tone": round(tone, 2), "mood": "positive" if tone > 0.15 else "negative" if tone < -0.15 else "neutral",
            "headlines": len(rel), "reasons": _top(rel, now, 5)}


def stock_view(symbol: str, items: list[dict], now: datetime, cfg: dict | None = None) -> dict:
    """score = own news (capped at +/-3) + sector tone (+/-1) + market tone (+/-0.6)."""
    c = {**DEFAULTS, **((cfg or {}).get("analyzer") or {})}
    sector = STOCK_SECTOR.get(symbol)
    own = [i for i in items if symbol in i["symbols"]]
    own_raw = sum(i["sentiment"] * i["impact"] * _weight(i, now) for i in own)
    own_score = 3 * math.tanh(own_raw / 3)
    sector_tone = _mean_tone([i for i in items if sector and sector in i["sectors"] and symbol not in i["symbols"]], now)
    market_tone = _mean_tone([i for i in items if i["scope"] in ("market", "global")], now)
    score = own_score + SCOPE_WEIGHT["sector"] * 2 * sector_tone + SCOPE_WEIGHT["market"] * 2 * market_tone
    sources = {i["source"] for i in own if abs(i["sentiment"]) > 0}
    direction = "up" if score >= 1 else "down" if score <= -1 else "neutral"
    confidence = min(100, round(100 * (1 - math.exp(-abs(score) / 2)) + 5 * max(len(sources) - 1, 0)))
    major = any(i["impact"] >= 3 and i["sentiment"] for i in own)
    # Strong = the stock's OWN news is loud and confirmed (2+ sources or a major item such as results),
    # and the overall score (with sector and market mood) still points the same way.
    strong = abs(own_score) >= c["forecast_score"] and (len(sources) >= c["min_sources"] or major) \
        and score * own_score > 0 and direction != "neutral"
    return {"symbol": symbol, "score": round(score, 2), "direction": direction, "confidence": confidence,
            "own_news": round(own_score, 2), "sector_tone": round(sector_tone, 2), "market_tone": round(market_tone, 2),
            "sources": sorted(sources), "strong": strong, "reasons": _top(own, now, 4)}


def as_extra(view: dict, side: str, cfg: dict) -> dict:
    """The analyzer's voice in a reversal-trade decision: CE on a loser wants 'up', PE on a gainer 'down'."""
    c = {**DEFAULTS, **(cfg.get("analyzer") or {})}
    want = "up" if side == "loser" else "down"
    if view["direction"] == "neutral" or view["confidence"] < 30:
        return {"points": 0, "notes": []}
    if view["direction"] == want:
        return {"points": c["agree_points"], "notes": [f"Analyzer: news flow points {want} ({view['confidence']}%)"]}
    return {"points": c["against_points"],
            "notes": [f"Analyzer: news flow points {view['direction']}, against the trade ({view['confidence']}%): "
                      f"{view['reasons'][0] if view['reasons'] else ''}"]}


def recent_items(now: datetime) -> list[dict]:
    return intel.load((now - timedelta(days=1)).date().isoformat(), now.date().isoformat())


def main() -> None:
    import json
    from .config import load_config
    now = datetime.now()
    items = recent_items(now)
    print(json.dumps({"items": len(items), "market": market_mood(items, now)}, indent=1))
    views = [stock_view(s, items, now) for s in load_config()["universe"]]
    for v in sorted(views, key=lambda v: -abs(v["score"]))[:10]:
        if v["score"]:
            print(json.dumps(v))


if __name__ == "__main__":
    main()
