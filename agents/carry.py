"""Overnight carry (user's rule, 3 Nov 2026): a trade that has not reached its target by 15:20 is kept
overnight instead of being squared off, unless the stock has its own news that makes the night a gamble.
The next session it sells at the target or at 15:20 (one night at most).

Carry at 15:20 only if:
- carrying is enabled for the trade's team (config.yaml -> carry),
- the trade was opened today (a carried trade is never carried a second night),
- the option has at least `min_days_to_expiry` days left (no carrying into expiry week's last days),
- the stock has no results today or on the next session (NSE results calendar), and no results or
  regulatory filing of its own today.

Next morning, before anything else: if the stock filed results or a regulatory action overnight, or
its own news turned strongly against the trade, sell at the first live bid after the open.

Evidence (journal/backtest_summary.md): on the 9 real paper trades of 27-30 Oct that missed their target,
carrying would have turned -Rs 22,225 into about +Rs 9,800 (6 of 9 hit the target next day); on 60 days of
quiet-spurt backtest trades carrying lost more than squaring off. A live paper test, judged by the review.
"""
import re
from datetime import date, datetime, time, timedelta

from . import analyzer

DEFAULTS = {"enabled": False, "teams": ["news", "spurt", "preopen", "movers"], "min_days_to_expiry": 3, "open_after": "09:16", "carry_puts": True}
MARK = "carried overnight"
MONTHS = {m: i for i, m in enumerate(["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"], 1)}


def expiry_of(contract: str, today: date) -> date | None:
    """Expiry from a contract name like 'SBIN-23-NOV-980-CALL' (the year is the next such date from today)."""
    m = re.search(r"-(\d{2})-([A-Z]{3})-[\d.]+-(?:CALL|PUT)$", str(contract))
    if not m or m.group(2) not in MONTHS:
        return None
    d = date(today.year, MONTHS[m.group(2)], int(m.group(1)))
    return d if d >= today - timedelta(days=31) else date(today.year + 1, d.month, d.day)


def is_carried(trade: dict, today: date) -> bool:
    return trade.get("status") == "OPEN" and str(trade.get("date")) < today.isoformat()


def _own_filings(items: list[dict], symbol: str, since: str, until: str, categories=("RESULTS", "REGULATORY")) -> list[dict]:
    return [i for i in items if symbol in (i.get("symbols") or []) and i.get("kind") == "filing"
            and i.get("category") in categories and since < str(i.get("time", ""))[:16] <= until]


def should_carry(trade: dict, now: datetime, team: str, items: list[dict], results_dates: list | None,
                 next_session: date, cfg: dict | None = None) -> tuple[bool, str]:
    """(carry?, reason) at square-off time for one OPEN trade."""
    c = {**DEFAULTS, **(cfg or {})}
    today = now.date()
    if not c["enabled"] or team not in c["teams"]:
        return False, "carry off for this team"
    if not c["carry_puts"] and str(trade.get("contract", "")).endswith("-PUT"):
        return False, "PUTs are not carried"
    if str(trade.get("date")) != today.isoformat():
        return False, "already carried one night"
    exp = expiry_of(trade.get("contract", ""), today)
    if exp is None or (exp - today).days < c["min_days_to_expiry"]:
        return False, f"option expires {exp}"
    due = {str(d) for d in results_dates or []}
    if today.isoformat() in due or next_session.isoformat() in due:
        return False, "results due today or next session"
    own = _own_filings(items, trade["symbol"], f"{today} 00:00", now.strftime("%Y-%m-%d %H:%M"))
    if own:
        return False, f"own {own[0]['category'].lower()} filing today"
    return True, ""


def overnight_exit(trade: dict, items: list[dict], now: datetime) -> str | None:
    """Reason to sell a carried trade at the open, or None to keep it to target / 15:20."""
    since = f"{trade['date']} 15:20"
    own = _own_filings(items, trade["symbol"], since, now.strftime("%Y-%m-%d %H:%M"))
    if own:
        return f"overnight {own[0]['category'].lower()} filing: {own[0].get('headline', '')[:100]}"
    want = "up" if trade.get("side") == "loser" else "down"
    fresh = [i for i in items if trade["symbol"] in (i.get("symbols") or []) and str(i.get("time", ""))[:16] > since]
    view = analyzer.stock_view(trade["symbol"], fresh, now) if fresh else None
    if view and view["strong"] and view["direction"] != want:
        return f"overnight news against the trade: {(view.get('reasons') or [''])[0][:100]}"
    return None


def market_open(now: datetime, cfg: dict | None = None) -> bool:
    c = {**DEFAULTS, **(cfg or {})}
    h, m = c["open_after"].split(":")
    return now.time() >= time(int(h), int(m))
