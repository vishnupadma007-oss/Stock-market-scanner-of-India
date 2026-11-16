"""ADR team (user's design, 15 Nov 2026): a regime-switching desk for the five NSE F&O stocks that also trade in
New York as ADRs. Overnight the ADR tells where the stock should open; the regime decides what to do after it.

Regimes (one per stock per day, mutually exclusive, checked in this order):
  1 macro shock      - Nifty gap (GIFT proxy) > 1.2%, or India VIX up 8%+, or Brent 4%+ / USD-INR 0.7%+ overnight
  2 sector catalyst  - both IT ADRs (INFY, WIT) or both bank ADRs (HDB, IBN) move 1.5%+ the same way, Nifty gap within 0.5%
  3 stock catalyst   - the stock's own ADR moves 2%+ on 1.5x+ its usual US volume
  4 normal           - ADR move under 1%, Nifty gap within 0.5%, first-15-minute NSE volume under 1.2x usual
  0 unclear          - none of the above (e.g. ADR 1-2% without volume): no trade

The desk buys options only (user's standing rule), so the plan's credit spreads / option selling are not built;
order-book delta and the option-chain OI wall are optional inputs (no history to test them).
"""
from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class Pair:
    nse: str
    adr: str
    ratio: float   # NSE shares per ADR
    sector: str


PAIRS = {p.nse: p for p in (
    Pair("INFY", "INFY", 1, "it"), Pair("WIPRO", "WIT", 1, "it"),
    Pair("HDFCBANK", "HDB", 3, "bank"), Pair("ICICIBANK", "IBN", 2, "bank"),
    Pair("DRREDDY", "RDY", 1, "pharma"))}

DEFAULTS = {"macro_gap_pct": 1.2, "vix_spike_pct": 8.0, "brent_shock_pct": 4.0, "usdinr_shock_pct": 0.7,
            "sector_adr_pct": 1.5, "sector_nifty_band_pct": 0.5,
            "stock_adr_pct": 2.0, "stock_adr_vol_x": 1.5, "orb_vol_x": 2.0,
            "normal_adr_pct": 1.0, "normal_nifty_band_pct": 0.5, "normal_first15_vol_x": 1.2,
            "atr_stretch": 0.90, "vwap_sd": 2.0, "rsi_high": 75.0, "rsi_low": 25.0, "stop_atr": 1.25}


def implied_nse_price(adr_close_usd: float, usdinr: float, ratio: float) -> float:
    return adr_close_usd * usdinr / ratio


def expected_gap_pct(adr_pct: float, usdinr_pct: float = 0.0) -> float:
    """ADR's move since India's close plus the rupee's move (a weaker rupee lifts the rupee value of the ADR)."""
    return adr_pct + usdinr_pct


