"""Walk-forward test of the Probability Analyzer (agents/probability.py) on the Quiet Volume Spurt:
every spurt trade of the ~60 days is replayed with the live rules (10% net target, no stop-loss,
15:20 square-off); before each one the analyzer judges it using only what was known then (its
base rate and learned score are fitted on earlier days' trades only). Compares the trades it
approves with the ones it rejects, and checks whether its Monte Carlo chance is honest.

Usage:  python backtest_probability.py --intraday intra.pkl --daily daily.pkl [--min-history 15]
"""
import argparse
from datetime import time

import numpy as np
import pandas as pd

from agents import probability as pa, spurt
from agents.config import load_config
from agents.indicators import hist_vol, intraday_sigma_per_min
from agents.options import suggest_contract
from agents.risk import plan
from backtest_reversal import IST, load, option_mid, run_trade


def replay(frames: dict, cfg: dict, sims: int) -> pd.DataFrame:
    frames.pop("^NSEI", None)
    half = cfg["assumed_spread_pct"] / 200
    sc = {**spurt.DEFAULTS, **(cfg.get("spurt") or {})}
    c = {**cfg, "net_target_pct": sc["target_net_pct"]}
    until = time.fromisoformat(cfg["entry_end"])
    rows = []
    for sym, (intra, daily) in frames.items():
        df = spurt.prepare(intra, sc["baseline_days"])
        for day in sorted(set(df["day"])):
            sig = spurt.first_signal(df, day, sc, until)
            past = daily[daily.index.date < day]
            if sig is None or len(past) < 25:
                continue
            t_close = sig["time"] + pd.Timedelta(minutes=5)
            hist = intra[intra.index <= sig["time"]]
            spot = float(hist["Close"].iloc[-1])
            side = "loser" if sig["direction"] == "up" else "gainer"
            option = suggest_contract(sym, spot, side, hist_vol(past["Close"]), None, c, day)
            option["est_premium"] = round(option_mid(option, spot, t_close, c) * (1 + half), 2)
            risk = plan(option, 0, t_close.to_pydatetime(), c, sigma_per_min=intraday_sigma_per_min(hist.tail(400)))
            if not risk["allowed"]:
                continue
            tr = run_trade(sym, side, option, risk, intra, t_close, day, c, half)
            rets = pa.recent_returns(intra, pd.Timestamp(day, tz=IST).to_pydatetime(), 20)
            sigma_ratio = pa.sigma_ratio(intra, sig["time"].to_pydatetime())
            square_off = pd.Timestamp(f"{day} {c['square_off_time']}", tz=IST).to_pydatetime()
            mc = pa.monte_carlo(option, spot, option["est_premium"], risk["target_premium"], risk["qty"],
                                t_close.to_pydatetime(), square_off, rets, c, n=sims, seed=1)
            rows.append({**tr, "move_pct": sig.get("move_pct"), "volume_x": sig.get("volume_x"),
                         "sigma_ratio": sigma_ratio,
                         "hit": tr["status"] == "TARGET",
                         **{f"mc_{k}": v for k, v in (mc or {}).items()}})
    return pd.DataFrame(rows).sort_values(["date", "opened"]).reset_index(drop=True)


def walk_forward(trades: pd.DataFrame, cfg: dict, min_history: int) -> pd.DataFrame:
    days = sorted(trades["date"].unique())
    out = []
    for k, day in enumerate(days):
        if k < min_history:
            continue
        past = trades[trades["date"] < day]
        recs = past.to_dict("records")
        model = pa.fit(past.assign(**pd.DataFrame([pa.features(r) for r in recs], index=past.index)))
        pa.set_cut(model, recs, cfg)
        for r in trades[trades["date"] == day].to_dict("records"):
            rep = pa.assess(r, pa._mc_of(r), model, cfg)
            out.append({**r, **{f"pa_{k2}": v for k2, v in rep.items()}})
    return pd.DataFrame(out)


def summary(name: str, g: pd.DataFrame) -> str:
    if g.empty:
        return f"{name:28} {0:5}"
    return (f"{name:28} {len(g):5} {g['hit'].mean() * 100:5.0f}% {g['net_pct'].mean():+7.2f}% "
            f"{g['net_pct'].min():+7.1f}% {g['net_pnl'].sum():+11,.0f}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--intraday", required=True)
    ap.add_argument("--daily", required=True)
    ap.add_argument("--min-history", type=int, default=15, help="days of trades before the first judgement")
    ap.add_argument("--sims", type=int, default=2000)
    ap.add_argument("--out", default="journal/backtest_probability.csv")
    ap.add_argument("--save-model", action="store_true", help="fit on all trades and save journal/probability_model.json")
    args = ap.parse_args()
    cfg = load_config()
    pcfg = {**pa.DEFAULTS, **(cfg.get("probability") or {})}
    trades = replay(load(args.intraday, args.daily, cfg["universe"]), cfg, args.sims)
    wf = walk_forward(trades, pcfg, args.min_history)
    wf.to_csv(args.out, index=False)
    print(f"All spurt trades: {len(trades)}; judged out-of-sample (after {args.min_history} days): {len(wf)}")
    print(f"Monte Carlo honesty: average chance {trades['mc_prob'].mean():.0%} vs actual hit {trades['hit'].mean():.0%}")
    for col in ("mc_prob", "pa_historical_win_rate", "pa_ml_confidence_score", "pa_blended_prob", "pa_expected_value_pct"):
        if col in wf and wf[col].notna().any():
            q = pd.qcut(wf[col].rank(method="first"), 3, labels=["low", "mid", "high"])
            parts = ", ".join(f"{lab}: {g['hit'].mean():.0%} hit {g['net_pct'].mean():+.1f}%" for lab, g in wf.groupby(q, observed=True))
            print(f"  by {col:26} {parts}")
    print(f"{'':28} {'trades':>5} {'hit':>6} {'avg':>8} {'worst':>8} {'net Rs':>11}")
    print(summary("all (out-of-sample)", wf))
    print(summary("approved", wf[wf["pa_approved"]]))
    print(summary("rejected", wf[~wf["pa_approved"]]))
    if args.save_model:
        recs = trades.to_dict("records")
        model = pa.fit(trades.assign(**pd.DataFrame([pa.features(r) for r in recs], index=trades.index)))
        pa.save_model(pa.set_cut(model, recs, pcfg))
        print(f"Saved {pa.MODEL} ({model['n']} trades, cut {model['cut']:.0%})")


if __name__ == "__main__":
    main()
