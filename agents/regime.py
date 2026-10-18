"""Market Regime agent: reads Nifty and India VIX to decide which side of the scan to trade.

Logic: in a rising market, beaten-down stocks tend to bounce while strong gainers keep
running, so we buy calls on top losers. In a falling market, stretched gainers tend to fade,
so we buy puts on top gainers. In a sideways market both sides are allowed.
"""
import pandas as pd


def _ret(close: pd.Series, days: int) -> float:
    return float(close.iloc[-1] / close.iloc[-1 - days] - 1) * 100 if len(close) > days else 0.0


def assess(nifty: pd.DataFrame, vix: pd.DataFrame | None, cfg: dict) -> dict:
    close = nifty["Close"]
    r1, r5, r21 = _ret(close, 1), _ret(close, 5), _ret(close, 21)
    sma20 = float(close.rolling(20).mean().iloc[-1])
    last = float(close.iloc[-1])
    vix_level = float(vix["Close"].iloc[-1]) if vix is not None and not vix.empty else None

    if r5 > 1.0 and last > sma20:
        trend = "up"
    elif r5 < -1.0 and last < sma20:
        trend = "down"
    else:
        trend = "sideways"

    notes = [f"Nifty {r1:+.2f}% today, {r5:+.2f}% 1-week, {r21:+.2f}% 1-month; "
             f"{'above' if last > sma20 else 'below'} 20-day average."]
    gainers_ok = losers_ok = True
    threshold_adj = 0

    if trend == "up":
        gainers_ok = False
        notes.append("Uptrend: gainers tend to keep running -> trade only bounces in top losers (buy CE).")
    elif trend == "down":
        losers_ok = False
        notes.append("Downtrend: losers tend to keep falling -> trade only fades in top gainers (buy PE).")
    else:
        notes.append("Sideways market: mean reversion works best; both sides allowed.")

    if abs(r1) >= cfg["trend_day_nifty_pct"]:
        threshold_adj += 10
        notes.append(f"Strong trend day ({r1:+.2f}%): counter-moves are weaker, so a higher chart score is required.")

    sides = cfg.get("sides", ["gainer", "loser"])
    if "gainer" not in sides:
        gainers_ok = False
        notes.append("Top gainers switched off in config (sides).")
    if "loser" not in sides:
        losers_ok = False
        notes.append("Top losers switched off in config (sides).")

    no_trade = False
    if vix_level is not None:
        notes.append(f"India VIX {vix_level:.1f}.")
        if vix_level > cfg["max_vix"]:
            no_trade = True
            notes.append(f"VIX above {cfg['max_vix']}: option premiums are inflated and moves are erratic -> no trades.")

    return {
        "trend": trend, "nifty_1d": r1, "nifty_1w": r5, "nifty_1m": r21, "vix": vix_level,
        "gainers_ok": gainers_ok and not no_trade, "losers_ok": losers_ok and not no_trade,
        "no_trade": no_trade, "threshold_adj": threshold_adj, "notes": notes,
    }
