"""Range trading at support / resistance (user, 14 Nov 2026): on calm market days only, in the most volatile F&O
stocks, buy a CALL when the price bounces off support and a PUT when it turns at resistance; 1% net target after all
charges, as many trades as come (after one closes, the next can open), no stop-loss, square-off 15:20.

Levels tested: previous day high/low; classic pivots S1/R1; the first-30-minute range. Calm day = Nifty within 0.5% of
yesterday's close at the entry time. Volatile stocks = the 25 with the largest 20-day average day range.
Entry: a 5-minute candle touches the level (within 0.15%) and closes back on the right side. Control: the same entries
the other way (a breakout bet). Yahoo 5-minute data (~60 days), ITM1 option, Rs 25k per trade.
Usage: python backtest_range_sr.py [--cache DIR]
"""
import argparse, os, warnings
import numpy as np, pandas as pd, yfinance as yf
from agents.config import load_config
from agents.costs import exit_for_net_target
from agents.indicators import hist_vol
from agents.options import suggest_contract
from backtest_reversal import IST, option_mid, run_trade
warnings.filterwarnings("ignore")
TOL, CALM, MAX_PER_DAY = 0.15, 0.5, 3


def load(cache, symbols):
    pi, pd_ = os.path.join(cache, "sr_intra.pkl"), os.path.join(cache, "sr_daily.pkl")
    if os.path.exists(pi):
        i, d = pd.read_pickle(pi), pd.read_pickle(pd_)
    else:
        t = [s + ".NS" for s in symbols] + ["^NSEI"]
        i = yf.download(t, period="60d", interval="5m", group_by="ticker", progress=False, auto_adjust=False)
        d = yf.download(t, period="1y", interval="1d", group_by="ticker", progress=False, auto_adjust=False)
        os.makedirs(cache, exist_ok=True); i.to_pickle(pi); d.to_pickle(pd_)
    i.index = i.index.tz_convert(IST)
    return {tk.removesuffix(".NS"): (i[tk].dropna(subset=["Close"]), d[tk].dropna(subset=["Close"]))
            for tk in i.columns.get_level_values(0).unique()}


def levels(kind, past, today_bars):
    p = past.iloc[-1]
    if kind == "prev day high/low":
        return p["Low"], p["High"]
    if kind == "pivot S1/R1":
        pv = (p["High"] + p["Low"] + p["Close"]) / 3
        return 2 * pv - p["High"], 2 * pv - p["Low"]
    f = today_bars.head(6)  # first 30 minutes
    return f["Low"].min(), f["High"].max()


def run(frames, cfg, kind, mode):
    n_i, n_d = frames["^NSEI"]
    half = cfg["assumed_spread_pct"] / 200
    out = []
    days = sorted(set(n_i.index.date))
    for day in days:
        n_prev = n_d[n_d.index.date < day]
        if n_prev.empty:
            continue
        n_close = float(n_prev["Close"].iloc[-1])
        # 25 most volatile stocks by 20-day average range
        vol = {}
        for s, (i, d) in frames.items():
            past = d[d.index.date < day]
            if s == "^NSEI" or len(past) < 25:
                continue
            vol[s] = ((past["High"] - past["Low"]) / past["Close"]).tail(20).mean()
        for s in sorted(vol, key=vol.get, reverse=True)[:25]:
            i, d = frames[s]
            past = d[d.index.date < day]
            bars = i[i.index.date == day]
            if len(bars) < 10:
                continue
            sup, res = levels(kind, past, bars)
            busy_until, count = None, 0
            for t, b in bars.iterrows():
                hm = t.strftime("%H:%M")
                if hm < "09:45" or hm > "14:30" or count >= MAX_PER_DAY or (busy_until is not None and t <= busy_until):
                    continue
                nb = n_i[n_i.index <= t]
                if nb.empty or abs(float(nb["Close"].iloc[-1]) / n_close - 1) * 100 >= CALM:
                    continue
                side = None
                if b["Low"] <= sup * (1 + TOL / 100) and b["Close"] > sup:
                    side = "loser"   # bounce off support -> CALL
                elif b["High"] >= res * (1 - TOL / 100) and b["Close"] < res:
                    side = "gainer"  # turn at resistance -> PUT
                if side is None:
                    continue
                if mode == "opposite":
                    side = "gainer" if side == "loser" else "loser"
                spot = float(b["Close"])
                c = {**cfg, "net_target_pct": 1.0}
                op = suggest_contract(s, spot, side, hist_vol(past["Close"]), None, c, day)
                t5 = t + pd.Timedelta(minutes=5)
                op["est_premium"] = round(option_mid(op, spot, t5, c) * (1 + half), 2)
                qty = max(int(25000 // op["est_premium"]), 1)
                risk = {"qty": qty, "hit_probability": 0,
                        "target_premium": exit_for_net_target(op["est_premium"], qty, 1.0, c["charges"])["exit_premium"]}
                tr = run_trade(s, side, op, risk, i, t5, day, c, half)
                out.append({**tr, "kind": kind, "mode": mode})
                count += 1
                busy_until = pd.Timestamp(f"{day} {tr['closed']}", tz=IST)
    return pd.DataFrame(out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--cache", default="."); a = ap.parse_args()
    cfg = load_config()
    frames = load(a.cache, cfg["universe"])
    print("| Levels | Bet | Trades | Hit 1% | Avg/trade | Worst | Net | Half 1 / Half 2 |\n|---|---|---|---|---|---|---|---|")
    for kind in ("prev day high/low", "pivot S1/R1", "first-30-min range"):
        for mode in ("range (fade the level)", "opposite"):
            df = run(frames, cfg, kind, mode)
            if df.empty:
                print(f"| {kind} | {mode} | 0 |"); continue
            days = sorted(df["date"].unique()); mid = days[len(days) // 2]
            h1, h2 = df[df.date < mid].net_pnl.sum(), df[df.date >= mid].net_pnl.sum()
            print(f"| {kind} | {mode} | {len(df)} | {(df.status == 'TARGET').mean() * 100:.0f}% | {df.net_pct.mean():+.2f}% | "
                  f"{df.net_pct.min():+.0f}% | Rs {df.net_pnl.sum():+,.0f} | {h1 / 1000:+.1f}k / {h2 / 1000:+.1f}k |")
