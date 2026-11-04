"""Probability Analyzer (user's design, 31 Oct 2026): a gatekeeper that asks "how likely is the target,
and is the trade worth it after costs?" before a trade is opened.

Adapted to the desk's rules: the target is the only planned exit (no stop-loss) and every trade is
squared off at 15:20, so "target before stop" becomes "target before square-off".

Four readings, blended into one report:
1. Historical base rate: how often trades like this one (same strategy, side, time of day, volume
   spurt size) reached the target in the backtest, shrunk towards the overall rate when few match.
2. Monte Carlo: 2,000 possible futures for the stock, built by re-sampling its own recent 5-minute
   moves (so fat tails and its usual swings are kept), with the option re-priced on every step.
   Gives the chance of touching the target, the expected net P&L after all charges, and the
   average of the worst 5% of outcomes.
3. Learned score: a small logistic regression on past trades' features (fitted on earlier trades
   only), the "ML confidence".
4. Expected value: blended hit chance x profit at target + miss chance x the average loss when the
   target is missed (from the Monte Carlo), in % of the premium paid.

`assess()` approves when the blended chance and the expected value clear `config.yaml -> probability`.
"""
import json
import math
from datetime import date, datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from .costs import round_trip_charges

IST = ZoneInfo("Asia/Kolkata")
MODEL = Path(__file__).resolve().parent.parent / "journal" / "probability_model.json"
LOG = Path(__file__).resolve().parent.parent / "journal" / "probability.csv"

DEFAULTS = {
    "mode": "observe",          # observe: log only; gate: block trades it rejects
    "min_blended_prob": None,   # None: use the model's own cut (reject the weakest `reject_share` of past trades)
    "reject_share": 0.33,
    "min_expected_value_pct": None,  # optional extra floor, % of premium after charges and the bid-ask gap
    "simulations": 2000,
    "lookback_days": 20,        # 5-minute moves re-sampled for the futures
    "weights": {"base": 1.0, "monte_carlo": 1.0, "ml": 1.0},
    "prior_strength": 20,       # base rate: how many trades' worth of weight the overall rate gets
}

FEATURES = ["minutes_from_open", "volume_x", "abs_move_pct", "call", "sigma_ratio"]


def _ncdf(x):
    """Normal CDF on numpy arrays (Abramowitz-Stegun 7.1.26 erf, error < 1.5e-7; no scipy here)."""
    z = np.asarray(x, dtype=float) / math.sqrt(2.0)
    s, a = np.sign(z), np.abs(z)
    t = 1.0 / (1.0 + 0.3275911 * a)
    poly = t * (0.254829592 + t * (-0.284496736 + t * (1.421413741 + t * (-1.453152027 + t * 1.061405429))))
    return 0.5 * (1.0 + s * (1.0 - poly * np.exp(-a * a)))


def bs_price(spot, strike: float, years, rate: float, vol: float, is_call: bool):
    """Black-Scholes price, vectorised over spot and time (numpy arrays)."""
    spot = np.maximum(np.asarray(spot, dtype=float), 0.01)
    years = np.maximum(np.asarray(years, dtype=float), 1.0 / 365.0)
    vol = max(vol, 0.01)
    sq = vol * np.sqrt(years)
    d1 = (np.log(spot / strike) + (rate + 0.5 * vol * vol) * years) / sq
    d2 = d1 - sq
    df = np.exp(-rate * years)
    if is_call:
        return spot * _ncdf(d1) - strike * df * _ncdf(d2)
    return strike * df * _ncdf(-d2) - spot * _ncdf(-d1)


def _years_to_expiry(expiry, at: datetime) -> float:
    exp = expiry if isinstance(expiry, date) else date.fromisoformat(str(expiry)[:10])
    close = datetime.combine(exp, time(15, 30), IST)
    return max((close - at).total_seconds() / (365 * 86400), 1 / 365)


def recent_returns(intra: pd.DataFrame, before: datetime, days: int = 20) -> np.ndarray:
    """5-minute log returns of the stock within sessions (no overnight gaps), last `days` sessions."""
    hist = intra[intra.index < before]
    sessions = sorted(set(hist.index.date))[-days:]
    hist = hist[np.isin(hist.index.date, sessions)]
    r = np.log(hist["Close"]).groupby(hist.index.date).diff().dropna()
    r = r[np.isfinite(r)]
    return r.to_numpy()


