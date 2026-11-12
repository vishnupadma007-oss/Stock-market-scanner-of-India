"""Commodities agent: MCX crude, gas, precious and base metals, and the stocks they move.

For each stock it checks whether today's commodity moves push the stock with or against the
trade. A sharp move in any commodity (a supply shock, sanctions, an OPEC cut, a mine closure)
is also reported once a day as a COMMODITY event, so Claude can look up the reason.

Sensitivity: +1 = the stock tends to gain when the commodity rises, -1 = tends to lose.
"""

COMMODITIES = ["crude oil", "natural gas", "gold", "silver", "copper", "aluminium", "zinc", "nickel"]

SENSITIVITY = {
    "crude oil": {"ONGC": 1, "BPCL": -1, "IOC": -1, "ASIANPAINT": -1},
    "natural gas": {"GAIL": 1},
    "gold": {"MUTHOOTFIN": 1},
    "silver": {"VEDL": 1},
    "copper": {"HINDALCO": 1, "VEDL": 1},
    "aluminium": {"HINDALCO": 1, "NATIONALUM": 1, "VEDL": 1},
    "zinc": {"VEDL": 1},
    "nickel": {},
}

DEFAULTS = {"move_pct": 1.5, "points": -20, "shock_pct": 3.0}


def assess(symbol: str, side: str, changes: dict[str, float | None], cfg: dict) -> dict:
    """side "gainer" = betting on a fall (PE), "loser" = betting on a rise (CE)."""
    c = {**DEFAULTS, **(cfg.get("commodities") or {})}
    want = 1 if side == "loser" else -1
    points, notes = 0, []
    for name, stocks in SENSITIVITY.items():
        sens, chg = stocks.get(symbol, 0), changes.get(name)
        if not sens or chg is None or abs(chg) < c["move_pct"]:
            continue
        if sens * (1 if chg > 0 else -1) != want:
            points += c["points"]
            notes.append(f"{name.capitalize()} {chg:+.1f}% pushes {symbol} the other way")
        else:
            notes.append(f"{name.capitalize()} {chg:+.1f}% supports the trade")
    return {"points": points, "notes": notes}


def shocks(changes: dict[str, float | None], cfg: dict) -> list[dict]:
    c = {**DEFAULTS, **(cfg.get("commodities") or {})}
    return [{"commodity": name, "change_pct": chg,
             "stocks_affected": sorted(SENSITIVITY.get(name, {}))}
            for name, chg in changes.items() if chg is not None and abs(chg) >= c["shock_pct"]]
