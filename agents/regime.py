"""Market Regime agent: reads Nifty and India VIX to decide which side of the scan to trade.

Logic:
- In an uptrending market, strong gainers tend to keep running, so we only trade bounces in top losers (buy CE).
- In a downtrending market, losers tend to keep falling, so we only trade fades in top gainers (buy PE).
- In a sideways market, mean reversion works best on both sides.
- On strong trend days (Nifty >= trend_day_nifty_pct), threshold is adjusted higher (+10 pts) for counter-moves.
- When India VIX exceeds max_vix, trading is halted due to unpredictable moves and inflated option premiums.
"""
import pandas as pd


def _ret(close: pd.Series, days: int) -> float:
    if len(close) <= days:
        return 0.0
    val_prev = float(close.iloc[-1 - days])
    if val_prev <= 0:
        return 0.0
    return float(close.iloc[-1] / val_prev - 1.0) * 100.0


def assess(nifty: pd.DataFrame, vix: pd.DataFrame | None, cfg: dict) -> dict:
    close = nifty["Close"]
    r1 = _ret(close, 1)
    r5 = _ret(close, 5)
    r21 = _ret(close, 21)

    # Rolling 20-day SMA with graceful fallback if fewer than 20 rows
    roll_len = min(len(close), 20)
    sma20 = float(close.tail(roll_len).mean()) if roll_len > 0 else float(close.iloc[-1])
    last = float(close.iloc[-1])

    vix_level = float(vix["Close"].iloc[-1]) if vix is not None and not vix.empty else None
    vix_chg_1d = _ret(vix["Close"], 1) if vix is not None and len(vix) >= 2 else None

    # Trend classification
    if r5 > 1.0 and last > sma20:
        trend = "up"
    elif r5 < -1.0 and last < sma20:
        trend = "down"
    else:
        trend = "sideways"

    notes = [
        f"Nifty {r1:+.2f}% today, {r5:+.2f}% 1-week, {r21:+.2f}% 1-month; "
        f"{'above' if last >= sma20 else 'below'} 20-day average."
    ]
    gainers_ok = True
    losers_ok = True
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
    vix_regime = "normal"
    if vix_level is not None:
        if vix_level < 13.0:
            vix_regime = "calm"
        elif vix_level <= 18.0:
            vix_regime = "normal"
        elif vix_level <= cfg["max_vix"]:
            vix_regime = "elevated"
        else:
            vix_regime = "panic"

        chg_note = f" ({vix_chg_1d:+.1f}% today)" if vix_chg_1d is not None else ""
        notes.append(f"India VIX {vix_level:.1f}{chg_note} [{vix_regime}].")

        if vix_level > cfg["max_vix"]:
            no_trade = True
            notes.append(f"VIX above {cfg['max_vix']}: option premiums are inflated and moves are erratic -> no trades.")

    return {
        "trend": trend,
        "nifty_1d": round(r1, 2),
        "nifty_1w": round(r5, 2),
        "nifty_1m": round(r21, 2),
        "vix": round(vix_level, 2) if vix_level is not None else None,
        "vix_regime": vix_regime,
        "vix_1d": round(vix_chg_1d, 2) if vix_chg_1d is not None else None,
        "gainers_ok": gainers_ok and not no_trade,
        "losers_ok": losers_ok and not no_trade,
        "no_trade": no_trade,
        "threshold_adj": threshold_adj,
        "notes": notes,
    }
