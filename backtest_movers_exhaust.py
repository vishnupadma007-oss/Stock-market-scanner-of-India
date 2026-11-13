"""Movers team: does the "exhaustion reversal" proposal (user, 13 Nov 2026) add money?

The proposal: a 2.0-3.8% mover (gap <= 1.5%, day range <= 4.5%), 1%+ stretched from VWAP, a volume
spike (2.5x the 20-bar average) on a candle that makes a new day extreme and closes back inside
(top/bottom 40% of its range), entry when the next candles break that candle's high/low; 0.5% scalp
exits (0.5% spot, +5% premium or VWAP touch; -3.5% stop; 15-minute time exit).

Tested on Yahoo 5-minute data (~60 days; 1-minute data only goes back 8 days). Order flow, top-2
depth and minute-by-minute futures OI have no history and are not tested.

Base = today's movers playbook entry: a top-5 mover (2%+) that turned 0.5% off its day extreme,
09:30-14:00. Exits = the desk's: 15% target when the stock had run 4%+ the same way over the last
5 sessions (stretched), else 1% net; no stop-loss; square-off 15:20. Each variant adds the
proposal's filters to these entries with the desk's exits; the last rows use the proposal's own exits.
One trade per stock per day, Rs 25,000 per trade (Rs 1 lakh / 4 slots), ITM1 monthly option,
Black-Scholes premium + the configured spread, all charges.

Usage: python backtest_movers_exhaust.py [--cache DIR]
"""
import argparse
import os

import numpy as np
import pandas as pd
import yfinance as yf

from agents.config import load_config
from agents.costs import exit_for_net_target, round_trip_charges
from agents.indicators import hist_vol
from agents.options import suggest_contract
from backtest_reversal import option_mid, IST

BUDGET = 25000


def load(symbols, cache):
    pi, pd_ = os.path.join(cache, "intra.pkl"), os.path.join(cache, "daily.pkl")
    if cache and os.path.exists(pi):
        intra, daily = pd.read_pickle(pi), pd.read_pickle(pd_)
    else:
        tickers = [s + ".NS" for s in symbols]
        intra = yf.download(tickers, period="60d", interval="5m", group_by="ticker", progress=False, auto_adjust=False)
        daily = yf.download(tickers, period="1y", interval="1d", group_by="ticker", progress=False, auto_adjust=False)
        if cache:
            os.makedirs(cache, exist_ok=True)
            intra.to_pickle(pi)
            daily.to_pickle(pd_)
    intra.index = intra.index.tz_convert(IST)
    out = {}
    for tk in intra.columns.get_level_values(0).unique():
        i, d = intra[tk].dropna(subset=["Close"]), daily[tk].dropna(subset=["Close"])
        if len(i) and len(d) > 25:
            out[tk.removesuffix(".NS")] = (i, d)
    return out


def day_frame(i, d, day):
    """Today's bars with the columns the rules need, or None."""
    today = i[i.index.date == day].copy()
    past = d[d.index.date < day]
    if len(today) < 10 or len(past) < 25:
        return None
    prev = float(past["Close"].iloc[-1])
    turnover = float((past["Close"] * past["Volume"]).tail(20).mean()) / 1e7
    tp = (today["High"] + today["Low"] + today["Close"]) / 3
    today["vwap"] = (tp * today["Volume"]).cumsum() / today["Volume"].cumsum().replace(0, np.nan)
    today["chg"] = (today["Close"] / prev - 1) * 100
    today["dayhi"] = today["High"].cummax()
    today["daylo"] = today["Low"].cummin()
    # 20-bar volume average over the last 20 bars (yesterday's included), excluding the current bar
    allv = i["Volume"][i.index <= today.index[-1]]
    today["vavg"] = allv.shift(1).rolling(20).mean().reindex(today.index)
    return {"bars": today, "prev": prev, "turnover": turnover, "gap": (float(today["Open"].iloc[0]) / prev - 1) * 100,
            "week": (prev / float(past["Close"].iloc[-6]) - 1) * 100, "past": past}


