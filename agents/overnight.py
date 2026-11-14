"""Overnight gap forecast per stock (user, 14 Nov 2026): while the market is closed, how much should each
F&O stock open up or down, and after the pre-open, did the market already price it in?

expected gap = the stock's beta to Nifty's gap x tomorrow's expected Nifty gap (US stocks + Brent, agents/reaction)
             + the stock's own crude-oil sensitivity x Brent's overnight move (fitted, e.g. OMCs and paints down on oil up)
             + the results-reaction model's expected gap when it filed results since the last close.
Strong news views are attached as direction notes only (their size cannot be measured).

At 09:08 the NSE pre-open gives the actual gap; `compare` labels each stock:
  "priced in"     - the gap is already at/over the forecast the same way (little left: smaller target);
  "under-reacted" - same way but well short of the forecast (room left);
  "opposite"      - the market opens against the overnight picture;
  "as expected"   - small forecast, small gap.

    python -m agents.overnight fit        # fit betas (2 years of Yahoo daily data), journal/overnight_betas.json
    python -m agents.overnight            # today's forecast (and the pre-open comparison after 09:08)
    python -m agents.overnight evaluate   # out-of-sample check of the model
"""
import json
import sys
from datetime import date, datetime
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
BETAS = ROOT / "journal" / "overnight_betas.json"
OUT = ROOT / "journal" / "overnight"


def _daily(tickers: list[str], years: int = 2) -> dict[str, pd.DataFrame]:
    import yfinance as yf
    raw = yf.download(tickers, period=f"{years}y", interval="1d", group_by="ticker", progress=False, auto_adjust=False)
    out = {}
    for tk in tickers:
        if tk in raw.columns.get_level_values(0):
            d = raw[tk].dropna(subset=["Open", "Close"])
            d.index = pd.to_datetime(d.index).tz_localize(None).normalize()
            out[tk] = d
    return out


def gap_table(universe: list[str], years: int = 2) -> pd.DataFrame:
    """Rows = Indian trading days; columns: each stock's opening gap %, Nifty's gap %, S&P 500 and Brent moves
    since India's previous close (their last close before the Indian day)."""
    data = _daily([s + ".NS" for s in universe] + ["^NSEI", "^GSPC", "BZ=F"], years)
    nifty = data["^NSEI"]
    tab = pd.DataFrame(index=nifty.index)
    for tk, d in data.items():
        if tk.endswith(".NS") or tk == "^NSEI":
            tab[tk.removesuffix(".NS")] = (d["Open"] / d["Close"].shift(1) - 1) * 100
    for tk, name in (("^GSPC", "spx"), ("BZ=F", "brent")):
        c = data[tk]["Close"]
        # move from its last close before India's previous session to its last close before today
        prev_day = pd.Series(nifty.index, index=nifty.index).shift(1)
        last_before = lambda day: c[c.index < day].iloc[-1] if (c.index < day).any() else np.nan
        tab[name] = [(last_before(d) / last_before(p) - 1) * 100 if pd.notna(p) else np.nan
                     for d, p in zip(nifty.index, prev_day)]
    return tab.dropna(subset=["^NSEI", "spx", "brent"])


def fit(tab: pd.DataFrame, universe: list[str]) -> dict:
    """Nifty gap model (spx, brent) and, per stock, gap = a + beta * nifty_gap + crude * brent."""
    X = np.column_stack([np.ones(len(tab)), tab["spx"], tab["brent"]])
    coef, *_ = np.linalg.lstsq(X, tab["^NSEI"].values, rcond=None)
    out = {"nifty": {"const": coef[0], "spx": coef[1], "brent": coef[2]}, "stocks": {},
           "fitted_on": f"{tab.index[0].date()} - {tab.index[-1].date()}", "days": len(tab)}
    for s in universe:
        if s not in tab:
            continue
        d = tab[[s, "^NSEI", "brent"]].dropna()
        d = d[d[s].abs() < 15]  # splits / bonus days
        if len(d) < 100:
            continue
        X = np.column_stack([np.ones(len(d)), d["^NSEI"], d["brent"]])
        c, *_ = np.linalg.lstsq(X, d[s].values, rcond=None)
        resid = d[s].values - X @ c
        out["stocks"][s] = {"const": round(c[0], 4), "beta": round(c[1], 3), "crude": round(c[2], 4),
                            "resid_sd": round(float(resid.std()), 3)}
    return out


def predict_gap(sym: str, model: dict, spx: float, brent: float) -> float | None:
    st = model["stocks"].get(sym)
    if not st:
        return None
    n = model["nifty"]
    nifty_gap = n["const"] + n["spx"] * spx + n["brent"] * brent
    return st["const"] + st["beta"] * nifty_gap + st["crude"] * brent


