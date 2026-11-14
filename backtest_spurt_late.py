"""Spurt team after 11:30 (user, 14 Nov 2026): trade a spurt after the 09:30-11:30 window only when the volume is
much bigger than the morning rule asks (2x / 3x / 4x)? Same option model, 15%-else-10% net target, no stop-loss,
15:20 square-off as backtest_spurt_v2.py. Rule = today's spurt engine: volume vs usual at this time of day, move
0.2-0.5% from yesterday's close, candle and VWAP its way, WITH the Nifty (Nifty 0.15%+ the same way), gap <= 1%.
"Burst" = the 5-minute bar itself is Nx its usual volume (cumulative volume 1.8x+).
Usage: python backtest_spurt_late.py [--intraday i.pkl --daily d.pkl]"""
import argparse
from datetime import time

import numpy as np
import pandas as pd

from agents.config import load_config
from agents.indicators import hist_vol, intraday_sigma_per_min
from agents.options import suggest_contract
from agents.risk import plan
from backtest_reversal import load, option_mid, run_trade
from backtest_spurt_v2 import base, features


def ok(r, d, vx, burst=None):
    if not base(r, d, vx, 0.2, 0.5) or r["nmove"] * d < 0.15 or abs(r["gap"]) > 1.0:
        return False
    return burst is None or (r["bar_vol_x"] == r["bar_vol_x"] and r["bar_vol_x"] >= burst)


VARIANTS = {  # name: (start, end, cumulative volume x, bar burst x)
    "A morning 09:30-11:30, 1.8x (today's rule)": (time(9, 30), time(11, 30), 1.8, None),
    "B 11:35-14:00, 1.8x": (time(11, 35), time(14, 0), 1.8, None),
    "C 11:35-14:00, 2x": (time(11, 35), time(14, 0), 2.0, None),
    "D 11:35-14:00, 3x": (time(11, 35), time(14, 0), 3.0, None),
    "E 11:35-14:00, 4x": (time(11, 35), time(14, 0), 4.0, None),
    "F 11:35-14:00, bar burst 2x": (time(11, 35), time(14, 0), 1.8, 2.0),
    "G 11:35-14:00, bar burst 3x": (time(11, 35), time(14, 0), 1.8, 3.0),
    "H 11:35-14:00, bar burst 4x": (time(11, 35), time(14, 0), 1.8, 4.0),
    "I 11:35-13:00, 3x": (time(11, 35), time(13, 0), 3.0, None),
    "J 13:00-14:30, 3x": (time(13, 0), time(14, 30), 3.0, None),
}


def run(frames, cfg):
    n_intra, _ = frames.pop("^NSEI")
    nprev = n_intra.groupby(n_intra.index.date)["Close"].last().shift(1)
    half = cfg["assumed_spread_pct"] / 200
    rows = []
    for sym, (intra, daily) in frames.items():
        if len(daily) < 30:
            continue
        df = features(sym, intra, daily, n_intra, nprev)
        for day in sorted(set(df["day"])):
            past = daily[daily.index.date < day]
            if len(past) < 25:
                continue
            g = df[(df["day"] == day) & (df["bar"] >= 3)]
            morning = None
            for name, (s, e, vx, burst) in VARIANTS.items():
                hit = None
                for t, r in g[(g.index.time >= s) & (g.index.time <= e)].iterrows():
                    if np.isnan(r["volume_x"]):
                        continue
                    d = 1 if r["move"] > 0 else -1
                    if ok(r, d, vx, burst):
                        hit = (t, d); break
                if name.startswith("A"):
                    morning = hit
                if hit is None:
                    continue
                t, d = hit
                t5 = t + pd.Timedelta(minutes=5); hist = intra[intra.index <= t]
                spot = float(hist["Close"].iloc[-1]); side = "loser" if d > 0 else "gainer"; res = None
                for tgt in (15.0, 10.0):
                    c = {**cfg, "net_target_pct": tgt, "entry_end": "14:35"}
                    o = suggest_contract(sym, spot, side, hist_vol(past["Close"]), None, c, day)
                    o["est_premium"] = round(option_mid(o, spot, t5, c) * (1 + half), 2)
                    pl = plan(o, 0, t5.to_pydatetime(), c, sigma_per_min=intraday_sigma_per_min(hist.tail(400)))
                    if pl["allowed"]:
                        res = run_trade(sym, side, o, pl, intra, t5, day, c, half); break
                if res:
                    rows.append({**res, "variant": name, "day": day, "sym": sym,
                                 "had_morning_trade": morning is not None and not name.startswith("A")})
    return pd.DataFrame(rows)


def table(df):
    days = sorted(set(df["day"])); cut = days[len(days) // 2]
    print(f"{'variant':44} {'n':>4} {'hit%':>5} {'avg%':>6} {'net Rs':>9} {'half1':>8} {'half2':>8}")
    for v, g in df.groupby("variant", sort=True):
        print(f"{v:44} {len(g):4} {(g.status == 'TARGET').mean() * 100:5.0f} {g.net_pct.mean():+6.2f} {g.net_pnl.sum():+9,.0f} "
              f"{g[g.day < cut].net_pnl.sum():+8,.0f} {g[g.day >= cut].net_pnl.sum():+8,.0f}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--intraday"); ap.add_argument("--daily"); ap.add_argument("--out")
    a = ap.parse_args(); cfg = load_config()
    df = run(load(a.intraday, a.daily, cfg["universe"]), cfg)
    if a.out:
        df.to_csv(a.out, index=False)
    print(f"{df['day'].nunique()} days {min(df['day'])} - {max(df['day'])}\n")
    table(df)
    print("\nLate trades on stocks with NO morning spurt trade that day (new trades only):")
    table(df[~df["had_morning_trade"] & ~df["variant"].str.startswith("A")])