def classify_regime(sym: str, ctx: dict, cfg: dict | None = None) -> dict:
    """ctx: adr_pct {nse symbol: % since India's close}, adr_vol_x {symbol: US volume / 20-day average},
    nifty_gap_pct (GIFT Nifty or the pre-open), vix_pct, brent_pct, usdinr_pct, first15_vol_x {symbol: x} (None before 09:30)."""
    c = {**DEFAULTS, **(cfg or {})}
    adr = ctx.get("adr_pct") or {}
    own = adr.get(sym)
    ng = ctx.get("nifty_gap_pct") or 0.0
    if abs(ng) > c["macro_gap_pct"] or (ctx.get("vix_pct") or 0) > c["vix_spike_pct"] \
            or abs(ctx.get("brent_pct") or 0) >= c["brent_shock_pct"] or abs(ctx.get("usdinr_pct") or 0) >= c["usdinr_shock_pct"]:
        d = 1 if ng > 0 else -1
        trig = "gap" if abs(ng) > c["macro_gap_pct"] or (ctx.get("vix_pct") or 0) > c["vix_spike_pct"] else "oil-fx"
        return {"regime": 1, "name": "macro shock", "direction": "up" if d > 0 else "down", "trigger": trig,
                "why": f"Nifty gap {ng:+.2f}%, VIX {ctx.get('vix_pct') or 0:+.1f}%, Brent {ctx.get('brent_pct') or 0:+.1f}%, "
                       f"USD-INR {ctx.get('usdinr_pct') or 0:+.2f}%"}
    sector = PAIRS[sym].sector
    mates = [adr.get(s) for s, p in PAIRS.items() if p.sector == sector]
    if len(mates) >= 2 and all(m is not None for m in mates) and abs(ng) <= c["sector_nifty_band_pct"] \
            and (all(m >= c["sector_adr_pct"] for m in mates) or all(m <= -c["sector_adr_pct"] for m in mates)):
        up = mates[0] > 0
        return {"regime": 2, "name": "sector catalyst", "direction": "up" if up else "down",
                "why": f"both {sector} ADRs moved {', '.join(f'{m:+.1f}%' for m in mates)}; Nifty gap {ng:+.2f}%"}
    vx = (ctx.get("adr_vol_x") or {}).get(sym)
    if own is not None and abs(own) >= c["stock_adr_pct"] and (vx or 0) >= c["stock_adr_vol_x"]:
        return {"regime": 3, "name": "stock catalyst", "direction": "up" if own > 0 else "down",
                "why": f"ADR {own:+.1f}% on {vx:.1f}x its usual US volume"}
    f15 = (ctx.get("first15_vol_x") or {}).get(sym)
    if own is not None and abs(own) < c["normal_adr_pct"] and abs(ng) <= c["normal_nifty_band_pct"] \
            and (f15 is None or f15 < c["normal_first15_vol_x"]):
        return {"regime": 4, "name": "normal", "direction": None,
                "why": f"ADR {own:+.1f}%, Nifty gap {ng:+.2f}%, first-15-min volume {f15 if f15 is not None else 'n/a'}x"}
    return {"regime": 0, "name": "unclear", "direction": None,
            "why": f"ADR {own if own is not None else float('nan'):+.1f}% without a clear driver: no trade"}


def atr14(daily: pd.DataFrame) -> float:
    pc = daily["Close"].shift(1)
    tr = pd.concat([daily["High"] - daily["Low"], (daily["High"] - pc).abs(), (daily["Low"] - pc).abs()], axis=1).max(axis=1)
    return float(tr.tail(14).mean())


def rsi(close: pd.Series, n: int = 14) -> pd.Series:
    d = close.diff()
    up, dn = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean(), (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn.replace(0, np.nan))


def vwap_bands(bars: pd.DataFrame, k: float = 2.0) -> pd.DataFrame:
    """Intraday VWAP with volume-weighted standard-deviation bands (one session's bars)."""
    tp = (bars["High"] + bars["Low"] + bars["Close"]) / 3
    v = bars["Volume"].replace(0, np.nan).fillna(1.0)
    cv = v.cumsum()
    vwap = (tp * v).cumsum() / cv
    sd = np.sqrt(((tp ** 2 * v).cumsum() / cv - vwap ** 2).clip(lower=0))
    return pd.DataFrame({"vwap": vwap, "upper": vwap + k * sd, "lower": vwap - k * sd})


