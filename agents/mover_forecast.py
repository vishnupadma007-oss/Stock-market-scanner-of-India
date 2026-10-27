"""Mover Forecast (morning brief): which F&O stocks are likely to be today's top gainers and
losers, and how their direction and target price will be decided.

What our data says makes a top mover (26 Oct 2026, 1 year x 76 stocks): a results day makes a
stock about 5x more likely to be among the day's five biggest movers, and on results days the
opening gap carries on (61-75%), while on ordinary days big gaps tend to reverse. News is the
other driver: the Data Analyzer's strong views. So:
  - results since the last close: expected size = the stock's typical results-day move (3 years of
    its own reactions, falling back to the 2.3% all-stock median); direction = set by the open
    (results-gap rule, agents/gapfollow.py), never by the figures alone (coin flip);
  - strong news views (Data Analyzer): direction = the forecast, size = the stock's usual daily move;
  - target price: projected underlying target price based on expected percentage movement.

    python -m agents.mover_forecast        # ranked list for the morning brief
"""
import json
from datetime import datetime, time, timedelta
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


def preopen_gaps(now: datetime) -> dict:
    """Today's NSE pre-open (saved by the watcher at 09:08, or fetched now), {} before 09:08."""
    from . import preopen
    data = preopen.load("preopen", now.date())
    if data is None and now.time() >= time(9, 8) and holidays.is_trading_day(now.date()):
        try:
            data = preopen.fetch_preopen(load_config()["universe"])
            preopen.save("preopen", now.date(), data)
        except Exception:
            data = None
    return data or {}


def forecast(now: datetime | None = None, top: int = 12) -> list[dict]:
    now = now or datetime.now()
    universe = load_config()["universe"]
    items = analyzer.recent_items(now)
    reported = results_since_last_close(now) & set(universe)
    pre = preopen_gaps(now)
    rows = []
    for sym in universe:
        view = analyzer.stock_view(sym, items, now)
        pre_info = pre.get(sym) or {}
        gap = pre_info.get("gap_pct")
        prev = pre_info.get("prev_close")
        if sym in reported:
            exp_move = results_move(sym)
            target_str = f"₹{prev * (1 + exp_move / 100):.1f} / ₹{prev * (1 - exp_move / 100):.1f}" if prev else "Pending open"
            rows.append({"symbol": sym, "why": "results since last session", "expected_move_pct": exp_move,
                         "direction": "follow the gap if the first 15 min agree (results-gap rule)",
                         "news_view": f"{view['direction']} {view['confidence']}%", "preopen_gap": gap,
                         "prev_close": prev, "expected_target_price": target_str})
        elif gap is not None and abs(gap) >= 2:
            exp_move = abs(gap)
            reversal_target = round(prev * (1 - 0.5 * gap / 100), 1) if prev else None
            rows.append({"symbol": sym, "why": f"pre-open gap {gap:+.1f}%, no results: ordinary-day gaps tend to reverse",
                         "expected_move_pct": exp_move, "direction": "fade candidate (movers team)", "news_view": "",
                         "preopen_gap": gap, "prev_close": prev, "expected_target_price": f"₹{reversal_target}" if reversal_target else ""})
        elif view["strong"]:
            from .reaction import typical_move
            exp_move = typical_move(sym) or 1.5
            sign = 1 if view["direction"] == "up" else -1
            target_val = round(prev * (1 + sign * exp_move / 100), 1) if prev else None
            rows.append({"symbol": sym, "why": "strong news: " + "; ".join(view["reasons"][:1])[:90],
                         "expected_move_pct": exp_move,
                         "direction": f"{view['direction']} ({view['confidence']}%)", "news_view": "", "preopen_gap": gap,
                         "prev_close": prev, "expected_target_price": f"₹{target_val}" if target_val else ""})
    # Results first (the strongest driver), then by expected size.
    rows.sort(key=lambda r: (r["why"] != "results since last session", -r["expected_move_pct"]))
    return rows[:top]


def main() -> None:
    for r in forecast():
        pre = f"pre-open {r['preopen_gap']:+.1f}%  " if r.get("preopen_gap") is not None else ""
        tgt = f"target {r['expected_target_price']}  " if r.get("expected_target_price") else ""
        print(f"{r['symbol']:11} ~{r['expected_move_pct']:.1f}%  {pre}{tgt}{r['direction']:40} {r['why'][:65]}"
              + (f"  [news reads {r['news_view']}]" if r["news_view"] else ""))


if __name__ == "__main__":
    main()