def candidates(frames, cfg):
    """Every (stock, day, bar) where the stock is a top-5 mover, with all the rule flags."""
    days = sorted({t.date() for i, _ in frames.values() for t in i.index[-3000:]})
    rows = []
    for day in days:
        df = {s: day_frame(i, d, day) for s, (i, d) in frames.items()}
        df = {s: f for s, f in df.items() if f and f["turnover"] >= cfg["min_turnover_cr"]}
        if not df:
            continue
        chg = pd.DataFrame({s: f["bars"]["chg"] for s, f in df.items()})
        for t in chg.index:
            if not ("09:30" <= t.strftime("%H:%M") <= "14:45"):
                continue
            c = chg.loc[t].dropna()
            for side, pick in (("gainer", c[c >= cfg["min_move_pct"]].nlargest(5)),
                               ("loser", c[c <= -cfg["min_move_pct"]].nsmallest(5))):
                for s in pick.index:
                    f = df[s]
                    b = f["bars"]
                    k = b.index.get_loc(t)
                    bar = b.iloc[k]
                    d = -1 if side == "gainer" else 1  # direction we trade
                    ext = bar["dayhi"] if side == "gainer" else bar["daylo"]
                    turned = (bar["Close"] - ext) * d / ext * 100 >= 0.5
                    move = abs(bar["chg"])
                    rng = max(abs(bar["dayhi"] / f["prev"] - 1), abs(bar["daylo"] / f["prev"] - 1)) * 100
                    vw = (bar["Close"] - bar["vwap"]) / bar["vwap"] * 100 * -d  # + = stretched against us, room to revert
                    prev_ext = b["dayhi"].iloc[k - 1] if side == "gainer" else b["daylo"].iloc[k - 1]
                    new_ext = (bar["High"] > prev_ext) if side == "gainer" else (bar["Low"] < prev_ext)
                    span = bar["High"] - bar["Low"]
                    pos = (bar["Close"] - bar["Low"]) / span if span > 0 else 0.5
                    wick = pos >= 0.6 if side == "loser" else pos <= 0.4
                    spike = bar["vavg"] > 0 and bar["Volume"] >= 2.5 * bar["vavg"]
                    rows.append({"day": day, "t": t, "sym": s, "side": side, "close": bar["Close"],
                                 "hi": bar["High"], "lo": bar["Low"], "turned": turned,
                                 "window": 2.0 <= move <= 3.8, "nogap": abs(f["gap"]) <= 1.5 and rng <= 4.5,
                                 "vwap1": vw >= 1.0, "exhaust": bool(new_ext and wick and spike),
                                 "stretched": f["week"] * -d >= 4.0, "early": t.strftime("%H:%M") <= "14:00",
                                 "prop_time": "10:00" <= t.strftime("%H:%M") <= "14:45"})
    return pd.DataFrame(rows), frames


