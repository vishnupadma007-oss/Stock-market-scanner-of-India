"""Macro agent: does the stock's move come from its sector, crude oil or the rupee?

A loser that is only falling because its whole sector is falling, or a refiner falling while
crude spikes, has a reason to keep going: that is not the overreaction this strategy trades.
Returns score points to add to the chart score, plus plain-language notes.
"""
from .sectors import CRUDE_SENSITIVITY, RUPEE_SENSITIVITY, sector_of

DEFAULTS = {
    "sector_trend_pct": 1.5,     # sector index move that counts as "the whole sector is moving"
    "sector_points": -15,        # stock moving with a strongly trending sector
    "stock_specific_points": 5,  # move is mostly the stock's own (sector calm)
    "crude_move_pct": 1.5,       # crude move that matters for oil-sensitive stocks
    "crude_points": -20,         # trade goes against what crude implies
    "rupee_move_pct": 0.4,       # USD/INR move that matters for exporters
    "rupee_points": -10,
}


def assess(symbol: str, side: str, stock_chg: float, sector_chg: float | None,
           crude_chg: float | None, usdinr_chg: float | None, cfg: dict) -> dict:
    """side "gainer" means we bet on a fall (PE); "loser" means we bet on a rise (CE).
    All changes are today's % moves."""
    c = {**DEFAULTS, **(cfg.get("macro") or {})}
    sector = sector_of(symbol)
    want = 1 if side == "loser" else -1  # direction the trade needs the stock to move
    move = 1 if stock_chg > 0 else -1
    points, notes = 0, []

    if sector_chg is not None and sector != "Market":
        if sector_chg * move >= c["sector_trend_pct"]:
            points += c["sector_points"]
            notes.append(f"Moving with its sector ({sector} {sector_chg:+.1f}%): a sector-wide move "
                         f"is less likely to reverse")
        elif abs(sector_chg) < abs(stock_chg) * 0.3:
            points += c["stock_specific_points"]
            notes.append(f"Stock-specific move ({sector} only {sector_chg:+.1f}%)")

    sens = CRUDE_SENSITIVITY.get(symbol, 0)
    if sens and crude_chg is not None and abs(crude_chg) >= c["crude_move_pct"]:
        implied = sens * (1 if crude_chg > 0 else -1)
        if implied != want:
            points += c["crude_points"]
            notes.append(f"Crude {crude_chg:+.1f}% pushes this stock the other way")
        else:
            notes.append(f"Crude {crude_chg:+.1f}% supports the trade")

    sens = RUPEE_SENSITIVITY.get(symbol, 0)
    if sens and usdinr_chg is not None and abs(usdinr_chg) >= c["rupee_move_pct"]:
        implied = sens * (1 if usdinr_chg > 0 else -1)
        if implied != want:
            points += c["rupee_points"]
            notes.append(f"Rupee move (USD/INR {usdinr_chg:+.2f}%) works against the trade")

    return {"points": points, "notes": notes, "sector": sector}
