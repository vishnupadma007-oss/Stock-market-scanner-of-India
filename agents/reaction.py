"""Results Reaction analyst: how much will the stock move on these results?

It learns from history. For every F&O stock it reads the last ~3 years of results filings on
NSE (the same PDFs the Announcements agent reads live) and the prices around each one, so it
knows, for each past quarter: how strong the numbers were, whether they beat the company's own
recent trend, how much the stock had run up before, and how it reacted (gap at the open, close).

From all stocks together it fits a simple model:

    stock move minus Nifty move  ~  profit surprise + revenue surprise + run-up before results

"Surprise" is growth versus the company's own last four quarters, because free consensus
estimates are not available: a company that usually grows 30% and reports 15% disappoints.
Each stock keeps its own habits on top of that (some always fall on results, some move 2%,
others 8%), and the market's likely open (from US stocks and crude overnight) is added.

Output: expected gap at the open and expected close, each with a likely range, and the chance
the stock ends the day up. It is a statistical estimate from about a dozen quarters per stock,
not a promise: the ranges say how wrong it usually is.

    python -m agents.reaction build              # read the history for every stock (slow, once)
    python -m agents.reaction TECHM              # scenarios before results: strong / in line / weak
    python -m agents.reaction market             # tomorrow's likely Nifty open from global cues
"""
import json
import math
import sys
import time as clock
from datetime import date, datetime, time, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from . import announcements, holidays

DIR = Path(__file__).resolve().parent.parent / "journal" / "results_history"
MODEL = Path(__file__).resolve().parent.parent / "journal" / "reaction_model.json"
OPEN, CLOSE = time(9, 15), time(15, 30)
CLIP = 100.0  # growth figures are capped at +/-100% so one-off swings do not dominate the fit
FEATURES = ["profit_surprise", "revenue_surprise", "runup_20d"]


# ---------------------------------------------------------------- prices

_prices: dict[str, pd.DataFrame] = {}


def prices(ticker: str, years: int = 4) -> pd.DataFrame:
    """Daily prices from Yahoo (free history; INDmoney's call budget is kept for live trading)."""
    if ticker not in _prices:
        import yfinance as yf
        df = yf.Ticker(ticker).history(period=f"{years}y", interval="1d", auto_adjust=False)
        df.index = df.index.tz_localize(None).normalize() if df.index.tz is not None else df.index.normalize()
        _prices[ticker] = df[["Open", "High", "Low", "Close"]].dropna()
    return _prices[ticker]


def reaction_day(filed: datetime, trading_days: pd.DatetimeIndex) -> tuple[pd.Timestamp | None, str]:
    """The session that first trades on the results, and whether the news came 'before open',
    'during market' or 'after close'."""
    day = pd.Timestamp(filed.date())
    if day in trading_days and filed.time() < OPEN:
        return day, "before open"
    if day in trading_days and filed.time() <= CLOSE:
        return day, "during market"
    later = trading_days[trading_days > day]
    return (later[0] if len(later) else None), "after close"


def measure(stock: pd.DataFrame, nifty: pd.DataFrame, filed: datetime) -> dict | None:
    """How the stock reacted to results filed at `filed`."""
    day, when = reaction_day(filed, stock.index)
    if day is None or day not in nifty.index:
        return None
    i = stock.index.get_loc(day)
    if i < 21:
        return None
    prev, today = stock.iloc[i - 1], stock.iloc[i]
    n_prev, n_today = nifty.loc[nifty.index < day].iloc[-1], nifty.loc[day]
    before = stock.iloc[i - 21:i]["Close"]
    n_before = nifty.loc[nifty.index < day].iloc[-21:]["Close"]
    out = {
        "reaction_day": day.date().isoformat(), "when": when,
        "gap_pct": round((today["Open"] / prev["Close"] - 1) * 100, 2),
        "close_pct": round((today["Close"] / prev["Close"] - 1) * 100, 2),
        "high_pct": round((today["High"] / prev["Close"] - 1) * 100, 2),
        "low_pct": round((today["Low"] / prev["Close"] - 1) * 100, 2),
        "nifty_gap_pct": round((n_today["Open"] / n_prev["Close"] - 1) * 100, 2),
        "nifty_close_pct": round((n_today["Close"] / n_prev["Close"] - 1) * 100, 2),
        "runup_20d": round(((before.iloc[-1] / before.iloc[0]) - (n_before.iloc[-1] / n_before.iloc[0])) * 100, 2),
    }
    out["excess_close_pct"] = round(out["close_pct"] - out["nifty_close_pct"], 2)
    # Results out during market hours: the open came before the news, so there is no results gap.
    out["excess_gap_pct"] = round(out["gap_pct"] - out["nifty_gap_pct"], 2) if when != "during market" else None
    return out


