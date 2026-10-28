"""Quiet Volume Spurt (user's strategy, 28 Oct 2026): catch a move at ~0.2%, before it runs.

An F&O stock trading far more volume than usual for this time of day while it has moved only a
little from yesterday's close: buy the option in the direction of that small move and aim for a
10% net gain on the option (a 1-2% stock move lifts an option 20-50%).

The signal, on 5-minute candles from 09:30:
  - cumulative volume so far today >= `min_volume_x` times the usual cumulative volume at the same
    candle of the day (mean of the previous 10 sessions);
  - move from yesterday's close between `min_move_pct` and `max_move_pct` (either direction);
  - the latest candle closes the move's way and the price is on the move's side of VWAP;
  - first signal per stock per day.

Backtest (60 days x 76 stocks, ITM1, no stop-loss, square-off 15:20; journal/backtest_summary.md):
>= 1.5x volume, 0.2-0.5% move, 10% net target: 174 trades, 68% hit, +2.89% per trade, +Rs 1.5 lakh,
positive in both halves of the period; the same entries the opposite way: -4.19% per trade.
With a 1% target the same signals lost money (a few untouched losers outweigh many small wins).

News cross-check (the user's plan): strong news against the move skips it; news the move's way is
noted on the signal. History has no news, so that part is judged on paper.

Data, live: NSE's own "stocks traded" page every minute (free, one call covers every listed stock:
price, previous close, volume and value traded so far; VWAP = value / volume). The latest candle
is read from our own snapshots (price now vs 5 minutes ago). The usual volume by this time of day
comes once each morning from the previous 10 sessions of 5-minute candles (Yahoo), and every NSE
snapshot is saved (journal/intel/nse_volume-<date>.jsonl) so that history becomes our own.
INDmoney's live quote confirms before buying.

    python -m agents.spurt            # today's signals so far
"""
from datetime import date, time

import numpy as np
import pandas as pd

from .indicators import vwap

DEFAULTS = {"min_volume_x": 1.5, "min_move_pct": 0.2, "max_move_pct": 0.5, "from": "09:30",
            "baseline_days": 10, "target_net_pct": 10.0}


def prepare(intra: pd.DataFrame, baseline_days: int = 10) -> pd.DataFrame:
    """Per-candle features: candle number of the day, cumulative volume vs usual, move vs the
    previous close, VWAP."""
    df = intra.copy()
    df["day"] = df.index.date
    df["bar"] = df.groupby("day").cumcount()
    df["cumvol"] = df.groupby("day")["Volume"].cumsum()
    piv = df.pivot_table(index="day", columns="bar", values="cumvol")
    usual = piv.shift(1).rolling(baseline_days, min_periods=5).mean()
    prev_close = df.groupby("day")["Close"].last().shift(1)
    df["usual"] = [usual.at[d, b] if b in usual.columns else np.nan for d, b in zip(df["day"], df["bar"])]
    df["prev"] = df["day"].map(prev_close)
    df["vwap"] = df.groupby("day", group_keys=False).apply(vwap)
    df["volume_x"] = df["cumvol"] / df["usual"]
    df["move"] = (df["Close"] / df["prev"] - 1) * 100
    return df


def first_signal(df: pd.DataFrame, day: date, cfg: dict | None = None, until: time | None = None) -> dict | None:
    """The day's first qualifying candle, or None. `df` from `prepare`."""
    c = {**DEFAULTS, **(cfg or {})}
    g = df[(df["day"] == day) & (df.index.time >= time.fromisoformat(c["from"])) & (df["bar"] >= 3)]
    if until is not None:
        g = g[g.index.time <= until]
    for t, r in g.iterrows():
        if np.isnan(r["volume_x"]) or r["volume_x"] < c["min_volume_x"] \
                or not c["min_move_pct"] <= abs(r["move"]) <= c["max_move_pct"]:
            continue
        d = 1 if r["move"] > 0 else -1
        if (d > 0) != bool(r["Close"] > r["Open"]) or (r["Close"] - r["vwap"]) * d <= 0:
            continue  # the latest candle and the VWAP side must agree with the move
        return {"time": t, "direction": "up" if d > 0 else "down", "volume_x": round(float(r["volume_x"]), 2),
                "move_pct": round(float(r["move"]), 2), "price": round(float(r["Close"]), 2)}
    return None


NSE_TRADED = "https://www.nseindia.com/api/live-analysis-stocksTraded"


