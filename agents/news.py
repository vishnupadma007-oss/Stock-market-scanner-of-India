"""News & Events agent: is there a real reason behind today's move?

Checks three things before a trade:
1. Results: results today or announced yesterday evening -> the move is earnings-driven, skip.
   Results due tomorrow -> event risk, lower score.
2. Fresh news (INDmoney headlines with sentiment, dated today or yesterday) that agrees with
   the move -> a real catalyst, so the move is less likely to reverse.
3. Sudden pressure: a burst of volume in the last few candles still pushing in the move's
   direction, the footprint of news hitting the stock right now.
"""
import re
from datetime import date, datetime, timedelta

import pandas as pd
import requests

from .holidays import is_trading_day

DEFAULTS = {
    "block_results_day": True,
    "results_tomorrow_points": -10,
    "fresh_news_points": -25,     # news agreeing with the move (real catalyst)
    "no_news_points": 5,          # no news: more likely an overreaction
    "volume_spike_ratio": 3.0,    # last 3 candles' volume vs normal
    "volume_spike_points": -15,
    "filing_points": -15,         # material NSE filing today (rating, order, deal, regulatory...)
}
_DATE = re.compile(r"(\d{1,2} [A-Za-z]{3},? \d{4})\s*$")


def headline_date(title: str) -> date | None:
    m = _DATE.search(title)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1).replace(",", ""), "%d %b %Y").date()
    except ValueError:
        return None


def previous_session(day: date) -> date:
    prev = day - timedelta(days=1)
    while not is_trading_day(prev):
        prev -= timedelta(days=1)
    return prev


def next_session(day: date) -> date:
    nxt = day + timedelta(days=1)
    while not is_trading_day(nxt):
        nxt += timedelta(days=1)
    return nxt


def results_calendar() -> dict[str, list[date]]:
    """Upcoming board meetings for financial results, from NSE's public event calendar.
    Returns {} if NSE is unreachable (the agent then says results were not checked)."""
    # Without dates NSE lists only future days: today's companies were missing (23 Oct: Infosys,
    # Dr Reddy's, IndusInd... all reporting that day). Ask from yesterday to six weeks ahead.
    start, end = date.today() - timedelta(days=1), date.today() + timedelta(days=42)
    try:
        resp = requests.get("https://www.nseindia.com/api/event-calendar", timeout=15,
                            params={"index": "equities", "from_date": f"{start:%d-%m-%Y}", "to_date": f"{end:%d-%m-%Y}"},
                            headers={"User-Agent": "Mozilla/5.0", "Referer": "https://www.nseindia.com/"})
        resp.raise_for_status()
        rows = resp.json()
    except Exception:
        return {}
    cal: dict[str, list[date]] = {}
    for r in rows:
        if "result" in str(r.get("purpose", "")).lower():
            try:
                cal.setdefault(r["symbol"], []).append(datetime.strptime(r["date"], "%d-%b-%Y").date())
            except (KeyError, ValueError):
                continue
    return cal


def volume_spike(intraday: pd.DataFrame, bars: int = 3) -> tuple[float, float]:
    """(ratio of the last `bars` candles' volume to normal, price change over those candles %)."""
    if len(intraday) < bars + 10:
        return 0.0, 0.0
    recent = intraday.tail(bars)
    normal = intraday["Volume"].iloc[-(bars + 75):-bars].median()
    ratio = float(recent["Volume"].mean() / normal) if normal else 0.0
    change = float(recent["Close"].iloc[-1] / recent["Open"].iloc[0] - 1) * 100
    return ratio, change


def assess(symbol: str, side: str, stock_chg: float, today: date, headlines: list[dict] | None,
           results: dict[str, list[date]] | None, intraday: pd.DataFrame, cfg: dict,
           filings: list[dict] | None = None) -> dict:
    """filings: today's material NSE announcements for this stock (Announcements agent)."""
    c = {**DEFAULTS, **(cfg.get("news") or {})}
    move = 1 if stock_chg > 0 else -1
    points, notes, block = 0, [], False

    for f in filings or []:
        if f["category"] == "RESULTS":
            block = c["block_results_day"]
            notes.append(f"Results filed on NSE at {f['time'][11:16]}: earnings-driven move")
        else:
            points += c.get("filing_points", -15)
            notes.append(f"NSE filing today ({f['category'].lower()}): {f['text'][:120]}")

    if results is None or not results:
        notes.append("Results calendar not checked")
    else:
        dates = results.get(symbol, [])
        if today in dates or previous_session(today) in dates:
            notes.append("Results today/yesterday: earnings-driven move")
            block = c["block_results_day"]
        elif next_session(today) in dates:
            points += c["results_tomorrow_points"]
            notes.append("Results due tomorrow: event risk")

    if headlines is None:
        notes.append("News not checked")
    else:
        fresh = [h for h in headlines if headline_date(h.get("title", "")) in (today, previous_session(today))]
        agreeing = [h for h in fresh if {"positive": 1, "negative": -1}.get(h.get("sentiment"), 0) == move]
        if agreeing:
            points += c["fresh_news_points"]
            notes.append(f"Fresh {agreeing[0]['sentiment']} news behind the move: \"{agreeing[0]['title']}\"")
        elif fresh:
            notes.append(f"Fresh news, but it does not explain the move: \"{fresh[0]['title']}\"")
        else:
            points += c["no_news_points"]
            notes.append("No fresh news: likely an overreaction")

    ratio, change = volume_spike(intraday)
    if ratio >= c["volume_spike_ratio"] and change * move > 0:
        points += c["volume_spike_points"]
        notes.append(f"Sudden pressure: last 15 min volume {ratio:.1f}x normal and still pushing "
                     f"{'up' if move > 0 else 'down'}")

    return {"points": points, "notes": notes, "block": block,
            "news_driven": any("Fresh" in n and "behind" in n for n in notes)}