def trade(frames, cfg, sym, side, day, t, spot, entry_t, mode, stretched):
    i, d = frames[sym]
    past = d[d.index.date < day]
    opt = suggest_contract(sym, spot, side, hist_vol(past["Close"]), None, cfg, day)
    hs = cfg["assumed_spread_pct"] / 200
    entry = option_mid(opt, spot, entry_t, cfg) * (1 + hs)
    qty = max(int(BUDGET // entry), 1)
    sq = pd.Timestamp(f"{day} 15:20", tz=IST)
    after = i[(i.index > entry_t) & (i.index <= sq)]
    today = i[i.index.date == day]
    tp = (today["High"] + today["Low"] + today["Close"]) / 3
    vwap = (tp * today["Volume"]).cumsum() / today["Volume"].cumsum()
    d_ = 1 if side == "loser" else -1
    if mode == "desk":
        target = entry * 1.15 if stretched else exit_for_net_target(entry, qty, 1.0, cfg["charges"])["exit_premium"]
    else:  # proposal: +5% premium or 0.5% spot or VWAP; -3.5% stop or 2 ticks past the day extreme; 15 min
        target = entry * 1.05
        spot_tgt = spot * (1 + 0.005 * d_)
        stop = entry * 0.965
        sofar = today[today.index <= entry_t]
        ext = float(sofar["Low"].min()) if d_ > 0 else float(sofar["High"].max())
        sq = min(sq, entry_t + pd.Timedelta(minutes=15))
        after = after[after.index <= sq]
    exit_p, status = None, "SQUARED_OFF"
    for ts, bar in after.iterrows():
        best = bar["High"] if d_ > 0 else bar["Low"]
        worst = bar["Low"] if d_ > 0 else bar["High"]
        if mode != "desk":
            if (worst - ext) * d_ < -0.1 or option_mid(opt, worst, ts, cfg) * (1 - hs) <= stop:
                exit_p, status = min(stop, option_mid(opt, worst, ts, cfg) * (1 - hs)), "STOP"
                break
            lvl = float(vwap.get(ts, np.nan))
            hit_spot = (best - spot_tgt) * d_ >= 0 or (lvl == lvl and (best - lvl) * d_ >= 0)
            if hit_spot:
                lvl_s = spot_tgt if (best - spot_tgt) * d_ >= 0 else lvl
                exit_p, status = max(option_mid(opt, lvl_s, ts, cfg) * (1 - hs), 0), "TARGET"
                break
        if option_mid(opt, best, ts, cfg) * (1 - hs) >= target:
            exit_p, status = target, "TARGET"
            break
    if exit_p is None:
        last = float(after["Close"].iloc[-1]) if len(after) else spot
        exit_p = option_mid(opt, last, sq, cfg) * (1 - hs)
    net = (exit_p - entry) * qty - round_trip_charges(entry, exit_p, qty, cfg["charges"])["total"]
    return {"day": day, "time": entry_t.strftime("%H:%M"), "sym": sym, "side": side, "stretched": stretched,
            "status": status, "net": net, "pct": net / (entry * qty) * 100}


def run(cands, frames, cfg, mask, entry_rule, mode):
    sel = cands[mask].sort_values("t")
    taken, out = set(), []
    for _, r in sel.iterrows():
        key = (r["day"], r["sym"])
        if key in taken:
            continue
        if entry_rule == "turn":
            entry_t, spot = r["t"], r["close"]
        else:  # break of the exhaustion candle within the next 3 bars
            i = frames[r["sym"]][0]
            nxt = i[(i.index > r["t"])].head(3)
            lvl = r["hi"] if r["side"] == "loser" else r["lo"]
            hit = nxt[nxt["High"] > lvl] if r["side"] == "loser" else nxt[nxt["Low"] < lvl]
            if hit.empty or hit.index[0].date() != r["day"]:
                continue
            entry_t, spot = hit.index[0], lvl
        taken.add(key)
        out.append(trade(frames, cfg, r["sym"], r["side"], r["day"], r["t"], spot, entry_t, mode, r["stretched"]))
    return pd.DataFrame(out)


def summary(name, tr, mid):
    if tr.empty:
        return f"| {name} | 0 | - | - | - | - |"
    h1, h2 = tr[tr["day"] < mid]["net"].sum(), tr[tr["day"] >= mid]["net"].sum()
    return (f"| {name} | {len(tr)} | {(tr['status'] == 'TARGET').mean() * 100:.0f}% | {tr['pct'].mean():+.2f}% | "
            f"Rs {tr['net'].sum():+,.0f} | {h1 / 1000:+.1f}k / {h2 / 1000:+.1f}k |")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache")
    args = ap.parse_args()
    cfg = load_config()
    cands, frames = candidates(load(cfg["universe"], args.cache), cfg)
    days = sorted(cands["day"].unique())
    mid = days[len(days) // 2]
    base = cands["turned"] & cands["early"]
    variants = [
        ("Base: movers entry (turned 0.5%), desk exits", base, "turn", "desk"),
        ("+ move 2.0-3.8%, gap <= 1.5%, range <= 4.5%", base & cands["window"] & cands["nogap"], "turn", "desk"),
        ("+ 1%+ from VWAP", base & cands["vwap1"], "turn", "desk"),
        ("+ window/gap + VWAP", base & cands["window"] & cands["nogap"] & cands["vwap1"], "turn", "desk"),
        ("Exhaustion candle entry (2.5x vol, wick, break), desk exits",
         cands["exhaust"] & cands["early"], "break", "desk"),
        ("Full proposal entry (all testable filters), desk exits",
         cands["exhaust"] & cands["window"] & cands["nogap"] & cands["vwap1"] & cands["prop_time"], "break", "desk"),
        ("Full proposal entry + proposal exits (0.5%/5%, -3.5% stop, 15 min)",
         cands["exhaust"] & cands["window"] & cands["nogap"] & cands["vwap1"] & cands["prop_time"], "break", "scalp"),
        ("Exhaustion entry + proposal exits", cands["exhaust"] & cands["prop_time"], "break", "scalp"),
    ]
    print(f"{len(days)} days, {days[0]} - {days[-1]}, halves split at {mid}\n")
    print("| Variant | Trades | Hit | Avg/trade | Net | Half 1 / Half 2 |\n|---|---|---|---|---|---|")
    for name, m, rule, mode in variants:
        tr = run(cands, frames, cfg, m, rule, mode)
        print(summary(name, tr, mid))
        if name.startswith("Base") or "+ window/gap + VWAP" == name:
            for flag in (True, False):
                print(summary(f"   {'stretched week' if flag else 'ordinary'}", tr[tr["stretched"] == flag], mid))


if __name__ == "__main__":
    main()