def parse_nse(payload: dict, universe: set[str]) -> dict[str, dict]:
    """{symbol: {price, prev_close, move_pct, volume (shares), vwap}} from NSE's stocks-traded page
    (volume in lakh shares, value in crore rupees)."""
    out = {}
    for r in ((payload or {}).get("total") or {}).get("data") or []:
        sym = r.get("symbol")
        if sym not in universe or r.get("series") != "EQ" or not r.get("previousClose") or not r.get("totalTradedVolume"):
            continue
        vol_lakh, val_cr = float(r["totalTradedVolume"]), float(r.get("totalTradedValue") or 0)
        out[sym] = {"price": float(r["lastPrice"]), "prev_close": float(r["previousClose"]),
                    "move_pct": round(float(r.get("pchange") or 0), 2), "volume": vol_lakh * 1e5,
                    "vwap": round(val_cr * 100 / vol_lakh, 2) if val_cr else None}
    return out


def fetch_nse(universe) -> dict[str, dict]:
    from .preopen import _get
    return parse_nse(_get(NSE_TRADED), set(universe))


def usual_curve(intra: pd.DataFrame, before: date, days: int = 10) -> pd.Series | None:
    """Usual cumulative volume by time of day (index: minutes after 09:15 at each 5-minute candle's
    close), the mean of the last `days` sessions before `before`."""
    past = intra[intra.index.date < before]
    sessions = sorted(set(past.index.date))[-days:]
    if len(sessions) < 5:
        return None
    curves = []
    for d in sessions:
        g = past[past.index.date == d]
        mins = (g.index.hour * 60 + g.index.minute - (9 * 60 + 15)) + 5
        curves.append(pd.Series(g["Volume"].cumsum().values, index=mins))
    return pd.concat(curves, axis=1).mean(axis=1).sort_index()


def usual_now(curve: pd.Series, minutes: float) -> float | None:
    if curve is None or curve.empty or minutes <= 0:
        return None
    return float(np.interp(minutes, curve.index.values, curve.values))


def live_signal(now_snap: dict, earlier_price: float | None, usual: float | None, minutes: float,
                cfg: dict | None = None) -> dict | None:
    """The same rule as `first_signal`, on live NSE data: volume so far vs usual by now, move from
    the previous close, the last 5 minutes' direction (price now vs `earlier_price`) and the VWAP side."""
    c = {**DEFAULTS, **(cfg or {})}
    if not usual or earlier_price is None or minutes < 15:
        return None
    vx = now_snap["volume"] / usual
    move = now_snap["move_pct"]
    if vx < c["min_volume_x"] or not c["min_move_pct"] <= abs(move) <= c["max_move_pct"]:
        return None
    d = 1 if move > 0 else -1
    if (now_snap["price"] - earlier_price) * d <= 0:
        return None  # the last 5 minutes must move the same way
    if now_snap.get("vwap") and (now_snap["price"] - now_snap["vwap"]) * d <= 0:
        return None
    return {"direction": "up" if d > 0 else "down", "volume_x": round(vx, 2), "move_pct": move,
            "price": now_snap["price"]}


def save_snapshot(day: date, at: str, rows: dict) -> None:
    from .preopen import DIR
    DIR.mkdir(parents=True, exist_ok=True)
    import json
    with open(DIR / f"nse_volume-{day.isoformat()}.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps({"time": at, "rows": {s: [r["price"], r["volume"]] for s, r in rows.items()}}) + "\n")


def fetch(universe: list[str], days: int = 20) -> dict[str, pd.DataFrame]:
    """5-minute candles (IST) for each stock, `days` sessions back, from Yahoo in one request."""
    import yfinance as yf
    raw = yf.download([f"{s}.NS" for s in universe], period=f"{days}d", interval="5m", progress=False,
                      auto_adjust=False, group_by="ticker", threads=True)
    out = {}
    for s in universe:
        try:
            d = raw[f"{s}.NS"][["Open", "High", "Low", "Close", "Volume"]].dropna()
        except KeyError:
            continue
        if d.empty:
            continue
        d.index = d.index.tz_convert("Asia/Kolkata") if d.index.tz else d.index.tz_localize("Asia/Kolkata")
        out[s] = d
    return out


def scan(frames: dict[str, pd.DataFrame], day: date, cfg: dict | None = None) -> dict[str, dict]:
    """Every stock's first signal today (stocks with no signal are left out)."""
    out = {}
    for sym, intra in frames.items():
        if intra.empty or intra.index[-1].date() != day:
            continue
        sig = first_signal(prepare(intra, (cfg or {}).get("baseline_days", 10)), day, cfg)
        if sig:
            out[sym] = sig
    return out


def main() -> None:
    from .config import load_config
    cfg = load_config()
    frames = fetch(cfg["universe"])
    day = max(f.index[-1].date() for f in frames.values())
    for sym, s in sorted(scan(frames, day, cfg.get("spurt")).items(), key=lambda kv: kv[1]["time"]):
        print(f"{s['time']:%H:%M} {sym:12} {s['direction']:5} move {s['move_pct']:+.2f}%  volume {s['volume_x']:.1f}x usual")


if __name__ == "__main__":
    main()
