"""Mover Forecast (morning brief): which F&O stocks are likely to be today's top gainers and
losers, and how their direction will be decided.

What our data says makes a top mover (26 Oct 2026, 1 year x 76 stocks): a results day makes a
stock about 5x more likely to be among the day's five biggest movers, and on results days the
opening gap carries on (61-75%), while on ordinary days big gaps tend to reverse. News is the
other driver: the Data Analyzer's strong views. So:
  - results since the last close: expected size = the stock's typical results-day move (3 years of
    its own reactions, falling back to the 2.3% all-stock median); direction = set by the open
    (results-gap rule, agents/gapfollow.py), never by the figures alone (coin flip);
  - strong news views (Data Analyzer): direction = the forecast, size = the stock's usual daily move.

    python -m agents.mover_forecast        # ranked list for the morning brief
"""
import json
from datetime import datetime, timedelta
from pathlib import Path

from . import analyzer, holidays
from .config import load_config

ANNOUNCEMENTS = Path(__file__).resolve().parents[1] / "journal" / "announcements.csv"
RESULTS_HISTORY = Path(__file__).resolve().parents[1] / "journal" / "results_history"
MEDIAN_RESULTS_MOVE = 2.3  # median |close| move on results days, all our stocks, 3 years


def results_move(symbol: str) -> float:
    """Median |close-to-close| move on this stock's past results days (%)."""
    try:
        moves = sorted(abs(e["reaction"]["close_pct"]) for e in json.loads((RESULTS_HISTORY / f"{symbol}.json").read_text())
                       if (e.get("reaction") or {}).get("close_pct") is not None)
        return round(moves[len(moves) // 2], 2) if len(moves) >= 3 else MEDIAN_RESULTS_MOVE
    except (OSError, ValueError, KeyError):
        return MEDIAN_RESULTS_MOVE


def results_since_last_close(now: datetime) -> set[str]:
    import csv
    # From the previous session's open: results filed during that session still move the stock the next day.
    since = f"{holidays.previous_trading_day(now.date() - timedelta(days=1))} 09:15:00"
    if not ANNOUNCEMENTS.exists():
        return set()
    return {r["symbol"] for r in csv.DictReader(open(ANNOUNCEMENTS))
            if r.get("category") == "RESULTS" and r.get("time", "") >= since}


def forecast(now: datetime | None = None, top: int = 12) -> list[dict]:
    now = now or datetime.now()
    universe = load_config()["universe"]
    items = analyzer.recent_items(now)
    reported = results_since_last_close(now) & set(universe)
    rows = []
    for sym in universe:
        view = analyzer.stock_view(sym, items, now)
        if sym in reported:
            rows.append({"symbol": sym, "why": "results since last session", "expected_move_pct": results_move(sym),
                         "direction": "set by the open (results-gap rule)", "news_view": f"{view['direction']} {view['confidence']}%"})
        elif view["strong"]:
            from .reaction import typical_move
            rows.append({"symbol": sym, "why": "strong news: " + "; ".join(view["reasons"][:1])[:90],
                         "expected_move_pct": typical_move(sym) or 1.0,
                         "direction": f"{view['direction']} ({view['confidence']}%)", "news_view": ""})
    # Results first (the strongest driver), then by expected size.
    rows.sort(key=lambda r: (r["why"] != "results since last session", -r["expected_move_pct"]))
    return rows[:top]


def main() -> None:
    for r in forecast():
        print(f"{r['symbol']:11} ~{r['expected_move_pct']:.1f}%  {r['direction']:36} {r['why'][:70]}"
              + (f"  [news reads {r['news_view']}]" if r["news_view"] else ""))


if __name__ == "__main__":
    main()
