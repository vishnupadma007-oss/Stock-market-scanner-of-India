"""The reflex engine: plain code that watches every tick so the AI doesn't have to.

- Armed setups: Arjun's planned entries wait here with a trigger price ("buy if it breaks above
  2,140 before 11:30"). The moment the price crosses the trigger, the trade goes to the risk manager and
  the broker. A setup armed when the price is already beyond its trigger waits for a fresh cross rather
  than chasing. Setups without a trigger fire on the next tick.
- Trailing stops: once a trade is 1R in profit (R = its original risk), the stop moves to break-even
  plus charges; at 2R it locks in 1R. Winners are allowed to run, losers are cut at the stop.
- Shock detector: a sharp move in a short window wakes the AI to re-think.
"""

import datetime as dt
from collections import deque


class Reflex:
    def __init__(self, shock_pct=1.0, window_min=5, cooldown_min=15):
        self.armed = []
        self.history = {}
        self.shock_pct, self.window = shock_pct, dt.timedelta(minutes=window_min)
        self.cooldown = dt.timedelta(minutes=cooldown_min)
        self.last_shock = {}

    # ---- armed setups --------------------------------------------------------

    def arm(self, setups):
        """Replace the armed list with Arjun's latest plan."""
        last = {sym: h[-1][1] for sym, h in self.history.items() if h}
        self.armed = [{**s, "last_px": s.get("last_px", last.get(s["symbol"]))} for s in setups]

    @staticmethod
    def _beyond(s, px):
        return ((s.get("trigger_above") is None or px >= float(s["trigger_above"]))
                and (s.get("trigger_below") is None or px <= float(s["trigger_below"])))

    def due(self, prices, now, held=()):
        """Setups that fired (removed from the list) and setups that expired or are moot (dropped)."""
        fired, keep, dropped = [], [], []
        hhmm = now.strftime("%H:%M")
        for s in self.armed:
            px = prices.get(s["symbol"])
            entry = s.get("action") in ("BUY", "SHORT")
            if s.get("valid_until") and hhmm > s["valid_until"]:
                dropped.append({**s, "why": f"expired at {s['valid_until']}"})
            elif entry and s["symbol"] in held:
                dropped.append({**s, "why": "already in a position"})
            elif s.get("action") == "EXIT" and s["symbol"] not in held:
                dropped.append({**s, "why": "no position to exit"})
            elif px is None:
                keep.append(s)
            elif s.get("trigger_above") is None and s.get("trigger_below") is None:
                fired.append({**s, "entry": px, "fired_at": hhmm})
            elif self._beyond(s, px) and s.get("last_px") is not None and not self._beyond(s, s["last_px"]):
                fired.append({**s, "entry": px, "fired_at": hhmm})  # a fresh cross
            else:
                keep.append({**s, "last_px": px})
        self.armed = keep
        return fired, dropped

    # ---- trailing stops -------------------------------------------------------

    @staticmethod
    def trail(positions, prices):
        """[(symbol, new_stop)] for positions whose stop should move up (longs) or down (shorts)."""
        moves = []
        for sym, p in positions.items():
            px, entry = prices.get(sym), p.get("avg_price")
            if px is None or entry is None or p.get("stop_loss") is None:
                continue
            r = abs(entry - p.get("initial_stop", p["stop_loss"]))
            if r <= 0:
                continue
            sign = 1 if p.get("side", "LONG") == "LONG" else -1
            gain_r = sign * (px - entry) / r
            buffer = entry * 0.001  # roughly the round-trip charges
            if gain_r >= 2:
                new = entry + sign * r
            elif gain_r >= 1:
                new = entry + sign * buffer
            else:
                continue
            new = round(new * 20) / 20
            if sign * (new - p["stop_loss"]) > 0:  # only ever tighten
                moves.append((sym, new))
        return moves

    # ---- shocks -----------------------------------------------------------------

    def shocks(self, prices, now):
        """[(symbol, % move over the window)] for sharp moves, at most one alert per symbol per cooldown."""
        out = []
        for sym, px in prices.items():
            h = self.history.setdefault(sym, deque())
            h.append((now, px))
            while h and now - h[0][0] > self.window:
                h.popleft()
            move = 100 * (px / h[0][1] - 1)
            if abs(move) >= self.shock_pct and now - self.last_shock.get(sym, now - 2 * self.cooldown) > self.cooldown:
                self.last_shock[sym] = now
                out.append((sym, round(move, 2)))
        return out
