"""Day mode from Claude's morning brief: normal / careful / no_trade, plus stocks to avoid.

Claude writes journal/day_mode.json each morning after checking global markets, crude,
geopolitics and today's events. The watcher reads it every cycle; a file from another day
is ignored (normal mode).
"""
import json
from datetime import date
from pathlib import Path

PATH = Path(__file__).resolve().parent.parent / "journal" / "day_mode.json"
NORMAL = {"mode": "normal", "notes": [], "avoid": []}


def load(today: date, path: Path = PATH) -> dict:
    try:
        data = json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return dict(NORMAL)
    if data.get("date") != today.isoformat():
        return dict(NORMAL)
    return {**NORMAL, **data}


def apply(cfg: dict, day: dict) -> dict:
    """Config for today: careful mode needs a stronger chart and allows only one trade."""
    if day["mode"] == "careful":
        return {**cfg, "min_chart_score": cfg["min_chart_score"] + 10,
                "max_trades_per_day": min(1, cfg["max_trades_per_day"])}
    return cfg
