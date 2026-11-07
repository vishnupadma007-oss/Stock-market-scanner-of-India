"""Spurt redesign tests (user, 7 Nov 2026): which extra confirmation makes the Quiet Volume Spurt profitable?
Same option model, charges, 15%-else-10% net target, no stop-loss, 15:20 square-off as backtest_spurt.py.
Each variant is a rule on the 5-minute bar (first matching bar of the day, 09:30-11:30), plus a control that trades the
SAME entries the opposite way. Usage: python backtest_spurt_v2.py --intraday i.pkl --daily d.pkl --out out.csv"""
import argparse
from datetime import time

import numpy as np
import pandas as pd

from agents import spurt
from agents.config import load_config
from agents.indicators import hist_vol, intraday_sigma_per_min
from agents.options import suggest_contract
from agents.risk import plan
from backtest_reversal import load, option_mid, run_trade

START, END = time(9, 30), time(11, 30)


def features(sym, intra, daily, nifty_intra, nifty_prev, base_days=10):
    df = spurt.prepare(intra, base_days)
    day = df["day"]
    df["dhi"] = df.groupby("day")["High"].cummax()
    df["dlo"] = df.groupby("day")["Low"].cummin()
    f30 = df[df["bar"] <= 5].groupby("day").agg(f_hi=("High", "max"), f_lo=("Low", "min"))
    df = df.join(f30, on="day")
    dd = daily.copy(); dd["pdh"] = dd["High"].shift(1); dd["pdl"] = dd["Low"].shift(1)
    dd.index = [d.date() for d in dd.index]
    df["pdh"] = day.map(dd["pdh"]); df["pdl"] = day.map(dd["pdl"])
    n = nifty_intra["Close"].reindex(df.index, method="ffill")
    df["nmove"] = (n / day.map(nifty_prev) - 1) * 100
    n6 = n - n.shift(6)
    df["n30"] = n6 / day.map(nifty_prev) * 100  # the Nifty's move over the last 30 minutes (%)
    df["gap"] = (day.map(intra.groupby(intra.index.date)["Open"].first()) / df["prev"] - 1) * 100
    df["bar_vol_x"] = df["Volume"] / df.groupby("bar")["Volume"].transform(lambda s: s.shift(1).rolling(10, min_periods=5).mean())
    return df


def candidates(df, day, rule):
    g = df[(df["day"] == day) & (df.index.time >= START) & (df.index.time <= END) & (df["bar"] >= 3)]
    for t, r in g.iterrows():
        if np.isnan(r["volume_x"]):
            continue
        d = 1 if r["move"] > 0 else -1
        if not rule(r, d):
            continue
        return t, d, r
    return None


def base(r, d, vx=1.5, lo=0.2, hi=0.5):
    if r["volume_x"] < vx or not lo <= abs(r["move"]) <= hi:
        return False
    return (d > 0) == bool(r["Close"] > r["Open"]) and (r["Close"] - r["vwap"]) * d > 0


def brk30(r, d):  # past the first-30-minute range (bar 6+ = after 09:45)
    return r["bar"] >= 6 and (r["Close"] > r["f_hi"] if d > 0 else r["Close"] < r["f_lo"])


def brkpd(r, d):  # past yesterday's high / low
    return (r["Close"] > r["pdh"]) if d > 0 else (r["Close"] < r["pdl"])


def near_dayextreme(r, d, tol=0.15):  # at the day's high (up) / low (down) so far
    return (r["Close"] >= r["dhi"] * (1 - tol / 100)) if d > 0 else (r["Close"] <= r["dlo"] * (1 + tol / 100))


