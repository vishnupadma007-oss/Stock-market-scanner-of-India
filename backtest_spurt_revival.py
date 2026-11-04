"""Backtest of the user's revived pure spurt rules (4 Nov 2026), stage by stage, on 60 days of 5-minute data.
Testable on history: volume floor, entry window, pre-open calm (proxy: opening bar vs yesterday's close),
multi-week structure (spurt.check_multiweek_context). NOT testable (no history): zero-news quarantine,
F&O open-interest confirmation, option delta/spread limits.
Usage: python backtest_spurt_revival.py --intraday intra.pkl --daily daily.pkl --out out.csv"""
import argparse
from datetime import time

import pandas as pd

from agents import spurt
from agents.config import load_config
from agents.indicators import hist_vol, intraday_sigma_per_min
from agents.options import suggest_contract
from agents.risk import plan
from backtest_reversal import load, option_mid, run_trade

STAGES = {  # name: (min volume x, entry until, pre-open calm max gap %, multi-week filter)
    "0 today's rule (1.5x, to 15:15)": (1.5, None, None, False),
    "1 + volume 1.8x": (1.8, None, None, False),
    "2 + window 09:30-11:30": (1.8, "11:30", None, False),
    "3 + pre-open calm (gap <= 1%)": (1.8, "11:30", 1.0, False),
    "4 + multi-week filter = REVIVED": (1.8, "11:30", 1.0, True),
    "5 multi-week filter only (1.5x, all day)": (1.5, None, None, True),
    "6 window + calm only (1.5x)": (1.5, "11:30", 1.0, False),
}


def run(frames, cfg):
    frames.pop("^NSEI", None)
    half = cfg["assumed_spread_pct"] / 200
    sc0 = {**spurt.DEFAULTS, **(cfg.get("spurt") or {})}
    end_all = time.fromisoformat(cfg["entry_end"])
    cache, rows = {}, []
    for sym, (intra, daily) in frames.items():
        df = spurt.prepare(intra, sc0["baseline_days"])
        day_open = intra.groupby(intra.index.date)["Open"].first()
        prev_close = intra.groupby(intra.index.date)["Close"].last().shift(1)
        for stage, (vx, until, gap_max, mw) in STAGES.items():
            sc = {**sc0, "min_volume_x": vx}
            until_t = time.fromisoformat(until) if until else end_all
            for day in sorted(set(df["day"])):
                sig = spurt.first_signal(df, day, sc, until_t)
                past = daily[daily.index.date < day]
                if sig is None or len(past) < 25:
                    continue
                if gap_max is not None and day in prev_close.index and prev_close[day] == prev_close[day]:
                    if abs((day_open[day] / prev_close[day] - 1) * 100) > gap_max:
                        continue
                if mw and not spurt.check_multiweek_context(daily, sig["direction"], day)[0]:
                    continue
                key = (sym, day, sig["time"])
                if key not in cache:
                    t5 = sig["time"] + pd.Timedelta(minutes=5)
                    hist = intra[intra.index <= sig["time"]]
                    spot = float(hist["Close"].iloc[-1]); d = 1 if sig["direction"] == "up" else -1
                    side = "loser" if d > 0 else "gainer"; res = None
                    for tgt in (15.0, 10.0):
                        c = {**cfg, "net_target_pct": tgt}
                        o = suggest_contract(sym, spot, side, hist_vol(past["Close"]), None, c, day)
                        o["est_premium"] = round(option_mid(o, spot, t5, c) * (1 + half), 2)
                        r = plan(o, 0, t5.to_pydatetime(), c, sigma_per_min=intraday_sigma_per_min(hist.tail(400)))
                        if r["allowed"]:
                            res = run_trade(sym, side, o, r, intra, t5, day, c, half); break
                    cache[key] = res
                if cache[key]:
                    rows.append({**cache[key], "stage": stage, "day": day, "volume_x": sig["volume_x"]})
    return pd.DataFrame(rows)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--intraday"); ap.add_argument("--daily")
    ap.add_argument("--out", default="journal/backtest_spurt_revival.csv"); a = ap.parse_args()
    cfg = load_config(); df = run(load(a.intraday, a.daily, cfg["universe"]), cfg); df.to_csv(a.out, index=False)
    mid = pd.to_datetime(df["day"]).sort_values().iloc[len(df) // 2 if False else 0]
    days = sorted(set(df["day"])); cut = days[len(days) // 2]
    print("stage                                      trades  hit%   avg%    net Rs   half1    half2")
    for st, g in df.groupby("stage"):
        print(f"{st:42} {len(g):5} {(g.status=='TARGET').mean()*100:5.0f} {g.net_pct.mean():+6.2f} {g.net_pnl.sum():+9,.0f} "
              f"{g[g.day<cut].net_pnl.sum():+8,.0f} {g[g.day>=cut].net_pnl.sum():+8,.0f}")