# ---------------------------------------------------------------- results history

def results_filings(symbol: str, start: date, end: date) -> list[dict]:
    """One filing per quarter: the first 'financial results' filing, skipping copies a few days later."""
    rows = []
    for chunk_start in pd.date_range(start, end, freq="365D"):
        chunk_end = min(end, (chunk_start + timedelta(days=364)).date())
        rows += announcements.fetch_feed(symbol=symbol, start=chunk_start.date(), end=chunk_end)
        clock.sleep(0.5)
    picked = []
    for r in sorted(rows, key=lambda r: r["sort_date"]):
        text = f"{r.get('desc', '')} {r.get('attchmntText', '')}".lower()
        if announcements.classify(r) != "RESULTS" or "no change in financial results" in text \
                or not str(r.get("attchmntFile", "")).endswith(".pdf"):
            continue
        t = datetime.strptime(r["sort_date"], "%Y-%m-%d %H:%M:%S")
        if picked and (t - picked[-1]["filed"]).days < 20:
            continue  # same quarter: press release, integrated filing, corrections
        picked.append({"filed": t, "seq_id": str(r["seq_id"]), "pdf": r["attchmntFile"]})
    return picked


def _clip(x):
    return None if x is None else max(-CLIP, min(CLIP, x))


def add_surprises(quarters: list[dict]) -> list[dict]:
    """Growth versus the company's own last four quarters (the market expects the trend to go on)."""
    for i, q in enumerate(quarters):
        for key in ("profit", "revenue"):
            yoy = _clip((q.get("figures", {}).get(key) or {}).get("yoy_pct"))
            past = [_clip((p.get("figures", {}).get(key) or {}).get("yoy_pct")) for p in quarters[max(0, i - 4):i]]
            past = [p for p in past if p is not None]
            q[f"{key}_yoy"] = yoy
            q[f"{key}_surprise"] = round(yoy - float(np.median(past)), 1) if yoy is not None and past else None
    return quarters


def build_history(symbol: str, years: int = 3, refresh: bool = False) -> list[dict]:
    """Past quarters with figures and the price reaction, cached in journal/results_history/."""
    path = DIR / f"{symbol}.json"
    cached = {q["seq_id"]: q for q in json.loads(path.read_text())} if path.exists() and not refresh else {}
    end = date.today()
    filings = results_filings(symbol, end - timedelta(days=365 * years), end)
    stock, nifty = prices(f"{symbol}.NS"), prices("^NSEI")
    quarters = []
    for f in filings:
        q = cached.get(f["seq_id"])
        if q is None or q.get("reaction") is None:
            q = {"seq_id": f["seq_id"], "filed": f["filed"].strftime("%Y-%m-%d %H:%M:%S"), "pdf": f["pdf"]}
            try:
                q["figures"] = announcements.figures_from_text(announcements.pdf_text(f["pdf"]))
            except Exception as e:
                q["figures"], q["error"] = {}, type(e).__name__
            q["view"] = announcements.score_results(q["figures"])["view"] if q["figures"] else "unread"
            q["reaction"] = measure(stock, nifty, f["filed"])
            clock.sleep(1)
        quarters.append(q)
    quarters = add_surprises(quarters)
    DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(quarters, indent=1))
    return quarters


def load_history(symbol: str) -> list[dict]:
    path = DIR / f"{symbol}.json"
    return json.loads(path.read_text()) if path.exists() else []


# ---------------------------------------------------------------- model

def dataset(universe: list[str]) -> pd.DataFrame:
    rows = []
    for s in universe:
        for q in load_history(s):
            r = q.get("reaction")
            if r:  # quarters whose figures could not be read still show the stock's usual move size
                rows.append({"symbol": s, "profit_surprise": q.get("profit_surprise"),
                             "revenue_surprise": q.get("revenue_surprise") or 0.0, **r})
    return pd.DataFrame(rows)


