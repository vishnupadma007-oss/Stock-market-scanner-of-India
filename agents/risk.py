"""Risk Manager agent: sizing, trade limits, timing and the exit plan. It has veto power."""
import math
from datetime import datetime, time

from .costs import exit_for_net_target, round_trip_charges


def _t(hhmm: str) -> time:
    h, m = hhmm.split(":")
    return time(int(h), int(m))


def hit_probability(move: float, sigma_per_min: float, minutes_left: float) -> float:
    """Chance the stock touches a level `move` rupees away before time runs out.

    Uses the reflection principle for a driftless random walk: P = 2 * (1 - N(move / (sigma * sqrt(t)))).
    It assumes no edge in direction, so it is a conservative forecast for a reversal setup.
    """
    if minutes_left <= 0 or sigma_per_min <= 0:
        return 0.0
    z = move / (sigma_per_min * math.sqrt(minutes_left))
    return min(1.0, 2 * (1 - 0.5 * (1 + math.erf(z / math.sqrt(2)))))


def plan(option: dict, trades_today: int, now: datetime, cfg: dict,
         sigma_per_min: float = 0.0, spread_pct: float | None = None,
         forecast: dict | None = None) -> dict:
    blocks = []
    if trades_today >= cfg["max_trades_per_day"]:
        blocks.append(f"Daily limit reached ({cfg['max_trades_per_day']} trades).")
    if not _t(cfg["entry_start"]) <= now.time() <= _t(cfg["entry_end"]):
        blocks.append(f"Outside entry window {cfg['entry_start']}-{cfg['entry_end']} IST.")

    premium, lot = option["est_premium"], option["lot_size"]
    budget = cfg["capital"] * cfg["max_capital_per_trade"]
    if lot:
        lots = int(budget // (premium * lot))
        if lots < 1:
            blocks.append(f"One lot costs ₹{premium * lot:,.0f}, above the ₹{budget:,.0f} per-trade budget.")
            lots = 1
        qty = lots * lot
    else:
        lots, qty = None, max(int(budget // premium), 1)

    target = exit_for_net_target(premium, qty, cfg["net_target_pct"], cfg["charges"])
    # You buy at the ask and sell at the bid, so the option's price must also cover the spread.
    spread_pct = cfg["assumed_spread_pct"] if spread_pct is None else spread_pct
    spread_cost = premium * spread_pct / 100

    # Forecast: option price if the stock reaches the forecast reversal level.
    forecast_premium = None
    if forecast and forecast.get("level") is not None and option["delta"]:
        forecast_premium = premium + abs(option["delta"]) * forecast["move"] - spread_cost
        if cfg.get("target_mode") == "forecast":
            # Aim for part of the forecast move, never below the minimum net target.
            aim = round(premium + cfg.get("forecast_capture", 0.7) * (forecast_premium - premium), 1)
            if aim > target["exit_premium"]:
                charges = round_trip_charges(premium, aim, qty, cfg["charges"])
                target = {"exit_premium": aim, "gross_move_pct": (aim / premium - 1) * 100,
                          "charges": charges, "net_profit": (aim - premium) * qty - charges["total"]}

    premium_move = target["exit_premium"] - premium + spread_cost
    # Underlying move needed for the option to reach the target premium (delta approximation).
    underlying_move = premium_move / abs(option["delta"]) if option["delta"] else None

    square_off = datetime.combine(now.date(), _t(cfg["square_off_time"]), now.tzinfo)
    minutes_left = (square_off - now).total_seconds() / 60
    prob = hit_probability(underlying_move or 0, sigma_per_min, minutes_left) * 100
    if sigma_per_min and prob < cfg["min_hit_probability"]:
        blocks.append(f"Forecast chance of reaching the target is {prob:.0f}% "
                      f"(need {cfg['min_hit_probability']}%).")

    if forecast is not None and cfg.get("forecast_filter", True):
        if forecast.get("level") is None:
            blocks.append(f"Forecast: {forecast['basis']}.")
        elif underlying_move and forecast["move"] < underlying_move:
            blocks.append(f"Forecast reversal to {forecast['basis']} (₹{forecast['level']:.2f}, "
                          f"₹{forecast['move']:.2f} away) is smaller than the ₹{underlying_move:.2f} move needed.")

    return {
        "allowed": not blocks, "forecast": forecast, "forecast_premium": forecast_premium, "blocks": blocks, "lots": lots, "qty": qty,
        "capital_used": premium * qty, "entry_premium": premium,
        "target_premium": target["exit_premium"], "gross_move_pct": target["gross_move_pct"],
        "charges": target["charges"], "net_profit": target["net_profit"],
        "underlying_move": underlying_move, "spread_pct": spread_pct,
        "hit_probability": prob, "minutes_left": minutes_left,
        "square_off": cfg["square_off_time"],
    }
