"""Backtest of the Quiet Volume Spurt (agents/spurt.py, the user's strategy of 28 Oct 2026) on ~60 days
of 5-minute data, with the same option model, charges and exits as the other backtests (ITM1, no
stop-loss, square-off 15:20), at several net targets; the same entries in the opposite direction
as a control.

Usage:  python backtest_spurt.py [--intraday intra.pkl --daily daily.pkl] [--targets 1 10 20]
"""
import argparse
from datetime import time

import pandas as pd

from agents import spurt
from agents.config import load_config
from agents.indicators import hist_vol, intraday_sigma_per_min
from agents.options import suggest_contract
from agents.risk import plan
from backtest_reversal import load, option_mid, run_trade


def simulate(frames: dict, cfg: dict, targets: list[float]) -> pd.DataFrame:
    frames.pop("^NSEI", None)
    half_spread = cfg["assumed_spread_pct"] / 200
    sc = {**spurt.DEFAULTS, **(cfg.get("spurt") or {})}
    until = time.fromisoformat(cfg["entry_end"])
    rows = []
    for sym, (intra, daily) in frames.items():
        df = spurt.prepare(intra, sc["baseline_days"])
        for day in sorted(set(df["day"])):
            sig = spurt.first_signal(df, day, sc, until)
            past = daily[daily.index.date < day]
            if sig is None or len(past) < 25:
                continue
            t = sig["time"]
            t_close = t + pd.Timedelta(minutes=5)
            hist = intra[intra.index <= t]
            spot = float(hist["Close"].iloc[-1])
            d = 1 if sig["direction"] == "up" else -1
            for tgt in targets:
                c = {**cfg, "net_target_pct": tgt}
                for mode, dd in (("signal", d), ("opposite", -d)):
                    side = "loser" if dd > 0 else "gainer"
                    option = suggest_contract(sym, spot, side, hist_vol(past["Close"]), None, c, day)
                    option["est_premium"] = round(option_mid(option, spot, t_close, c) * (1 + half_spread), 2)
                    risk = plan(option, 0, t_close.to_pydatetime(), c,
                                sigma_per_min=intraday_sigma_per_min(hist.tail(400)))
                    if risk["allowed"]:
                        tr = run_trade(sym, side, option, risk, intra, t_close, day, c, half_spread)
                        rows.append({**tr, "target": tgt, "mode": mode})
    return pd.DataFrame(rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--intraday")
    ap.add_argument("--daily")
    ap.add_argument("--targets", nargs="+", type=float, default=[1.0, 10.0])
    ap.add_argument("--out", default="journal/backtest_spurt.csv")
    args = ap.parse_args()
    cfg = load_config()
    df = simulate(load(args.intraday, args.daily, cfg["universe"]), cfg, args.targets)
    df.to_csv(args.out, index=False)
    print("target  mode      trades  hit%   avg%   worst%    net Rs")
    for (tgt, m), g in df.groupby(["target", "mode"]):
        print(f"{tgt:5.0f}%  {m:9} {len(g):6} {(g['status'] == 'TARGET').mean() * 100:5.0f} "
              f"{g['net_pct'].mean():+6.2f} {g['net_pct'].min():+7.1f} {g['net_pnl'].sum():+10,.0f}")


if __name__ == "__main__":
    main()
