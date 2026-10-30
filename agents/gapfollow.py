"""Results-gap follower (news team): on a results morning, trade WITH the opening gap.

Why: reading results figures gives the direction no better than a coin flip (49.6% over 3 years),
but the market's first reaction carries on. Our data (26 Oct 2026):
  - 1 year, 76 F&O stocks: on results days a gap of 1%+ vs Nifty kept going the same way to the
    close 61-66% of the time (2%+: 65-67%, 3%+: 67-75%); on ordinary days big gaps did the
    opposite (42-49%), which is the movers team's reversal trade.
  - 3 years of results reactions: gap-downs of 2%+ kept falling 69% (n=84), 3%+ 73% (n=48).
  - Option backtest, last 60 days: following a results-day gap at 09:30 when the first 15
    minutes agreed: 10 trades, 90% reached the target (unconfirmed gaps: 73%, fading: worse).
    Small sample: judged on paper.

Direction comes from the gap; the first 15 minutes must extend it (price beyond the open).
"""


def assess(stats: dict, nifty_stats: dict | None, min_gap_pct: float = 1.0) -> dict | None:
    """stats / nifty_stats: INDmoney entity_stats (day_open, prev_close, live_price).
    Returns the gap read, or None when there is no gap of at least `min_gap_pct` vs Nifty."""
    try:
        o, prev, live = float(stats["day_open"]), float(stats["prev_close"]), float(stats["live_price"])
    except (KeyError, TypeError, ValueError):
        return None
    if not (o > 0 and prev > 0):
        return None
    n_gap = 0.0
    if nifty_stats and nifty_stats.get("day_open") and nifty_stats.get("prev_close"):
        n_gap = (float(nifty_stats["day_open"]) / float(nifty_stats["prev_close"]) - 1) * 100
    gap = (o / prev - 1) * 100 - n_gap
    if abs(gap) < min_gap_pct:
        return None
    sign = 1 if gap > 0 else -1
    since_open = (live / o - 1) * 100
    return {"direction": "up" if sign > 0 else "down", "gap_pct": round(gap, 2),
            "since_open_pct": round(since_open, 2), "confirmed": since_open * sign > 0}
