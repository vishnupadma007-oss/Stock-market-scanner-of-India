"""Risk manager: plain code, not an LLM. It sizes every trade and can veto it.

Arjun's emotions can only shrink positions here, never grow them: a hurt trader trades smaller,
a trader on a hot streak is held back from getting overconfident, and three losses in a row
in a day means no new trades until tomorrow.
"""

import math
from dataclasses import dataclass


@dataclass
class Limits:
    capital: float = 100_000.0
    risk_per_trade_pct: float = 1.0     # max loss if the stop-loss is hit, as % of capital
    max_position_pct: float = 20.0      # max value of one position, as % of capital
    max_open_positions: int = 5
    daily_loss_limit_pct: float = 2.0   # stop opening trades after losing this much today
    min_reward_risk: float = 1.5
    min_conviction: int = 3
    max_stop_distance_pct: float = 10.0
    max_entry_gap_pct: float = 2.0      # entry must be close to the current price

    def describe(self):
        return (f"- Capital ₹{self.capital:,.0f}; risk per trade {self.risk_per_trade_pct}% of capital; "
                f"max position {self.max_position_pct}% of capital; max {self.max_open_positions} open positions\n"
                f"- No new trades after a {self.daily_loss_limit_pct}% loss in a day\n"
                f"- Reward:risk at least {self.min_reward_risk}; conviction at least {self.min_conviction}; "
                f"stop no further than {self.max_stop_distance_pct}% from entry; entry within "
                f"{self.max_entry_gap_pct}% of the last price\n"
                "- Your emotional state scales size down: wounded = no new trades, rattled = half size, "
                "riding high = 75% size")


EMOTION_SIZE = {"wounded": 0.0, "rattled": 0.5, "riding high": 0.75}


def review(decisions, snapshot, portfolio, emotions, limits, realized_today):
    """Return (orders, rejections). Orders are dicts ready for the broker."""
    orders, rejected = [], []
    held = portfolio["positions"]
    open_count = len(held)
    cash = portfolio["cash"]
    mood = emotions.mood
    mood_mult = EMOTION_SIZE.get(mood, 1.0)
    day_stop = realized_today <= -limits.capital * limits.daily_loss_limit_pct / 100

    def reject(d, why):
        rejected.append({"symbol": d.get("symbol"), "action": d.get("action"), "reason": why})

    # Exits first, so they free up slots and cash for new trades.
    ordered = sorted(decisions, key=lambda d: d.get("action") != "EXIT")
    for d in ordered:
        sym, action = d.get("symbol"), (d.get("action") or "").upper()
        if action == "EXIT":
            if sym not in held:
                reject(d, "not held")
                continue
            orders.append({"side": "SELL", "symbol": sym, "qty": held[sym]["qty"], "reason": d.get("rationale", "")})
            open_count -= 1
            continue
        if action != "BUY":
            continue
        if sym in held:
            reject(d, "already held; no averaging up or down")
            continue
        if sym not in snapshot:
            reject(d, "no price data")
            continue
        if day_stop:
            reject(d, f"daily loss limit hit (₹{realized_today:,.0f} today)")
            continue
        if mood_mult == 0:
            reject(d, f"Arjun is {mood} (losses today {emotions.s['losses_today']}, frustration "
                      f"{emotions.s['frustration']}); cooling off, no new trades")
            continue
        if open_count >= limits.max_open_positions:
            reject(d, "max open positions reached")
            continue
        try:
            entry, stop, target = float(d["entry"]), float(d["stop_loss"]), float(d["target"])
            conviction = int(d.get("conviction", 0))
        except (KeyError, TypeError, ValueError):
            reject(d, "missing or invalid entry / stop_loss / target")
            continue
        last = snapshot[sym]["last_price"]
        if not stop < entry < target:
            reject(d, "needs stop_loss < entry < target")
            continue
        if abs(entry / last - 1) * 100 > limits.max_entry_gap_pct:
            reject(d, f"entry {entry} is too far from last price {last}")
            continue
        risk_per_share = entry - stop
        if risk_per_share / entry * 100 > limits.max_stop_distance_pct:
            reject(d, "stop-loss too wide")
            continue
        rr = (target - entry) / risk_per_share
        if rr < limits.min_reward_risk:
            reject(d, f"reward:risk {rr:.2f} below {limits.min_reward_risk}")
            continue
        if conviction < limits.min_conviction:
            reject(d, f"conviction {conviction} below {limits.min_conviction}")
            continue

        size_mult = mood_mult * min(conviction, 5) / 5
        risk_budget = limits.capital * limits.risk_per_trade_pct / 100 * size_mult
        qty = math.floor(risk_budget / risk_per_share)
        qty = min(qty, math.floor(limits.capital * limits.max_position_pct / 100 / entry), math.floor(cash / entry))
        if qty < 1:
            reject(d, "position size rounds to zero (not enough capital or cash for this stop distance)")
            continue
        cash -= qty * entry
        open_count += 1
        orders.append({"side": "BUY", "symbol": sym, "qty": qty, "entry": round(entry, 2),
                       "stop_loss": round(stop, 2), "target": round(target, 2),
                       "risk_rupees": round(qty * risk_per_share, 2), "reward_risk": round(rr, 2),
                       "size_note": f"conviction {conviction}/5, mood '{mood}' x{mood_mult}",
                       "reason": d.get("rationale", "")})
    return orders, rejected
