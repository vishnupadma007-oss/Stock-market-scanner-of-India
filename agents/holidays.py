"""NSE trading holidays, so nothing runs on days the exchange is closed.

The list comes from NSE's public holiday API and is saved to journal/nse_holidays.json, which
is committed: if NSE cannot be reached, the saved list is used.
"""
import json
from datetime import date, datetime, timedelta
from pathlib import Path

import requests

SAVED = Path(__file__).resolve().parent.parent / "journal" / "nse_holidays.json"
URL = "https://www.nseindia.com/api/holiday-master?type=trading"


def refresh() -> dict[str, str]:
    """Download NSE's cash-market holidays ({YYYY-MM-DD: name}) and save them."""
    resp = requests.get(URL, timeout=20, headers={"User-Agent": "Mozilla/5.0",
                                                  "Referer": "https://www.nseindia.com/"})
    resp.raise_for_status()
    rows = resp.json().get("CM", [])
    holidays = {datetime.strptime(r["tradingDate"], "%d-%b-%Y").date().isoformat(): r["description"]
                for r in rows}
    SAVED.parent.mkdir(exist_ok=True)
    SAVED.write_text(json.dumps(holidays, indent=1, sort_keys=True))
    return holidays


def load() -> dict[str, str]:
    try:
        return json.loads(SAVED.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        try:
            return refresh()
        except Exception:
            return {}


def holiday_name(day: date, holidays: dict[str, str] | None = None) -> str | None:
    """Why NSE is shut on `day` ("Weekend", a holiday name), or None on a trading day."""
    if day.weekday() >= 5:
        return "Weekend"
    return (load() if holidays is None else holidays).get(day.isoformat())


def is_trading_day(day: date, holidays: dict[str, str] | None = None) -> bool:
    return holiday_name(day, holidays) is None


def previous_trading_day(day: date, holidays: dict[str, str] | None = None) -> date:
    while not is_trading_day(day, holidays):
        day -= timedelta(days=1)
    return day