def evaluate(universe: list[str]) -> str:
    """Fit on the first 18 months, test on the last 6: does the forecast beat 'no change'?"""
    tab = gap_table(universe, 2)
    cut = tab.index[int(len(tab) * 0.75)]
    model = fit(tab[tab.index < cut], universe)
    test = tab[tab.index >= cut]
    rows = []
    for s in model["stocks"]:
        for day, r in test.iterrows():
            if pd.isna(r.get(s)) or abs(r[s]) >= 15:
                continue
            p = predict_gap(s, model, r["spx"], r["brent"])
            rows.append({"sym": s, "pred": p, "actual": r[s], "brent": r["brent"]})
    df = pd.DataFrame(rows)
    big = df[df["pred"].abs() >= 0.5]
    oil = df[df["brent"].abs() >= 2]
    corr = df[["pred", "actual"]].corr().iloc[0, 1]
    lines = [f"Test {cut.date()} - {test.index[-1].date()}: {len(df)} stock-days",
             f"correlation forecast vs actual gap: {corr:.2f}",
             f"error vs 'no change': {np.mean(np.abs(df.actual - df.pred)):.2f}% vs {np.mean(np.abs(df.actual)):.2f}%",
             f"direction right when forecast >= 0.5%: {(np.sign(big.pred) == np.sign(big.actual)).mean() * 100:.0f}% "
             f"({len(big)} cases)",
             f"on big oil nights (Brent 2%+): direction right {(np.sign(oil.pred) == np.sign(oil.actual)).mean() * 100:.0f}% "
             f"({len(oil)} cases)"]
    sens = sorted(model["stocks"].items(), key=lambda kv: kv[1]["crude"])
    lines.append("most oil-hurt: " + ", ".join(f"{k} {v['crude']:+.3f}" for k, v in sens[:5]))
    lines.append("most oil-helped: " + ", ".join(f"{k} {v['crude']:+.3f}" for k, v in sens[-5:]))
    return "\n".join(lines)


def load_model() -> dict | None:
    return json.loads(BETAS.read_text()) if BETAS.exists() else None


def forecast(now: datetime, universe: list[str]) -> dict:
    """Today's expected gap per stock (before the open)."""
    from . import analyzer, mover_forecast, reaction
    model = load_model()
    if model is None:
        model = fit(gap_table(universe, 2), universe)
        BETAS.write_text(json.dumps(model, indent=1))
    mkt = reaction.expected_market_gap()
    spx, brent = mkt["spx_change_pct"], mkt["brent_change_pct"]
    items = analyzer.recent_items(now)
    reported = mover_forecast.results_since_last_close(now)
    stocks = {}
    for s in universe:
        g = predict_gap(s, model, spx, brent)
        if g is None:
            continue
        parts = [f"market {g:+.2f}%"]
        oil = model["stocks"][s]["crude"] * brent
        if abs(oil) >= 0.2:
            parts.append(f"oil {oil:+.2f}% (Brent {brent:+.1f}%)")
        if s in reported:
            parts.append("results since the last close (size: results model in the morning brief)")
        view = analyzer.stock_view(s, items, now)
        stocks[s] = {"expected_gap_pct": round(g, 2), "sd": model["stocks"][s]["resid_sd"],
                     "news": f"{view['direction']} {view['confidence']}%" if view["strong"] else "",
                     "results": s in reported, "why": "; ".join(parts)}
    return {"date": now.date().isoformat(), "expected_nifty_gap_pct": mkt["expected_nifty_gap_pct"],
            "spx_change_pct": spx, "brent_change_pct": brent, "stocks": stocks}


def label(expected: float, actual: float, sd: float = 1.0) -> str:
    """How the pre-open gap compares with the overnight forecast."""
    if abs(expected) < 0.3:
        return "as expected" if abs(actual) < max(0.5, sd) else ("opposite" if False else "news-driven gap")
    if actual * expected < 0 and abs(actual) >= 0.3:
        return "opposite"
    if abs(actual) >= abs(expected):
        return "priced in"
    if abs(actual) <= 0.5 * abs(expected):
        return "under-reacted"
    return "as expected"


def compare(fc: dict, pre: dict) -> dict:
    """Add the pre-open gap and its label to each stock of a forecast."""
    for s, f in fc["stocks"].items():
        g = (pre.get(s) or {}).get("gap_pct")
        if g is not None:
            f["preopen_gap_pct"] = g
            f["label"] = label(f["expected_gap_pct"], g, f.get("sd") or 1.0)
    return fc


def path(day: date) -> Path:
    return OUT / f"{day.isoformat()}.json"


def load(day: date) -> dict | None:
    p = path(day)
    return json.loads(p.read_text()) if p.exists() else None


def save(fc: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    path(date.fromisoformat(fc["date"])).write_text(json.dumps(fc, indent=1))


def stock_note(day: date, sym: str) -> dict:
    """{label, expected_gap_pct, preopen_gap_pct} for one stock today, {} if unknown."""
    fc = load(day) or {}
    return (fc.get("stocks") or {}).get(sym) or {}


def main(argv: list[str]) -> None:
    from .config import load_config
    universe = load_config()["universe"]
    if argv and argv[0] == "fit":
        BETAS.write_text(json.dumps(fit(gap_table(universe, 2), universe), indent=1))
        print("saved", BETAS)
        return
    if argv and argv[0] == "evaluate":
        print(evaluate(universe))
        return
    from zoneinfo import ZoneInfo
    from . import mover_forecast
    now = datetime.now(ZoneInfo("Asia/Kolkata")).replace(tzinfo=None)
    fc = compare(forecast(now, universe), mover_forecast.preopen_gaps(now))
    save(fc)
    print(f"Expected Nifty gap {fc['expected_nifty_gap_pct']:+.2f}% (S&P {fc['spx_change_pct']:+.2f}%, Brent {fc['brent_change_pct']:+.2f}%)")
    top = sorted(fc["stocks"].items(), key=lambda kv: -abs(kv[1]["expected_gap_pct"]))[:12]
    for s, f in top:
        pre = f" | pre-open {f['preopen_gap_pct']:+.2f}% -> {f['label']}" if "preopen_gap_pct" in f else ""
        print(f"{s:12} {f['expected_gap_pct']:+.2f}%  {f['why']}{(' | news ' + f['news']) if f['news'] else ''}{pre}")


if __name__ == "__main__":
    main(sys.argv[1:])