def detect_exhaustion(bars: pd.DataFrame, rsi5: pd.Series, atr: float, prev: dict, oi_wall: dict | None = None,
                      cfg: dict | None = None) -> dict:
    """Latest 5-minute bar of today's `bars`: which exhaustion checks fire, and on which side.
    prev: {"high", "low", "close"} of the previous day. oi_wall (optional): {"call": strike, "put": strike}."""
    c = {**DEFAULTS, **(cfg or {})}
    b, o = bars.iloc[-1], float(bars["Open"].iloc[0])
    vb = vwap_bands(bars, c["vwap_sd"]).iloc[-1]
    pivot = (prev["high"] + prev["low"] + prev["close"]) / 3
    r1, s1 = 2 * pivot - prev["low"], 2 * pivot - prev["high"]
    falling_vol = len(bars) >= 2 and b["Volume"] < bars["Volume"].iloc[-2]
    r = float(rsi5.iloc[-1]) if len(rsi5) and pd.notna(rsi5.iloc[-1]) else 50.0
    near = lambda x, lvl: abs(x / lvl - 1) * 100 <= 0.3
    up = {"atr": b["High"] >= o + c["atr_stretch"] * atr and (near(b["High"], prev["high"]) or near(b["High"], r1)
                                                               or b["High"] >= max(prev["high"], r1)),
          "vwap": b["High"] >= vb["upper"] and falling_vol, "rsi": r > c["rsi_high"]}
    dn = {"atr": b["Low"] <= o - c["atr_stretch"] * atr and (near(b["Low"], prev["low"]) or near(b["Low"], s1)
                                                              or b["Low"] <= min(prev["low"], s1)),
          "vwap": b["Low"] <= vb["lower"] and falling_vol, "rsi": r < c["rsi_low"]}
    if oi_wall:
        up["oi"] = bool(oi_wall.get("call")) and b["High"] >= oi_wall["call"] * 0.997
        dn["oi"] = bool(oi_wall.get("put")) and b["Low"] <= oi_wall["put"] * 1.003
    side = "up" if sum(up.values()) > sum(dn.values()) else "down" if sum(dn.values()) > 0 else None
    checks = up if side == "up" else dn
    return {"side": side, "checks": {k: bool(v) for k, v in checks.items()}, "count": int(sum(checks.values())),
            "vwap": float(vb["vwap"]), "rsi": round(r, 1), "open": o, "atr": atr,
            "stop_spot": o + c["stop_atr"] * atr if side == "up" else o - c["stop_atr"] * atr}


def generate_trade_signal(sym: str, regime: dict, spot: float, exhaustion: dict | None = None, step: float | None = None) -> dict | None:
    """Buy-only signal: regimes 1-3 buy WITH the direction (CALL up / PUT down); regime 4 buys the reversal at an
    exhaustion point (PUT at upside exhaustion, CALL at downside), target = VWAP, stop = 1.25 ATR from the open."""
    if regime["regime"] in (1, 2, 3) and regime["direction"]:
        opt = "CE" if regime["direction"] == "up" else "PE"
        out = {"strategy": "debit momentum", "option": opt, "target": "10% on the premium or 15:20", "stop_spot": None}
    elif regime["regime"] == 4 and exhaustion and exhaustion.get("side"):
        opt = "PE" if exhaustion["side"] == "up" else "CE"
        out = {"strategy": "exhaustion reversal", "option": opt, "target_spot": round(exhaustion["vwap"], 2),
               "stop_spot": round(exhaustion["stop_spot"], 2), "checks": exhaustion["checks"]}
    else:
        return None
    if step:
        out["strike"] = round(spot / step) * step
    return {"symbol": sym, "regime": regime["regime"], "regime_name": regime["name"], "why": regime["why"], "spot": spot, **out}


# ------------------------------------------------------------------ live: overnight context and the trade rule

import json
from datetime import date, timedelta
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "journal" / "adr"
TEAM_DEFAULTS = {"enabled": True, "open_from": "09:16", "open_until": "09:30", "from": "10:15", "until": "10:45",
                 "targets": [10.0], "min_premium": 5.0}


