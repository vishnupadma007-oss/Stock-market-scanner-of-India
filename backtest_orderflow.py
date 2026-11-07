"""Backtest of the order-flow / early-movement detectors (agents/orderflow.py) on ~60 days of
5-minute data, with the same option simulation, charges and exits as backtest_reversal.py:
buy the ITM1 option at the signal candle's close, sell at the 1% net target or square-off.
No stop-loss.

Each detector's first signal per stock per day is traded. As a control, the same entries are
also traded in the OPPOSITE direction: a signal with real information should clearly beat its
mirror image (both pay the same costs and time decay).

Usage:  python backtest_orderflow.py [--intraday intra.pkl --daily daily.pkl] [--out trades.csv]
"""
import argparse
from datetime import time

import pandas as pd

from agents import orderflow
from agents.config import load_config
from agents.indicators import hist_vol, intraday_sigma_per_min
from agents.options import suggest_contract
from agents.risk import plan
from backtest_reversal import load, option_mid, run_trade


def simulate(frames: dict, cfg: dict) -> pd.DataFrame:
    frames.pop("^NSEI", None)
    half_spread = cfg["assumed_spread_pct"] / 200
    start, end = time.fromisoformat(cfg["entry_start"]), time.fromisoformat(cfg["entry_end"])
    trades = []
    for sym, (intra, daily) in frames.items():
        f = orderflow.features(intra)
        sig = orderflow.signals(f)
        for det in orderflow.DETECTORS:
            hits = sig[det][sig[det] != 0]
            hits = hits[(hits.index.time >= start) & (hits.index.time <= end) & (f.loc[hits.index, "bar"] >= 2)]
            for day, first in hits.groupby(hits.index.date):
                t, direction = first.index[0], int(first.iloc[0])
                # The signal candle is labelled by its start; it closes 5 minutes later.
                t_close = t + pd.Timedelta(minutes=5)
                past = daily[daily.index.date < day]
                hist = intra[intra.index <= t]
                if len(past) < 25:
                    continue
                spot = float(hist["Close"].iloc[-1])
                for mode, d in (("signal", direction), ("opposite", -direction)):
                    side = "loser" if d > 0 else "gainer"  # loser -> CALL, gainer -> PUT
                    option = suggest_contract(sym, spot, side, hist_vol(past["Close"]), None, cfg, day)
                    option["est_premium"] = round(option_mid(option, spot, t_close, cfg) * (1 + half_spread), 2)
                    risk = plan(option, 0, t_close.to_pydatetime(), cfg,
                                sigma_per_min=intraday_sigma_per_min(hist.tail(400)))
                    if not risk["allowed"]:
                        continue
                    tr = run_trade(sym, side, option, risk, intra, t_close, day, cfg, half_spread)
                    trades.append({**tr, "detector": det, "mode": mode, "direction": "CALL" if d > 0 else "PUT"})
    return pd.DataFrame(trades)


def report(trades: pd.DataFrame) -> str:
    if trades.empty:
        return "No trades."
    lines = ["detector  mode      trades  hit%   avg%    worst%   net Rs"]
    for (det, mode), g in trades.groupby(["detector", "mode"]):
        hit = (g["status"] == "TARGET").mean() * 100
        lines.append(f"{det:9} {mode:9} {len(g):6} {hit:5.0f} {g['net_pct'].mean():+7.2f} {g['net_pct'].min():+8.1f} "
                     f"{g['net_pnl'].sum():+10,.0f}")
    for (det, d), g in trades[trades["mode"] == "signal"].groupby(["detector", "direction"]):
        lines.append(f"  {det} {d}: {len(g)} trades, {(g['status'] == 'TARGET').mean() * 100:.0f}% hit, "
                     f"avg {g['net_pct'].mean():+.2f}%")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--intraday")
    ap.add_argument("--daily")
    ap.add_argument("--out", default="journal/backtest_orderflow.csv")
    args = ap.parse_args()
    cfg = load_config()
    trades = simulate(load(args.intraday, args.daily, cfg["universe"]), cfg)
    trades.to_csv(args.out, index=False)
    print(report(trades))


if __name__ == "__main__":
    main()