def fit(df: pd.DataFrame) -> dict:
    """Least squares for the close and the gap (stock minus Nifty), plus each stock's own habits."""
    model = {"n_quarters": len(df), "fitted": datetime.now().strftime("%Y-%m-%d %H:%M"), "targets": {}}
    full = df
    df = df[df["profit_surprise"].notna()].reset_index(drop=True)  # the fit needs the figures
    model["n"] = len(df)
    if len(df) < 30:
        return model
    X = np.column_stack([np.ones(len(df))] + [df[f].astype(float).values for f in FEATURES])
    for target in ("excess_close_pct", "excess_gap_pct"):
        ok = df[target].notna().values
        y = df[target].astype(float).values[ok]
        coef, *_ = np.linalg.lstsq(X[ok], y, rcond=None)
        resid = y - X[ok] @ coef
        r2 = 1 - resid.var() / y.var() if y.var() else 0.0
        model["targets"][target] = {"coef": dict(zip(["const"] + FEATURES, np.round(coef, 4))),
                                    "resid_sd": round(float(resid.std()), 2), "r2": round(float(r2), 3)}
    # Direction hit rate of the close model (would it have called up/down right?).
    pred = X @ np.array(list(model["targets"]["excess_close_pct"]["coef"].values()))
    model["direction_hit_pct"] = round(float(((pred > 0) == (df["excess_close_pct"] > 0)).mean() * 100), 1)
    habits = {}
    coef = np.array(list(model["targets"]["excess_close_pct"]["coef"].values()))
    for s, g_all in full.groupby("symbol"):
        g = g_all[g_all["profit_surprise"].notna()]
        Xs = np.column_stack([np.ones(len(g))] + [g[f].astype(float).values for f in FEATURES])
        res = g["excess_close_pct"].astype(float).values - Xs @ coef
        # Habit (bias) needs figures; the usual move size uses every results day.
        size = g_all["excess_close_pct"].astype(float)
        habits[s] = {"n": len(g), "bias": round(float(res.mean()), 2) if len(g) else 0.0,
                     "resid_sd": round(float(res.std()), 2) if len(g) >= 4 else None,
                     "move_sd": round(float(size.std()), 2) if len(size) >= 4 else None,
                     "typical_abs_move": round(float(g_all["close_pct"].abs().median()), 2),
                     "typical_abs_gap": round(float(g_all.loc[g_all["when"] != "during market", "gap_pct"].abs().median()), 2)}
    model["stocks"] = habits
    return model


def load_model() -> dict:
    return json.loads(MODEL.read_text()) if MODEL.exists() else {}


def _ncdf(x: float) -> float:
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def predict(symbol: str, features: dict, model: dict, market_gap: float = 0.0, beta: float = 1.0) -> dict:
    """Expected gap and close (%), likely ranges and the chance of closing up."""
    t = model.get("targets", {})
    if "excess_close_pct" not in t:
        return {"error": "model not built yet: python -m agents.reaction build"}
    h = model.get("stocks", {}).get(symbol, {"n": 0, "bias": 0.0, "resid_sd": None})
    shrink = h["n"] / (h["n"] + 6)  # a stock's own habit counts more as its history grows

    def one(target: str) -> tuple[float, float]:
        c = t[target]["coef"]
        x = c["const"] + sum(c[f] * float(features.get(f) or 0.0) for f in FEATURES)
        if target == "excess_close_pct":
            x += shrink * h["bias"]
        sd = t[target]["resid_sd"]
        stock_sd = h.get("resid_sd") or h.get("move_sd")  # how far off it usually is for THIS stock
        if target == "excess_close_pct" and stock_sd:
            w = max(shrink, 0.5) if not h.get("resid_sd") else shrink
            sd = w * stock_sd + (1 - w) * sd
        return x, sd

    close_x, close_sd = one("excess_close_pct")
    gap_x, gap_sd = one("excess_gap_pct")
    close = close_x + beta * market_gap
    gap = gap_x + beta * market_gap
    return {"expected_gap_pct": round(gap, 1), "gap_range_pct": [round(gap - gap_sd, 1), round(gap + gap_sd, 1)],
            "expected_close_pct": round(close, 1),
            "close_range_pct": [round(close - close_sd, 1), round(close + close_sd, 1)],
            "chance_up_pct": round(_ncdf(close / close_sd) * 100) if close_sd else None,
            "typical_results_move_pct": h.get("typical_abs_move"), "history_quarters": h["n"],
            "market_gap_used_pct": round(market_gap, 2)}


