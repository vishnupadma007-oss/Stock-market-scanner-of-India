"""Risk manager: plain code, not an LLM. It sizes every trade and can veto it.

- All money is counted after charges (charges.py): a trade must still be worth taking once
  brokerage, STT, GST, stamp duty and the rest are paid.
- The 1% daily target is chased, never forced: once today's net profit reaches it, no new trades
  open, and nothing gets bigger to "catch up" on a bad day.
- Arjun's emotions can only shrink positions: a hurt trader trades smaller, a trader on a hot
  streak is held back from overconfidence, and three losses in a day means done until tomorrow.
"""

import math
from dataclasses import dataclass

from charges import breakeven_move_pct, trade_charges


@dataclass
class Limits:
    capital: float = 100_000.0          # start-of-day equity; set by the agent each day
    mode: str = "intraday"              # "intraday" (MIS) or "swing" (CNC)
    daily_target_pct: float = 1.0       # net of charges
    risk_per_trade_pct: float = 0.5     # max net loss if a stop is hit, % of capital
    daily_loss_limit_pct: float = 1.5   # stop opening trades after losing this much (net) today
    max_position_pct: float = 25.0      # max value of one position, % of capital
    max_exposure_pct: float = 100.0     # all open positions together; 100 = no leverage
    max_open_positions: int = 4
    min_reward_risk: float = 1.5        # net of charges
    max_charges_share_pct: float = 25.0 # charges may eat at most this share of the gross target profit
    min_conviction: int = 3
    max_stop_distance_pct: float = 3.0  # intraday; swing allows 3x
    max_entry_gap_pct: float = 1.0      # entry must be near the current price

    @property
    def product(self):
        return "MIS" if self.mode == "intraday" else "CNC"

    @property
    def target_rupees(self):
        return self.capital * self.daily_target_pct / 100

    def describe(self):
        stop = self.max_stop_distance_pct * (1 if self.mode == "intraday" else 3)
        return (f"- Mode {self.mode} ({self.product}); start-of-day capital ₹{self.capital:,.0f}; daily target "
                f"{self.daily_target_pct}% net = ₹{self.target_rupees:,.0f}. Once hit, no new trades today.\n"
                f"- Risk per trade {self.risk_per_trade_pct}% of capital (net of charges); no new trades after a "
                f"{self.daily_loss_limit_pct}% net loss in a day\n"
                f"- Max position {self.max_position_pct}% of capital, total exposure {self.max_exposure_pct}%, "
                f"max {self.max_open_positions} open positions\n"
                f"- Net reward:risk at least {self.min_reward_risk}; charges at most {self.max_charges_share_pct}% of "
                f"gross profit at target; conviction at least {self.min_conviction}; stop within {stop}% of entry; "
                f"entry within {self.max_entry_gap_pct}% of the last price\n"
                + ("- Swing mode: longs only\n" if self.mode == "swing" else "- Intraday: longs and shorts; all squared off by 15:10\n")
                + "- Arjun's emotional state scales size down: wounded = no new trades, rattled = half size, "
                  "riding high = 75% size")


EMOTION_SIZE = {"wounded": 0.0, "rattled": 0.5, "riding high": 0.75}


def money_brief(limits, realized_today, snapshot, symbols):
    """What the Strategist and Arjun are told about money: target, progress, and break-even moves."""
    lines = [f"Daily target: {limits.daily_target_pct}% net = ₹{limits.target_rupees:,.0f}. "
             f"Net P&L so far today: ₹{realized_today:,.0f}. Still needed: "
             f"₹{max(limits.target_rupees - realized_today, 0):,.0f}.",
             f"Product: {limits.product}. Break-even move per round trip for a full-size position "
             f"({limits.max_position_pct}% of capital):"]
    for s in symbols:
        if s in snapshot:
            px = snapshot[s]["last_price"]
            qty = math.floor(limits.capital * limits.max_position_pct / 100 / px)
            lines.append(f"  {s}: {breakeven_move_pct(px, qty, limits.product)}% (₹{px}, {qty} shares)")
    return "\n".join(lines)


