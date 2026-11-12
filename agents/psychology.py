"""Crowd Psychology agent: what is the crowd doing behind today's move?

Behavioral-finance ideas (overreaction, herding, anchoring, trapped traders) turned into
things we can measure on NSE F&O stocks:

1. Futures open interest vs price (who is behind the move):
   up   + OI up   = long build-up:  fresh buyers with conviction  -> a fade is risky
   up   + OI down = short covering: trapped sellers rushing out    -> often fizzles, good fade
   down + OI up   = short build-up: fresh sellers with conviction  -> a bounce is risky
   down + OI down = long unwinding: holders giving up (panic exit) -> often exhausts, good bounce
2. Herding at extremes: a stock at its 52-week high/low draws breakout traders and stop
   orders, so the move tends to extend before it reverses.
3. Frenzy: near the upper/lower circuit the crowd is one-sided and the stock can freeze.

No free history of open interest exists, so this cannot be backtested. In "observe" mode it
only records its readings (shown on signals, logged, compared in the evening review); in
"score" mode its points count in the decision.
"""

DEFAULTS = {
    "mode": "observe",          # "observe" (record only) or "score"
    "oi_change_pct": 2.0,       # OI change that counts as real build-up/unwinding
    "conviction_points": -15,   # long build-up on a gainer / short build-up on a loser
    "trapped_points": 10,       # short covering on a gainer / long unwinding on a loser
    "extreme_pct": 1.0,         # within this % of the 52-week high/low
    "extreme_points": -10,
    "circuit_pct": 2.0,         # within this % of the circuit limit -> skip
}


def oi_type(price_chg: float, oi_chg: float, threshold: float) -> str:
    if abs(oi_chg) < threshold:
        return "no clear OI change"
    if price_chg > 0:
        return "long build-up" if oi_chg > 0 else "short covering"
    return "short build-up" if oi_chg > 0 else "long unwinding"


def assess(side: str, price: float, stock_chg: float, fut_oi_chg: float | None,
           week52_high: float | None, week52_low: float | None,
           upper_circuit: float | None, lower_circuit: float | None, cfg: dict) -> dict:
    c = {**DEFAULTS, **(cfg.get("psychology") or {})}
    points, notes, block = 0, [], False

    kind = oi_type(stock_chg, fut_oi_chg, c["oi_change_pct"]) if fut_oi_chg is not None else "OI not checked"
    if kind in ("long build-up", "short build-up"):
        points += c["conviction_points"]
        notes.append(f"{kind.capitalize()} (futures OI {fut_oi_chg:+.1f}%): fresh positions with conviction "
                     f"behind the move")
    elif kind in ("short covering", "long unwinding"):
        points += c["trapped_points"]
        notes.append(f"{kind.capitalize()} (futures OI {fut_oi_chg:+.1f}%): trapped traders exiting, "
                     f"the move often runs out of fuel")

    if side == "gainer" and week52_high and price >= week52_high * (1 - c["extreme_pct"] / 100):
        points += c["extreme_points"]
        notes.append("At its 52-week high: breakout buyers tend to pile in")
    if side == "loser" and week52_low and price <= week52_low * (1 + c["extreme_pct"] / 100):
        points += c["extreme_points"]
        notes.append("At its 52-week low: panic sellers tend to pile in")

    circuit = upper_circuit if side == "gainer" else lower_circuit
    if circuit and abs(circuit - price) / price * 100 <= c["circuit_pct"]:
        block = True
        notes.append(f"Within {c['circuit_pct']:.0f}% of the {'upper' if side == 'gainer' else 'lower'} "
                     f"circuit: one-sided frenzy, skip")

    observe = c["mode"] != "score"
    return {"points": 0 if observe else points, "block": block and not observe,
            "notes": [f"(observe) {n}" for n in notes] if observe else notes,
            "oi_type": kind, "would_score": points, "would_block": block}