def features_for(symbol: str, figures: dict, runup_20d: float | None, history: list[dict] | None = None) -> dict:
    """Surprise of new figures against the stock's own last four quarters."""
    history = history if history is not None else load_history(symbol)
    q = add_surprises([*history[-4:], {"figures": figures}])[-1]
    return {"profit_surprise": q["profit_surprise"], "revenue_surprise": q["revenue_surprise"],
            "runup_20d": runup_20d, "profit_yoy": q["profit_yoy"], "revenue_yoy": q["revenue_yoy"]}


def similar_quarters(symbol: str, profit_yoy: float | None, n: int = 3) -> list[dict]:
    hist = [q for q in load_history(symbol) if q.get("reaction") and q.get("profit_yoy") is not None]
    if profit_yoy is not None:
        hist.sort(key=lambda q: abs(q["profit_yoy"] - profit_yoy))
    return [{"filed": q["filed"][:10], "profit_yoy": q["profit_yoy"], "revenue_yoy": q.get("revenue_yoy"),
             "gap_pct": q["reaction"]["gap_pct"], "close_pct": q["reaction"]["close_pct"]} for q in hist[:n]]


def runup(symbol: str, before: date) -> float | None:
    try:
        s, n = prices(f"{symbol}.NS"), prices("^NSEI")
        s, n = s[s.index < pd.Timestamp(before)]["Close"].iloc[-21:], n[n.index < pd.Timestamp(before)]["Close"].iloc[-21:]
        return round(((s.iloc[-1] / s.iloc[0]) - (n.iloc[-1] / n.iloc[0])) * 100, 2)
    except Exception:
        return None


def forecast(symbol: str, figures: dict, filed: datetime, market_gap: float = 0.0) -> dict:
    """The full read for a results filing: features, prediction, similar past quarters, notes."""
    model = load_model()
    feats = features_for(symbol, figures, runup(symbol, filed.date() + timedelta(days=1)))
    out = {**predict(symbol, feats, model, market_gap), "features": feats,
           "similar_past_quarters": similar_quarters(symbol, feats["profit_yoy"])}
    notes = []
    if feats["profit_surprise"] is not None:
        notes.append(f"Profit growth {feats['profit_yoy']:+.0f}% YoY is {feats['profit_surprise']:+.0f} points "
                     f"vs its own last 4 quarters")
    if feats["runup_20d"] is not None and abs(feats["runup_20d"]) >= 5:
        notes.append(f"Already {'ran up' if feats['runup_20d'] > 0 else 'fell'} {feats['runup_20d']:+.1f}% vs Nifty "
                     f"in the 4 weeks before")
    if "expected_close_pct" in out:
        notes.append(f"Expected: open {out['expected_gap_pct']:+.1f}% (likely {out['gap_range_pct'][0]:+.1f} to "
                     f"{out['gap_range_pct'][1]:+.1f}), close {out['expected_close_pct']:+.1f}% (likely "
                     f"{out['close_range_pct'][0]:+.1f} to {out['close_range_pct'][1]:+.1f}), "
                     f"{out['chance_up_pct']}% chance of closing up")
    out["notes"] = notes
    return out


def scenarios(symbol: str, market_gap: float = 0.0) -> dict:
    """Before results: what each kind of quarter would likely do to the stock."""
    model, hist = load_model(), load_history(symbol)
    base = [q for q in hist if q.get("profit_yoy") is not None][-4:]
    trend_p = float(np.median([q["profit_yoy"] for q in base])) if base else 10.0
    trend_r = float(np.median([q["revenue_yoy"] for q in base if q.get("revenue_yoy") is not None] or [10.0]))
    ru = runup(symbol, date.today() + timedelta(days=1))
    out = {"usual_growth": {"profit_yoy": round(trend_p, 1), "revenue_yoy": round(trend_r, 1)}, "runup_20d": ru}
    for name, dp, dr in (("strong (beats its trend by 15 pts profit, 5 pts revenue)", 15, 5),
                         ("in line with its trend", 0, 0),
                         ("weak (misses by 15 pts profit, 5 pts revenue)", -15, -5)):
        out[name] = predict(symbol, {"profit_surprise": dp, "revenue_surprise": dr, "runup_20d": ru}, model, market_gap)
    out["past_reactions"] = [{"filed": q["filed"][:10], "view": q.get("view"), "profit_yoy": q.get("profit_yoy"),
                              "gap_pct": q["reaction"]["gap_pct"], "close_pct": q["reaction"]["close_pct"]}
                             for q in hist if q.get("reaction")][-6:]
    return out


