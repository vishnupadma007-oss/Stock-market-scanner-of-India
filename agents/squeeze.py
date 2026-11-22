"""Squeeze team (user's idea, 22 Nov 2026): a quiet patch, then a breakout the candles voted for.

Every F&O stock now and then goes quiet on the 5-minute chart (a "stagnation"). Inside that quiet patch, count the
candles: clearly more green than red -> it tends to break UP (buy a CALL); more red than green -> DOWN (buy a PUT).

The rule (backtest_squeeze.py, 60 days x 218 F&O stocks; the strict version is the only one that made money in both
halves of the test, see journal/backtest_summary.md):
  - quiet patch: the last `n` 5-minute candles (12 = one hour) span at most `tight` x sqrt(n) x the stock's usual
    5-minute candle range (median of the last 20 sessions);
  - vote: greens - reds >= `vote` AND more volume on the green candles than on the red ones (mirror for PUTs);
  - breakout: within the next `within` candles, one closes outside the box the vote's way on `volume_x` x the box's
    average candle volume;
  - filters: price the right side of VWAP and the 9-EMA the right side of the 21-EMA;
  - entries 09:45-14:30, one per stock per day; target 15% net on the option, no stop-loss, square-off 15:20.

Live (watcher.squeeze_track): NSE's own stocks-traded page once a minute covers every listed stock (price and volume
so far); our snapshots are cut into 5-minute candles and every F&O stock is checked as each candle closes. A stock
that passes is confirmed on INDmoney's real 5-minute candles before the paper trade opens. NSE updates the page about
once a minute and the rule reads closed 5-minute candles, so scanning faster than that would only re-read the same
numbers.

    python -m agents.squeeze            # today's signals so far, on Yahoo 5-minute candles
"""
from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

import numpy as np
import pandas as pd

DEFAULTS = {"enabled": True, "n": 12, "tight": 0.5, "vote": 4, "volume_x": 1.2, "within": 6, "filters": True,
            "from": "09:45", "until": "14:30", "usual_days": 20, "targets": [15.0], "min_premium": 5.0}
LOG_DIR = Path(__file__).resolve().parent.parent / "journal" / "squeeze"


def usual_range(intra: pd.DataFrame, before: date, days: int = 20) -> float | None:
    """Median 5-minute candle range (high - low) over the last `days` sessions before `before`."""
    if intra is None or intra.empty:
        return None
    past = intra[intra.index.date < before]
    sessions = sorted(set(past.index.date))[-days:]
    if len(sessions) < 5:
        return None
    past = past[np.isin(past.index.date, sessions)]
    r = float((past["High"] - past["Low"]).median())
    return r if r > 0 else None


def day_signals(bars: pd.DataFrame, typ: float, n: int = 12, tight: float = 0.5, vote: int = 4, entry: str = "break",
                filters: bool = True, use_vote: bool = True, volume_x: float = 1.2, within: int = 6,
                start: str = "09:45", until: str = "14:30"):
    """Yield (bar index, direction +1/-1, details) for the FIRST signal of one stock-day (bars: that day's 5-minute
    candles, oldest first). entry "break" waits for the breakout candle; "box" enters when the quiet patch ends.
    use_vote=False is the test baseline (any breakout, no candle count)."""
    if bars is None or len(bars) <= n or not typ or typ <= 0:
        return
    o, h, l, c, v = (bars[k].to_numpy(float) for k in ("Open", "High", "Low", "Close", "Volume"))
    tp = (h + l + c) / 3
    vwap = np.cumsum(tp * v) / np.maximum(np.cumsum(v), 1)
    e9 = pd.Series(c).ewm(span=9, adjust=False).mean().to_numpy()
    e21 = pd.Series(c).ewm(span=21, adjust=False).mean().to_numpy()
    hm = bars.index.strftime("%H:%M")
    limit = tight * typ * n ** 0.5
    for k in range(n, len(bars)):
        lo_i = k - n
        box_hi, box_lo = h[lo_i:k].max(), l[lo_i:k].min()
        if box_hi - box_lo > limit:
            continue
        green, red = c[lo_i:k] > o[lo_i:k], c[lo_i:k] < o[lo_i:k]
        g, r = int(green.sum()), int(red.sum())
        vg, vr = float(v[lo_i:k][green].sum()), float(v[lo_i:k][red].sum())
        if use_vote:
            if g - r >= vote and vg > vr:
                d = 1
            elif r - g >= vote and vr > vg:
                d = -1
            else:
                continue
        else:
            d = 0
        avg_v = float(v[lo_i:k].mean())
        j = dd = None
        if entry == "box":
            j, dd = k - 1, d
        else:
            for m in range(k, min(k + within, len(bars))):
                up, dn = c[m] > box_hi, c[m] < box_lo
                if (up and d >= 0) or (dn and d <= 0):
                    if v[m] >= volume_x * avg_v:
                        j, dd = m, (1 if up else -1)
                    break
        if j is None or not dd or not (start <= hm[j] <= until):
            continue
        if filters and ((c[j] - vwap[j]) * dd <= 0 or (e9[j] - e21[j]) * dd <= 0):
            continue
        yield j, dd, {"box_high": round(float(box_hi), 2), "box_low": round(float(box_lo), 2), "greens": g, "reds": r,
                      "green_volume_share": round(vg / max(vg + vr, 1), 2), "box_from": hm[lo_i], "box_to": hm[k - 1],
                      "breakout_volume_x": round(float(v[j]) / max(avg_v, 1), 2), "price": round(float(c[j]), 2)}
        return


