"""Does a technical-strength filter improve the Quiet Volume Spurt? (user, 4 Nov 2026)
Replays every first spurt signal (same option model, charges, 15%-else-10% target, no stop-loss, 15:20
square-off as backtest_spurt.py) and records chart features at the signal, then slices the result.
Usage: python backtest_spurt_filters.py --intraday intra.pkl --daily daily.pkl --out journal/backtest_spurt_filters.csv"""
import argparse
from datetime import time

import pandas as pd

from agents import spurt
from agents.config import load_config
from agents.indicators import ema, hist_vol, intraday_sigma_per_min, rsi
from agents.options import suggest_contract
from agents.risk import plan
from backtest_reversal import load, option_mid, run_trade


def simulate(frames, cfg):
    frames.pop("^NSEI", None)
    half = cfg["assumed_spread_pct"] / 200
    sc = {**spurt.DEFAULTS, **(cfg.get("spurt") or {})}
    until = time.fromisoformat(cfg["entry_end"])
    rows = []
    for sym, (intra, daily) in frames.items():
        df = spurt.prepare(intra, sc["baseline_days"])
        d_rsi, d_e20, d_e50 = rsi(daily["Close"]), ema(daily["Close"], 20), ema(daily["Close"], 50)
        for day in sorted(set(df["day"])):
            sig = spurt.first_signal(df, day, sc, until)
            past = daily[daily.index.date < day]
            if sig is None or len(past) < 55:
                continue
            t = sig["time"]; t5 = t + pd.Timedelta(minutes=5)
            hist = intra[intra.index <= t]
            spot = float(hist["Close"].iloc[-1]); d = 1 if sig["direction"] == "up" else -1
            pc = past["Close"]
            feat = dict(
                rsi5=float(rsi(hist["Close"].tail(60)).iloc[-1]),
                rsi_d=float(d_rsi[d_rsi.index.date < day].iloc[-1]),
                vs_e20=(pc.iloc[-1] / float(d_e20[d_e20.index.date < day].iloc[-1]) - 1) * 100,
                vs_e50=(pc.iloc[-1] / float(d_e50[d_e50.index.date < day].iloc[-1]) - 1) * 100,
                prev_day=(pc.iloc[-1] / pc.iloc[-2] - 1) * 100,
                run5=(pc.iloc[-1] / pc.iloc[-6] - 1) * 100,
                hi20=float(past["High"].tail(20).max()), lo20=float(past["Low"].tail(20).min()))
            feat["breakout"] = (spot > feat["hi20"]) if d > 0 else (spot < feat["lo20"])
            feat["near_extreme"] = ((feat["hi20"] / spot - 1) * 100) if d > 0 else ((spot / feat["lo20"] - 1) * 100)
            side = "loser" if d > 0 else "gainer"
            res = {}
            for tgt in (15.0, 10.0):
                c = {**cfg, "net_target_pct": tgt}
                option = suggest_contract(sym, spot, side, hist_vol(past["Close"]), None, c, day)
                option["est_premium"] = round(option_mid(option, spot, t5, c) * (1 + half), 2)
                risk = plan(option, 0, t5.to_pydatetime(), c, sigma_per_min=intraday_sigma_per_min(hist.tail(400)))
                if risk["allowed"]:
                    res = run_trade(sym, side, option, risk, intra, t5, day, c, half); res["tgt"] = tgt
                    break
            if res:
                rows.append({**res, **feat, "day": day, "dir": d, "volume_x": sig["volume_x"],
                             "move_pct": sig["move_pct"], "hour": t.hour + t.minute / 60})
    return pd.DataFrame(rows)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--intraday"); ap.add_argument("--daily"); ap.add_argument("--out", default="journal/backtest_spurt_filters.csv")
    a = ap.parse_args(); cfg = load_config()
    simulate(load(a.intraday, a.daily, cfg["universe"]), cfg).to_csv(a.out, index=False)
