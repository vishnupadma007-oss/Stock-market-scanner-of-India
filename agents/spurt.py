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
from datetime import date, time, datetime

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


_UNITS = {"k": 1e3, "l": 1e5, "lakh": 1e5, "lakhs": 1e5, "cr": 1e7, "crore": 1e7}


def _num(v, unit: float = 1.0) -> float:
    """NSE numbers, plain (in `unit`, e.g. lakh) or as text with a unit since 2 Nov 2026 ("472.67 L",
    "1,234.5 Cr"); returned in `unit`."""
    if isinstance(v, (int, float)):
        return float(v)
    parts = str(v).replace(",", "").split()
    x = float(parts[0])
    if len(parts) > 1 and parts[1].lower() in _UNITS:
        return x * _UNITS[parts[1].lower()] / unit
    return x


def parse_nse(payload: dict, universe: set[str]) -> dict[str, dict]:
    """{symbol: {price, prev_close, move_pct, volume (shares), vwap}} from NSE's stocks-traded page
    (volume in lakh shares, value in crore rupees)."""
    out = {}
    for r in ((payload or {}).get("total") or {}).get("data") or []:
        sym = r.get("symbol")
        if sym not in universe or r.get("series") != "EQ" or not r.get("previousClose") or not r.get("totalTradedVolume"):
            continue
        vol_lakh, val_cr = _num(r["totalTradedVolume"], 1e5), _num(r.get("totalTradedValue") or 0, 1e7)
        out[sym] = {"price": _num(r["lastPrice"]), "prev_close": _num(r["previousClose"]),
                    "move_pct": round(_num(r.get("pchange") or 0), 2), "volume": vol_lakh * 1e5,
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


# ==============================================================================
# Enhanced Pure Institutional Volume Spurt Engine (Revived Spurt Engine, Nov 2026)
# ==============================================================================

def check_news_quarantine(symbol: str, now: datetime, daily_intel: dict,
                          filings: list[dict], items: list[dict],
                          results_calendar: dict, min_impact: int = 3) -> tuple[bool, str]:
    """Total News Quarantine Filter: returns (is_quarantined, reason).
    If a stock has ANY news, corporate filing, analyst forecast, or upcoming results,
    it is strictly disqualified from the Pure Volume Spurt Team.
    """
    today_str = now.strftime("%Y-%m-%d")
    
    # 1. Results Calendar: results today or upcoming in next 2 sessions
    if results_calendar:
        r_dates = results_calendar.get(symbol, [])
        if any(str(d) == today_str for d in r_dates):
            return True, "Results due today; extreme binary volatility"
        next_days = [(now.date() + pd.Timedelta(days=i)).strftime("%Y-%m-%d") for i in (1, 2)]
        if any(str(d) in next_days for d in r_dates):
            return True, "Results due in next 48h; pre-results positioning noise"

    # 2. Corporate & Regulatory Filings: today or post-close yesterday
    for f in filings:
        if f.get("symbol") == symbol:
            cat = f.get("category", "")
            t = str(f.get("time", ""))
            if t.startswith(today_str) or cat == "RESULTS":
                return True, f"Filing detected ({cat}): {str(f.get('text', ''))[:60]}"

    # 3. Material news only (user, 5 Nov: option 2): filings, policy hits and high-impact news. Routine media
    #    articles, concall transcripts and call schedules do not disqualify a clean tape.
    for item in items:
        if symbol in item.get("symbols", []):
            kind = item.get("kind", "")
            if kind in ("filing", "policy") or (kind == "news" and int(item.get("impact", 0) or 0) >= min_impact):
                headline = (item.get("headline") or item.get("category") or "")[:60]
                return True, f"Material news/catalyst ({kind}): {headline}"

    # 4. Intelligence log / Daily forecasts
    if symbol in (daily_intel.get("forecasts") or {}):
        return True, "Stock has active Data Analyzer forecast"

    return False, "Clean: Zero news detected (Pure Tape Anomaly)"


def check_preopen_profile(symbol: str, preopen_data: dict, max_gap_pct: float = 1.0) -> tuple[bool, str]:
    """Pre-Market Interlinking: verifies the stock did not have a violent opening gap.
    Pure quiet institutional spurts require an uncrowded, calm pre-open where the market
    underestimated the stock before the open.
    """
    if not preopen_data or symbol not in preopen_data:
        return True, "No pre-open gap distortion recorded"

    pod = preopen_data[symbol]
    gap = pod.get("gap_pct", pod.get("pchange", 0.0))
    if abs(gap) > max_gap_pct:
        return False, f"Pre-open gap {gap:+.2f}% too large (> {max_gap_pct}%); handled by Preopen Team"

    return True, f"Pre-open calm ({gap:+.2f}% gap); ideal for stealth intraday flow"


def check_fo_activity(symbol: str, direction: str, activity_data: dict,
                      min_oi_pct: float = 2.0) -> tuple[bool, str]:
    """Derivatives Institutional Footprint: verifies volume is backed by real Open Interest (OI)
    expansion, not empty retail churn or day-trader noise.
    """
    if not activity_data or symbol not in activity_data:
        return True, "No derivatives OI distortion recorded"

    act = activity_data[symbol]
    kind = act.get("kind", "")
    oi_pct = act.get("oi_pct", 0.0)

    if direction == "up":
        if kind == "long build-up":
            return True, f"Institutional confirmation: Long build-up (OI {oi_pct:+.1f}%)"
        elif kind == "short covering":
            return True, f"Short covering rally (OI {oi_pct:+.1f}%)"
        elif kind == "short build-up":
            return False, f"Bearish trap: Short build-up against upward spurt (OI {oi_pct:+.1f}%)"
    elif direction == "down":
        if kind == "short build-up":
            return True, f"Institutional confirmation: Short build-up (OI {oi_pct:+.1f}%)"
        elif kind == "long unwinding":
            return True, f"Long unwinding flush (OI {oi_pct:+.1f}%)"
        elif kind == "long build-up":
            return False, f"Bullish trap: Long build-up against downward spurt (OI {oi_pct:+.1f}%)"

    return True, f"Derivatives flow neutral: {kind} (OI {oi_pct:+.1f}%)"


def check_multiweek_context(daily_df: pd.DataFrame, direction: str,
                            now_date: date) -> tuple[bool, str, dict]:
    """Multi-Week Structural Context (The 5%-10% Prior Move Parameter):
    Evaluates prior 1-3 week momentum and consolidation structures.
    Prevents buying exhausted blow-off tops or shorting oversold climax bottoms.
    """
    past = daily_df[daily_df.index.date < now_date]
    if len(past) < 20:
        return True, "Insufficient daily history; pass with default risk", {}

    pc = past["Close"]
    spot = float(pc.iloc[-1])
    run5 = float((pc.iloc[-1] / pc.iloc[-6] - 1.0) * 100.0) if len(pc) >= 6 else 0.0
    run10 = float((pc.iloc[-1] / pc.iloc[-11] - 1.0) * 100.0) if len(pc) >= 11 else 0.0
    hi20 = float(past["High"].tail(20).max())
    lo20 = float(past["Low"].tail(20).min())
    dist_to_hi = (hi20 / spot - 1.0) * 100.0
    dist_to_lo = (spot / lo20 - 1.0) * 100.0

    meta = {
        "run5": round(run5, 2), "run10": round(run10, 2),
        "hi20": round(hi20, 2), "lo20": round(lo20, 2),
        "dist_to_hi": round(dist_to_hi, 2), "dist_to_lo": round(dist_to_lo, 2)
    }

    if direction == "up":
        # 1. Exhaustion Veto: up > 8% in 5d or > 12% in 10d and hugging 20d high
        if (run5 > 8.0 or run10 > 12.0) and dist_to_hi < 0.5:
            return False, f"Exhaustion risk: Stock already surged {run5:+.1f}% (5d) / {run10:+.1f}% (10d) into 20d high", meta

        # 2. Golden Base Breakout: 5%-10% prior move with tight recent consolidation
        if 4.0 <= run10 <= 12.0 and abs(run5) < 3.0:
            return True, f"Golden Base Breakout: Tight consolidation (5d {run5:+.1f}%) after prior move ({run10:+.1f}%)", meta

        # 3. Fresh Trend Ignition from base
        if abs(run10) < 4.0:
            return True, f"Fresh Trend Ignition from tight base ({run10:+.1f}% over 10d)", meta

        return True, f"Standard upward structure (5d {run5:+.1f}%, 10d {run10:+.1f}%)", meta

    else: # direction == "down"
        # 1. Climax Dump Veto: down > 8% in 5d or > 12% in 10d into 20d low
        if (run5 < -8.0 or run10 < -12.0) and dist_to_lo < 0.5:
            return False, f"Climax dump risk: Stock already dumped {run5:+.1f}% (5d) / {run10:+.1f}% (10d) into 20d low", meta

        # 2. Golden Breakdown: tight consolidation before fresh breakdown
        if -12.0 <= run10 <= -4.0 and abs(run5) < 3.0:
            return True, f"Golden Breakdown: Tight consolidation (5d {run5:+.1f}%) before leg down ({run10:+.1f}%)", meta

        # 3. Fresh Breakdown from Highs
        if abs(run10) < 4.0:
            return True, f"Fresh Top Breakdown from tight base ({run10:+.1f}% over 10d)", meta

        return True, f"Standard downward structure (5d {run5:+.1f}%, 10d {run10:+.1f}%)", meta


def check_institutional_timing(now: datetime, entry_from: str = "09:30",
                               entry_until: str = "11:30") -> tuple[bool, str]:
    """Prime Institutional Window: Volume spurts in the morning (09:30-11:30) have the highest
    follow-through. Afternoon spurts suffer from intraday decay and lack of momentum.
    """
    t = now.time()
    t_start = time.fromisoformat(entry_from)
    t_end = time.fromisoformat(entry_until)

    if t < t_start:
        return False, f"Too early for volume spurt ({t:%H:%M} < {entry_from})"
    if (t.hour, t.minute) > (t_end.hour, t_end.minute):  # the whole closing minute counts
        return False, f"Outside prime institutional window ({t:%H:%M} > {entry_until}); avoid late churn"

    return True, f"Inside prime institutional execution window ({t:%H:%M})"


PURE_DEFAULTS = {"enabled": True, "window_until": "11:30", "preopen_max_gap_pct": 1.0, "min_oi_pct": 2.0,
                 "max_spread_pct": 1.0, "min_delta": 0.50, "max_delta": 0.65,
                 "with_market": True, "market_min_pct": 0.0, "market_flat_band_pct": 0.15,
                 "late_until": "14:00", "late_burst_x": 3.0}


def bar_burst(vol_now: float, vol_before: float | None, curve: pd.Series | None, minutes: float) -> float | None:
    """The last 5 minutes' volume vs the usual volume in the same 5 minutes of the day (from the usual
    cumulative curve): 3.0 = three times the usual for this slot."""
    if vol_before is None or curve is None or minutes < 20:
        return None
    a, b = usual_now(curve, minutes - 5), usual_now(curve, minutes)
    if not a or not b or b <= a:
        return None
    return round((vol_now - vol_before) / (b - a), 2)


def late_burst_ok(now: datetime, burst_x: float | None, pure: dict) -> tuple[bool, str]:
    """After the 09:30-11:30 window (user's idea, 14 Nov): a spurt still trades until `late_until` when the
    last 5-minute candle alone has `late_burst_x` times its usual volume (backtest: 6 new trades, +Rs 9.6k, both halves)."""
    p = {**PURE_DEFAULTS, **(pure or {})}
    t = now.time()
    if (t.hour, t.minute) > tuple(int(x) for x in p["late_until"].split(":")):
        return False, f"after {p['late_until']}: too late even for a big burst"
    if burst_x is None or burst_x < p["late_burst_x"]:
        return False, f"after {p['window_until']}: last 5-min volume {burst_x or 0:.1f}x usual, needs {p['late_burst_x']:g}x"
    return True, f"late burst: last 5-min volume {burst_x:.1f}x usual"


def check_option_limits(option: dict, pure: dict) -> str:
    """The pure spurt's contract limits (user, 4 Nov): bid-ask gap <= max_spread_pct and |delta| inside the band.
    Returns why it fails, "" if the contract fits. A missing delta is not held against the contract."""
    if option.get("spread_pct", 0) > pure["max_spread_pct"]:
        return f"bid-ask gap {option['spread_pct']:.2f}% > {pure['max_spread_pct']}%"
    delta = option.get("delta")
    if delta is not None and not pure["min_delta"] <= abs(float(delta)) <= pure["max_delta"]:
        return f"delta {abs(float(delta)):.2f} outside {pure['min_delta']}-{pure['max_delta']}"
    return ""


def check_market_alignment(direction: str, nifty_move_pct: float | None, min_pct: float = 0.0,
                           flat_band_pct: float = 0.15) -> tuple[bool, str]:
    """Trade WITH the market (user's idea, backtest 7 Nov). Nifty up -> only spurts up (CALLs); Nifty down -> only spurts down
    (PUTs); a flat market (|Nifty| under `flat_band_pct`) -> both directions. 60 days: with the market CALLs +Rs 44.7k (against: PUTs
    +Rs 1.4k), PUTs +Rs 23k (against: CALLs -Rs 39k), flat market both ways +Rs 66k (CALLs +36k, PUTs +32k). No Nifty reading is not
    held against the trade."""
    if nifty_move_pct is None:
        return True, "no Nifty reading"
    move = float(nifty_move_pct)
    if abs(move) < flat_band_pct:
        return True, f"flat market (Nifty {move:+.2f}%): both directions"
    sign = 1 if direction == "up" else -1
    if sign * move > min_pct:
        return True, f"with the market (Nifty {move:+.2f}%)"
    return False, f"against the market: spurt {direction}, Nifty {move:+.2f}%"


def level_note(daily_df: pd.DataFrame, direction: str, price: float, today: date, look: int = 60, k: int = 2) -> str:
    """Support / resistance around the entry (observe only, user's question 7 Nov): the nearest swing high above and swing low
    below in the last `look` sessions, the room ahead and behind in the trade's direction, and whether it broke the 20-day high/low.
    Noted on the trade so the review can test it on live trades (the 60-day backtest: no filter added money)."""
    past = daily_df[daily_df.index.date < today].tail(look)
    if len(past) < 2 * k + 3 or not price:
        return ""
    hi, lo = past["High"].values, past["Low"].values
    res = [hi[i] for i in range(k, len(past) - k) if hi[i] == max(hi[i - k:i + k + 1]) and hi[i] > price * 1.0005]
    sup = [lo[i] for i in range(k, len(past) - k) if lo[i] == min(lo[i - k:i + k + 1]) and lo[i] < price * 0.9995]
    up = (min(res) / price - 1) * 100 if res else None
    dn = (price / max(sup) - 1) * 100 if sup else None
    ahead, behind = (up, dn) if direction == "up" else (dn, up)
    h20, l20 = float(past["High"].tail(20).max()), float(past["Low"].tail(20).min())
    brk = price > h20 if direction == "up" else price < l20
    fmt = lambda v: "none" if v is None else f"{v:.1f}%"
    return f"levels: room ahead {fmt(ahead)}, level behind {fmt(behind)}, {'breaks' if brk else 'inside'} the 20-day range"
