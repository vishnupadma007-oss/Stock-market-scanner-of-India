"""Risk Manager agent: sizing, trade limits, timing and the exit plan. It has veto power."""
from datetime import datetime, time

from .costs import exit_for_net_target


def _t(hhmm: str) -> time:
    h, m = hhmm.split(":")
    return time(int(h), int(m))


def plan(option: dict, trades_today: int, now: datetime, cfg: dict) -> dict:
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
    # Underlying move needed for the option to reach the target premium (delta approximation).
    underlying_move = (target["exit_premium"] - premium) / abs(option["delta"]) if option["delta"] else None

    emergency = None
    if cfg.get("emergency_exit_pct"):
        emergency = round(premium * (1 - cfg["emergency_exit_pct"] / 100), 1)

    return {
        "allowed": not blocks, "blocks": blocks, "lots": lots, "qty": qty,
        "capital_used": premium * qty, "entry_premium": premium,
        "target_premium": target["exit_premium"], "gross_move_pct": target["gross_move_pct"],
        "charges": target["charges"], "net_profit": target["net_profit"],
        "underlying_move": underlying_move, "emergency_exit": emergency,
        "square_off": cfg["square_off_time"],
    }