VARIANTS = {
    "0 today's pure rule (1.5x, 0.2-0.5%)": lambda r, d: base(r, d),
    "1 + with the Nifty (same direction)": lambda r, d: base(r, d) and r["nmove"] * d > 0,
    "2 + against the Nifty": lambda r, d: base(r, d) and r["nmove"] * d < 0,
    "3 + stronger than the Nifty (rel. strength >= 0.2)": lambda r, d: base(r, d) and (r["move"] - r["nmove"]) * d >= 0.2,
    "4 + at the day's high/low (no pullback)": lambda r, d: base(r, d) and near_dayextreme(r, d),
    "5 + past the first-30-min range": lambda r, d: base(r, d) and brk30(r, d),
    "6 + past yesterday's high/low": lambda r, d: base(r, d) and brkpd(r, d),
    "7 move up to 1.0% + past first-30 range": lambda r, d: base(r, d, 1.5, 0.2, 1.0) and brk30(r, d),
    "8 ORB: 1.5x volume + first-30 break (any move<=1.5%)": lambda r, d: base(r, d, 1.5, 0.0, 1.5) and brk30(r, d),
    "9 ORB + with the Nifty": lambda r, d: base(r, d, 1.5, 0.0, 1.5) and brk30(r, d) and r["nmove"] * d > 0,
    "10 volume 2.5x + past first-30": lambda r, d: base(r, d, 2.5, 0.2, 0.8) and brk30(r, d),
    "11 volume 2.5x (no breakout)": lambda r, d: base(r, d, 2.5, 0.2, 0.8),
    "12 last-bar burst 3x + past first-30": lambda r, d: base(r, d, 1.2, 0.2, 1.0) and r["bar_vol_x"] >= 3 and brk30(r, d),
}


def run(frames, cfg, variants=VARIANTS):
    nifty = frames.pop("^NSEI")
    n_intra, n_daily = nifty
    nprev = n_intra.groupby(n_intra.index.date)["Close"].last().shift(1)
    half = cfg["assumed_spread_pct"] / 200
    cache, rows = {}, []
    for sym, (intra, daily) in frames.items():
        if len(daily) < 30:
            continue
        df = features(sym, intra, daily, n_intra, nprev)
        for name, rule in variants.items():
            for day in sorted(set(df["day"])):
                past = daily[daily.index.date < day]
                if len(past) < 25:
                    continue
                hit = candidates(df, day, rule)
                if hit is None:
                    continue
                t, d, r = hit
                for mode, dd in (("signal", d), ("opposite", -d)):
                    key = (sym, day, t, dd)
                    if key not in cache:
                        t5 = t + pd.Timedelta(minutes=5); hist = intra[intra.index <= t]
                        spot = float(hist["Close"].iloc[-1]); side = "loser" if dd > 0 else "gainer"; res = None
                        for tgt in (15.0, 10.0):
                            c = {**cfg, "net_target_pct": tgt}
                            o = suggest_contract(sym, spot, side, hist_vol(past["Close"]), None, c, day)
                            o["est_premium"] = round(option_mid(o, spot, t5, c) * (1 + half), 2)
                            pl = plan(o, 0, t5.to_pydatetime(), c, sigma_per_min=intraday_sigma_per_min(hist.tail(400)))
                            if pl["allowed"]:
                                res = run_trade(sym, side, o, pl, intra, t5, day, c, half); break
                        cache[key] = res
                    if cache[key]:
                        rows.append({**cache[key], "variant": name, "mode": mode, "day": day, "sym": sym, "t": t})
    return pd.DataFrame(rows)


def table(df, mode="signal"):
    days = sorted(set(df["day"])); cut = days[len(days) // 2]
    print(f"{'variant':54} {'n':>4} {'hit%':>5} {'avg%':>6} {'net Rs':>9} {'h1':>8} {'h2':>8}")
    for v, g in df[df["mode"] == mode].groupby("variant", sort=False):
        print(f"{v:54} {len(g):4} {(g.status=='TARGET').mean()*100:5.0f} {g.net_pct.mean():+6.2f} {g.net_pnl.sum():+9,.0f} "
              f"{g[g.day<cut].net_pnl.sum():+8,.0f} {g[g.day>=cut].net_pnl.sum():+8,.0f}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--intraday"); ap.add_argument("--daily"); ap.add_argument("--out")
    a = ap.parse_args(); cfg = load_config()
    df = run(load(a.intraday, a.daily, cfg["universe"]), cfg)
    if a.out:
        df.to_csv(a.out, index=False)
    table(df)
    print("\nCONTROL: the same entries the opposite way"); table(df, "opposite")