def review(decisions, snapshot, portfolio, emotions, limits, realized_today):
    """Return (orders, rejections). Orders are dicts ready for the broker."""
    orders, rejected = [], []
    held = dict(portfolio["positions"])
    open_count = len(held)
    exposure = sum(p["qty"] * p.get("avg_price", 0) for p in held.values())
    cash = portfolio["cash"]
    mood = emotions.mood
    mood_mult = EMOTION_SIZE.get(mood, 1.0)
    cap = limits.capital
    stop_cap = limits.max_stop_distance_pct * (1 if limits.mode == "intraday" else 3)

    def reject(d, why):
        rejected.append({"symbol": d.get("symbol"), "action": d.get("action"), "reason": why})

    # Exits first, so they free up slots and capital for new trades.
    for d in sorted(decisions, key=lambda d: (d.get("action") or "").upper() != "EXIT"):
        sym, action = d.get("symbol"), (d.get("action") or "").upper()
        if action == "EXIT":
            if sym not in held:
                reject(d, "not held")
                continue
            p = held.pop(sym)
            orders.append({"action": "EXIT", "symbol": sym, "qty": p["qty"], "reason": d.get("rationale", "")})
            open_count -= 1
            exposure -= p["qty"] * p.get("avg_price", 0)
            continue
        if action not in ("BUY", "SHORT"):
            continue
        side = "LONG" if action == "BUY" else "SHORT"
        if side == "SHORT" and limits.mode != "intraday":
            reject(d, "shorts are intraday only")
            continue
        if sym in held:
            reject(d, "already in a position; no averaging")
            continue
        if sym not in snapshot:
            reject(d, "no price data")
            continue
        if realized_today >= limits.target_rupees:
            reject(d, f"daily target already reached (₹{realized_today:,.0f} net); protecting the day")
            continue
        if realized_today <= -cap * limits.daily_loss_limit_pct / 100:
            reject(d, f"daily loss limit hit (₹{realized_today:,.0f} net today)")
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
        if side == "LONG" and not stop < entry < target:
            reject(d, "a long needs stop_loss < entry < target")
            continue
        if side == "SHORT" and not target < entry < stop:
            reject(d, "a short needs target < entry < stop_loss")
            continue
        last = snapshot[sym]["last_price"]
        if abs(entry / last - 1) * 100 > limits.max_entry_gap_pct:
            reject(d, f"entry {entry} is too far from last price {last}")
            continue
        risk_ps, reward_ps = abs(entry - stop), abs(target - entry)
        if risk_ps / entry * 100 > stop_cap:
            reject(d, f"stop-loss wider than {stop_cap}%")
            continue
        if conviction < limits.min_conviction:
            reject(d, f"conviction {conviction} below {limits.min_conviction}")
            continue

        # Size so that a stopped-out trade, charges included, loses at most the risk budget.
        size_mult = mood_mult * min(conviction, 5) / 5
        budget = cap * limits.risk_per_trade_pct / 100 * size_mult
        qty = math.floor(budget / risk_ps)
        qty = min(qty, math.floor(cap * limits.max_position_pct / 100 / entry),
                  math.floor((cap * limits.max_exposure_pct / 100 - exposure) / entry), math.floor(cash / entry))
        for _ in range(20):
            if qty < 1:
                break
            loss_net = qty * risk_ps + trade_charges(side, qty, entry, stop, limits.product)["total"]
            if loss_net <= budget:
                break
            qty = max(qty - max(1, qty // 20), 0)
        if qty < 1:
            reject(d, "position size rounds to zero after charges, limits and available capital")
            continue
        win_charges = trade_charges(side, qty, entry, target, limits.product)["total"]
        loss_charges = trade_charges(side, qty, entry, stop, limits.product)["total"]
        gross_win = qty * reward_ps
        net_win, net_loss = gross_win - win_charges, qty * risk_ps + loss_charges
        if win_charges > gross_win * limits.max_charges_share_pct / 100:
            reject(d, f"charges ₹{win_charges:,.0f} would eat {100 * win_charges / gross_win:.0f}% of the "
                      f"₹{gross_win:,.0f} gross profit")
            continue
        rr = net_win / net_loss
        if rr < limits.min_reward_risk:
            reject(d, f"net reward:risk {rr:.2f} below {limits.min_reward_risk} after charges")
            continue

        cash -= qty * entry
        exposure += qty * entry
        open_count += 1
        orders.append({"action": action, "side": side, "symbol": sym, "qty": qty, "entry": round(entry, 2),
                       "stop_loss": round(stop, 2), "target": round(target, 2), "product": limits.product,
                       "net_win": round(net_win, 2), "net_loss": round(net_loss, 2),
                       "charges_at_target": round(win_charges, 2), "net_reward_risk": round(rr, 2),
                       "size_note": f"conviction {conviction}/5, mood '{mood}' x{mood_mult}",
                       "reason": d.get("rationale", "")})
    return orders, rejected