def overnight_context(today: date) -> dict:
    """ADR move and US volume (vs 20 sessions) since India's previous session, rupee and Brent: Yahoo daily data.
    Measured the same way as the backtest: last close before `today` vs last close before India's previous trading day."""
    import yfinance as yf
    from . import holidays
    prev = holidays.previous_trading_day(today - timedelta(days=1))
    tickers = [p.adr for p in PAIRS.values()] + ["INR=X", "BZ=F"]
    raw = yf.download(tickers, period="3mo", interval="1d", group_by="ticker", progress=False, auto_adjust=False)

    def series(t, col="Close"):
        s = raw[t][col].dropna()
        s.index = pd.to_datetime(s.index).tz_localize(None).normalize()
        return s

    def move(t):
        c = series(t)
        a, b = c[c.index < pd.Timestamp(today)], c[c.index < pd.Timestamp(prev)]
        return round((float(a.iloc[-1]) / float(b.iloc[-1]) - 1) * 100, 2) if len(a) and len(b) else None
    ctx = {"date": today.isoformat(), "adr_pct": {}, "adr_vol_x": {}, "usdinr_pct": move("INR=X"), "brent_pct": move("BZ=F")}
    for s, p in PAIRS.items():
        ctx["adr_pct"][s] = move(p.adr)
        v = series(p.adr, "Volume")
        v = v[v.index < pd.Timestamp(today)]
        if len(v) > 21 and v.iloc[-21:-1].mean() > 0:
            ctx["adr_vol_x"][s] = round(float(v.iloc[-1] / v.iloc[-21:-1].mean()), 2)
    return ctx


def nifty_gap_fallback(today: date) -> float | None:
    """Nifty's opening gap % when INDmoney does not give it: NSE's live index feed, then Yahoo."""
    try:
        from . import nse_mcp
        q = nse_mcp.live_index("NIFTY 50")
        o, pc = nse_mcp._f(q, "open", "dayOpen"), nse_mcp._f(q, "previousClose", "prevClose")
        if o and pc:
            return round((o / pc - 1) * 100, 2)
    except Exception:
        pass
    try:
        import yfinance as yf
        d = yf.Ticker("^NSEI").history(period="5d", interval="1d", auto_adjust=False)
        if len(d) >= 2 and d.index[-1].date() == today:
            return round((float(d["Open"].iloc[-1]) / float(d["Close"].iloc[-2]) - 1) * 100, 2)
    except Exception:
        pass
    return None


def open_decision(sym: str, regime: dict) -> dict | None:
    """At the open (16 Nov test, 2 years, hourly bars): on a stock catalyst the first hour carries on the ADR's way:
    buying WITH the ADR at the 09:15 open, 10% target: 50 trades, 82% hit, +Rs 40,430 (+20.0k / +20.4k). The same buy at
    10:15 lost Rs 45,262. (Macro gaps at the open: with the gap lost Rs 1.92 lakh; against it +Rs 70.9k but the first half lost.)"""
    if regime["regime"] == 3 and regime.get("direction"):
        return {"direction": regime["direction"], "rule": "stock-catalyst open", "why": regime["why"]}
    return None


def fade_decision(sym: str, regime: dict, first_hour_pct: float | None) -> dict | None:
    """What the 2-year test supports (backtest_adr_regimes.py, options bought at 10:15, 10% target, no stop-loss):
    - stock catalyst (ADR 2%+ on 1.5x volume): buy AGAINST the ADR's direction (50 trades, 70% hit, +Rs 30.5k, both halves;
      with it: -Rs 45.7k);
    - macro shock by a Nifty gap of 1.2%+: buy AGAINST the gap, only if the stock's first hour already turned that way
      (67 trades, 61% hit, +Rs 36.3k, both halves; with the gap: -Rs 78.8k).
    Sector days, oil/rupee-only shocks and normal days: no tested edge -> no trade."""
    if regime["regime"] == 3:
        d = "down" if regime["direction"] == "up" else "up"
        return {"direction": d, "rule": "stock-catalyst fade", "why": regime["why"]}
    if regime["regime"] == 1 and regime.get("trigger") == "gap" and first_hour_pct is not None:
        d = "down" if regime["direction"] == "up" else "up"
        if first_hour_pct * (1 if d == "up" else -1) > 0:
            return {"direction": d, "rule": "macro-gap fade", "why": f"{regime['why']}; first hour {first_hour_pct:+.2f}% (turning)"}
    return None


def save(day: date, data: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{day.isoformat()}.json").write_text(json.dumps(data, indent=1, default=str))