def monte_carlo(option: dict, spot: float, entry: float, target: float, qty: int, now: datetime,
                square_off: datetime, returns: np.ndarray, cfg: dict, n: int = 2000,
                seed: int | None = None) -> dict | None:
    """Re-sample `returns` into n paths from now to square-off (5-minute steps); the option is
    re-priced each step at its bid (model mid less half the bid-ask gap). A path that touches the
    target bid exits there; the rest are sold at square-off. Returns the hit chance and the net P&L
    distribution after charges."""
    steps = int((square_off - now).total_seconds() // 300)
    if steps < 1 or len(returns) < 30 or entry <= 0:
        return None
    rng = np.random.default_rng(seed)
    r = returns - returns.mean()  # no drift: the direction is the strategy's call, not the sample's
    paths = spot * np.exp(np.cumsum(rng.choice(r, size=(n, steps)), axis=1))
    times = [now + pd.Timedelta(minutes=5 * (k + 1)) for k in range(steps)]
    years = np.array([_years_to_expiry(option["expiry"], t) for t in times])
    is_call = option["type"] == "CE"
    half = cfg.get("assumed_spread_pct", 1.0) / 200
    bid = bs_price(paths, float(option["strike"]), years[None, :], cfg.get("risk_free_rate", 0.065),
                   float(option.get("iv_used") or 0.3), is_call) * (1 - half)
    hit = (bid >= target).any(axis=1)
    exit_px = np.where(hit, target, bid[:, -1])
    rates = cfg["charges"]
    charges = np.array([round_trip_charges(entry, float(x), qty, rates)["total"] for x in np.round(exit_px, 1)]) \
        if n <= 500 else _charges_fast(entry, exit_px, qty, rates)
    pnl_pct = ((exit_px - entry) * qty - charges) / (entry * qty) * 100
    miss = pnl_pct[~hit]
    worst = np.sort(pnl_pct)[: max(1, n // 20)]
    return {"prob": float(hit.mean()), "ev_pct": float(pnl_pct.mean()),
            "win_pct": float(pnl_pct[hit].mean()) if hit.any() else 0.0,
            "miss_pct": float(miss.mean()) if len(miss) else 0.0,
            "worst5_pct": float(worst.mean()), "median_pct": float(np.median(pnl_pct))}


def _charges_fast(entry: float, exit_px: np.ndarray, qty: int, rates: dict) -> np.ndarray:
    """Charges on a grid of exit prices, interpolated (round_trip_charges is per trade)."""
    lo, hi = float(exit_px.min()), float(exit_px.max())
    grid = np.linspace(lo, hi if hi > lo else lo + 1, 41)
    vals = np.array([round_trip_charges(entry, float(x), qty, rates)["total"] for x in grid])
    return np.interp(exit_px, grid, vals)


def features(sig: dict) -> dict:
    """Numbers the base rate and the learned score use. `sig` keys: opened (HH:MM), volume_x,
    move_pct, side, sigma_ratio (today's 5-minute swing vs its recent usual)."""
    h, m = str(sig.get("opened", "09:30")).split(":")
    return {"minutes_from_open": (int(h) * 60 + int(m)) - (9 * 60 + 15),
            "volume_x": float(sig.get("volume_x") or 0.0),
            "abs_move_pct": abs(float(sig.get("move_pct") or 0.0)),
            "call": 1.0 if sig.get("side") == "loser" else 0.0,
            "sigma_ratio": float(sig.get("sigma_ratio") or 1.0)}


def _bucket(f: dict) -> str:
    t = "early" if f["minutes_from_open"] < 75 else "mid" if f["minutes_from_open"] < 225 else "late"
    v = "v<2" if f["volume_x"] < 2 else "v2+"
    return f"{t}|{v}|{'call' if f['call'] else 'put'}"


def fit(trades: pd.DataFrame, l2: float = 1.0, iters: int = 400) -> dict:
    """Base-rate table and logistic regression from past trades (needs FEATURES + `hit` columns)."""
    X = trades[FEATURES].to_numpy(dtype=float)
    y = trades["hit"].to_numpy(dtype=float)
    mu, sd = X.mean(axis=0), X.std(axis=0)
    sd[sd == 0] = 1.0
    Z = np.c_[np.ones(len(X)), (X - mu) / sd]
    w = np.zeros(Z.shape[1])
    for _ in range(iters):  # Newton steps with an L2 penalty (no intercept penalty)
        p = 1 / (1 + np.exp(-Z @ w))
        reg = np.r_[0.0, np.full(len(w) - 1, l2)]
        g = Z.T @ (p - y) + reg * w
        H = (Z * (p * (1 - p))[:, None]).T @ Z + np.diag(reg + 1e-9)
        step = np.linalg.solve(H, g)
        w -= step
        if np.abs(step).max() < 1e-6:
            break
    buckets = {}
    for b, g in trades.assign(bucket=[_bucket(dict(zip(FEATURES, row))) for row in X]).groupby("bucket"):
        buckets[b] = {"n": int(len(g)), "hits": int(g["hit"].sum())}
    return {"overall": float(y.mean()), "n": int(len(y)), "buckets": buckets,
            "mu": mu.tolist(), "sd": sd.tolist(), "w": w.tolist()}


def base_rate(model: dict, f: dict, prior_strength: float = 20) -> float:
    b = model["buckets"].get(_bucket(f), {"n": 0, "hits": 0})
    a = model["overall"] * prior_strength
    return (b["hits"] + a) / (b["n"] + prior_strength)


def ml_score(model: dict, f: dict) -> float:
    x = (np.array([f[k] for k in FEATURES]) - np.array(model["mu"])) / np.array(model["sd"])
    z = model["w"][0] + float(np.dot(model["w"][1:], x))
    return float(1 / (1 + math.exp(-max(min(z, 30), -30))))


def set_cut(model: dict, past: list[dict], cfg: dict | None = None) -> dict:
    """The blended-chance cut that rejects the weakest `reject_share` of past trades (each judged
    with `model`, Monte Carlo fields mc_prob/mc_win_pct/mc_miss_pct/mc_worst5_pct when present)."""
    c = {**DEFAULTS, **(cfg or {}), "min_blended_prob": 0.0, "min_expected_value_pct": None}
    vals = [assess(r, _mc_of(r), model, c)["blended_prob"] for r in past]
    model["cut"] = float(np.quantile(vals, c["reject_share"])) if vals else None
    return model


def _mc_of(r: dict) -> dict | None:
    if r.get("mc_prob") is None or (isinstance(r.get("mc_prob"), float) and math.isnan(r["mc_prob"])):
        return None
    return {"prob": r["mc_prob"], "win_pct": r["mc_win_pct"], "miss_pct": r["mc_miss_pct"],
            "worst5_pct": r["mc_worst5_pct"]}


def load_model() -> dict | None:
    try:
        return json.loads(MODEL.read_text())
    except (OSError, ValueError):
        return None


def assess(sig: dict, mc: dict | None, model: dict | None, cfg: dict | None = None) -> dict:
    """The Probability Report: base rate, Monte Carlo chance, learned score, blended chance,
    expected value (% of premium, after charges) and the verdict."""
    c = {**DEFAULTS, **(cfg or {})}
    f = features(sig)
    parts, w = {}, c["weights"]
    if model:
        parts["base"] = base_rate(model, f, c["prior_strength"])
        parts["ml"] = ml_score(model, f)
    if mc:
        parts["monte_carlo"] = mc["prob"]
    if not parts:
        return {"approved": True, "rejection_reason": "no data to judge (approved by default)"}
    total = sum(w.get(k, 1.0) for k in parts)
    blended = sum(p * w.get(k, 1.0) for k, p in parts.items()) / total
    if mc:
        ev = blended * mc["win_pct"] + (1 - blended) * mc["miss_pct"]
    else:
        ev = None
    reasons = []
    floor = c["min_blended_prob"] if c["min_blended_prob"] is not None else (model or {}).get("cut")
    if floor is not None and blended < floor:
        reasons.append(f"blended chance {blended:.0%} is in the weakest group (< {floor:.0%})")
    if ev is not None and c["min_expected_value_pct"] is not None and ev < c["min_expected_value_pct"]:
        reasons.append(f"expected value {ev:+.1f}% < {c['min_expected_value_pct']:+.1f}%")
    return {"historical_win_rate": round(parts.get("base", float("nan")), 3),
            "monte_carlo_target_prob": round(parts.get("monte_carlo", float("nan")), 3),
            "ml_confidence_score": round(parts.get("ml", float("nan")), 3),
            "blended_prob": round(blended, 3),
            "expected_value_pct": round(ev, 2) if ev is not None else None,
            "worst5_pct": round(mc["worst5_pct"], 1) if mc else None,
            "approved": not reasons, "rejection_reason": "; ".join(reasons) or None}


def sigma_ratio(intra: pd.DataFrame, now: datetime, days: int = 20) -> float:
    """Today's 5-minute swing so far vs the stock's recent usual (1.0 = normal day)."""
    usual = recent_returns(intra, datetime.combine(now.date(), time(0, 0), now.tzinfo), days)
    today = intra[(intra.index.date == now.date()) & (intra.index <= now)]
    r = np.log(today["Close"]).diff().dropna()
    return float(r.std() / usual.std()) if len(r) > 2 and len(usual) > 30 and usual.std() > 0 else 1.0


def save_model(model: dict) -> None:
    MODEL.write_text(json.dumps(model, indent=1))


def log(now: datetime, symbol: str, contract: str, report: dict) -> None:
    """One row per signal (observe mode), for the evening review."""
    row = {"date": now.date().isoformat(), "time": now.strftime("%H:%M"), "symbol": symbol,
           "contract": contract, **{k: report.get(k) for k in
           ("historical_win_rate", "monte_carlo_target_prob", "ml_confidence_score", "blended_prob",
            "expected_value_pct", "worst5_pct", "approved", "rejection_reason")}}
    pd.DataFrame([row]).to_csv(LOG, mode="a", header=not LOG.exists(), index=False)