def live_signal(today_bars: pd.DataFrame, typ: float | None, cfg: dict | None = None, last_n: int = 1) -> dict | None:
    """The day's first signal, if it is on one of the last `last_n` CLOSED candles (else it is old or not there)."""
    c = {**DEFAULTS, **(cfg or {})}
    if today_bars is None or today_bars.empty or not typ:
        return None
    for j, d, info in day_signals(today_bars, typ, c["n"], c["tight"], c["vote"], "break", c["filters"], True,
                                  c["volume_x"], c["within"], c["from"], c["until"]):
        if j < len(today_bars) - last_n:
            return None
        return {"direction": "up" if d > 0 else "down", "bar": today_bars.index[j].strftime("%H:%M"), **info,
                "why": why(d, info)}
    return None


def why(d: int, info: dict) -> str:
    side = "green" if d > 0 else "red"
    return (f"quiet {info['box_from']}-{info['box_to']} ({info['box_low']}-{info['box_high']}), "
            f"{info['greens']} green vs {info['reds']} red candles, "
            f"{round(100 * (info['green_volume_share'] if d > 0 else 1 - info['green_volume_share']))}% of the volume "
            f"on {side} candles; broke {'up' if d > 0 else 'down'} on {info['breakout_volume_x']}x volume")


class SnapshotBars:
    """5-minute candles built from once-a-minute snapshots (price, cumulative volume) of NSE's stocks-traded page.
    High/low come only from the snapshots, so a box looks a little tighter than it is: a pre-filter only, the trade
    is confirmed on INDmoney's real candles."""

    def __init__(self):
        self.snaps: dict[str, list[tuple[datetime, float, float]]] = {}

    def add(self, sym: str, ts: datetime, price: float, volume: float | None) -> None:
        if price:
            self.snaps.setdefault(sym, []).append((ts, float(price), float(volume or 0)))

    def bars(self, sym: str, now: datetime) -> pd.DataFrame:
        rows = self.snaps.get(sym) or []
        if len(rows) < 2:
            return pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])
        s = pd.DataFrame(rows, columns=["t", "p", "v"]).set_index("t")
        open_t = s.index[0].replace(hour=9, minute=15, second=0, microsecond=0)
        bucket = ((s.index - open_t).total_seconds() // 300).astype(int)
        g = s.groupby(bucket)
        out = pd.DataFrame({"Open": g["p"].first(), "High": g["p"].max(), "Low": g["p"].min(), "Close": g["p"].last(),
                            "cum": g["v"].last()})
        out["Volume"] = out["cum"].diff().fillna(out["cum"]).clip(lower=0)
        out.index = [open_t + pd.Timedelta(minutes=5 * int(b)) for b in out.index]
        out = out[[t + pd.Timedelta(minutes=5) <= now for t in out.index]]  # closed candles only
        return out[["Open", "High", "Low", "Close", "Volume"]]


def save(day: date, entry: dict) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with open(LOG_DIR / f"{day.isoformat()}.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, default=str) + "\n")


def main() -> None:
    from . import data
    from .spurt import fetch
    syms = sorted(s for s in data.nse_lot_sizes() if not s.startswith(("NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY")))
    frames = fetch(syms, 25)
    today = max(max(f.index.date) for f in frames.values())
    for s, f in frames.items():
        bars = f[f.index.date == today]
        for j, d, info in day_signals(bars, usual_range(f, today) or 0):
            print(f"{s:12} {bars.index[j].strftime('%H:%M')} {'CALL' if d > 0 else 'PUT '} {why(d, info)}")


if __name__ == "__main__":
    main()