def typical_move(symbol: str, days: int = 60) -> float | None:
    """The stock's usual daily move (median of |close-to-close|, last `days` sessions), in %."""
    try:
        c = prices(f"{symbol}.NS")["Close"].iloc[-days - 1:]
        return round(float((c.pct_change().abs() * 100).median()), 2)
    except Exception:
        return None


# ---------------------------------------------------------------- market open from global cues

def market_gap_model(years: int = 3) -> dict:
    """Nifty's open gap explained by the US session(s) and crude since India's last close."""
    nifty, spx, brent = prices("^NSEI", years), prices("^GSPC", years), prices("BZ=F", years)
    rows = []
    for i in range(1, len(nifty)):
        d, prev_d = nifty.index[i], nifty.index[i - 1]
        us = spx[(spx.index >= prev_d) & (spx.index < d)]
        oil = brent[(brent.index >= prev_d) & (brent.index < d)]
        prior_us = spx[spx.index < prev_d]
        prior_oil = brent[brent.index < prev_d]
        if us.empty or prior_us.empty or oil.empty or prior_oil.empty:
            continue
        rows.append({"gap": (nifty["Open"].iloc[i] / nifty["Close"].iloc[i - 1] - 1) * 100,
                     "spx": (us["Close"].iloc[-1] / prior_us["Close"].iloc[-1] - 1) * 100,
                     "brent": (oil["Close"].iloc[-1] / prior_oil["Close"].iloc[-1] - 1) * 100})
    df = pd.DataFrame(rows)
    X = np.column_stack([np.ones(len(df)), df["spx"], df["brent"]])
    coef, *_ = np.linalg.lstsq(X, df["gap"].values, rcond=None)
    resid = df["gap"].values - X @ coef
    return {"coef": {"const": round(coef[0], 4), "spx": round(coef[1], 4), "brent": round(coef[2], 4)},
            "resid_sd": round(float(resid.std()), 2), "r2": round(float(1 - resid.var() / df["gap"].var()), 3),
            "n": len(df)}


def expected_market_gap() -> dict:
    """Tomorrow's likely Nifty open: US stocks and Brent since India's last close."""
    gm = market_gap_model()
    nifty, spx, brent = prices("^NSEI"), prices("^GSPC"), prices("BZ=F")
    last_close = nifty.index[-1]
    us_now, us_then = spx["Close"].iloc[-1], spx[spx.index < last_close]["Close"].iloc[-1]
    oil_now, oil_then = brent["Close"].iloc[-1], brent[brent.index < last_close]["Close"].iloc[-1]
    spx_chg, oil_chg = (us_now / us_then - 1) * 100, (oil_now / oil_then - 1) * 100
    c = gm["coef"]
    gap = c["const"] + c["spx"] * spx_chg + c["brent"] * oil_chg
    return {"expected_nifty_gap_pct": round(gap, 2), "range_pct": [round(gap - gm["resid_sd"], 2), round(gap + gm["resid_sd"], 2)],
            "since_india_close": last_close.date().isoformat(), "spx_change_pct": round(spx_chg, 2),
            "brent_change_pct": round(oil_chg, 2), "model": gm}


# ---------------------------------------------------------------- CLI

def main(argv: list[str]) -> None:
    from .config import load_config
    cmd = argv[1] if len(argv) > 1 else ""
    if cmd == "build":
        universe = argv[2:] or load_config()["universe"]
        for s in universe:
            try:
                h = build_history(s)
                print(s, len(h), "quarters", sum(1 for q in h if q.get("figures")), "read", flush=True)
            except Exception as e:
                print(s, "failed:", type(e).__name__, e, flush=True)
        model = fit(dataset(load_config()["universe"]))
        MODEL.write_text(json.dumps(model, indent=1))
        print(json.dumps({k: v for k, v in model.items() if k != "stocks"}, indent=1))
    elif cmd == "market":
        print(json.dumps(expected_market_gap(), indent=1))
    elif cmd:
        print(json.dumps(scenarios(cmd.upper()), indent=1))
    else:
        print(__doc__)


if __name__ == "__main__":
    main(sys.argv)
