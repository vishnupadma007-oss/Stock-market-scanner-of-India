"""ADR team regimes (user's design, 15 Nov 2026), tested two ways:

A. 2 years of daily data: how often each regime happens for the five stocks, and whether the stock keeps going in the
   regime's direction after the open (open -> close).
B. ~60 days of 5-minute data: each regime's entry rule with bought options (ITM1, Rs 25k per trade, all charges):
   1 macro: buy with the gap at 09:30;  2 sector: buy with the ADRs on the first pullback to VWAP (09:30-13:00);
   3 stock catalyst: first-15-minute range breakout with 2x opening volume (to 11:30);
   4 normal: exhaustion reversal (ATR stretch / VWAP 2 SD band on falling volume / RSI 75-25), target VWAP.
GIFT Nifty has no free history: the Nifty's actual opening gap stands in for it. Order-book delta and option-chain OI
walls have no history either. Credit spreads / option selling are not tested (the desk buys options only).
Usage: python backtest_adr_regimes.py
"""
import warnings

import numpy as np
import pandas as pd
import yfinance as yf

from agents import adr_team as A
from agents.config import load_config
from agents.costs import exit_for_net_target, round_trip_charges
from agents.indicators import hist_vol
from agents.options import suggest_contract
from backtest_reversal import IST, option_mid

warnings.filterwarnings("ignore")
SYMS = list(A.PAIRS)


def daily(tickers, years=2):
    raw = yf.download(tickers, period=f"{years}y", interval="1d", group_by="ticker", progress=False, auto_adjust=False)
    out = {}
    for t in tickers:
        d = raw[t].dropna(subset=["Close"]); d.index = pd.to_datetime(d.index).tz_localize(None).normalize(); out[t] = d
    return out


def context_table(D):
    """One row per Indian trading day: overnight ADR moves and volume, rupee, Brent, Nifty gap, VIX jump."""
    n = D["^NSEI"]; idx = n.index; prev = pd.Series(idx, index=idx).shift(1)

    def mv(c):
        lb = lambda d: c[c.index < d].iloc[-1] if (c.index < d).any() else np.nan
        return pd.Series([(lb(d) / lb(p) - 1) * 100 if pd.notna(p) else np.nan for d, p in zip(idx, prev)], index=idx)
    t = pd.DataFrame(index=idx)
    for s, p in A.PAIRS.items():
        a = D[p.adr]
        t["adr_" + s] = mv(a["Close"])
        vx = a["Volume"] / a["Volume"].shift(1).rolling(20).mean()
        t["vx_" + s] = [vx[vx.index < d].iloc[-1] if (vx.index < d).any() else np.nan for d in idx]
        st = D[s + ".NS"].reindex(idx)
        t["gap_" + s] = (st["Open"] / st["Close"].shift(1) - 1) * 100
        t["oc_" + s] = (st["Close"] / st["Open"] - 1) * 100
    t["usdinr"], t["brent"] = mv(D["INR=X"]["Close"]), mv(D["BZ=F"]["Close"])
    t["nifty_gap"] = (n["Open"] / n["Close"].shift(1) - 1) * 100
    v = D["^INDIAVIX"].reindex(idx)
    t["vix"] = (v["Open"] / v["Close"].shift(1) - 1) * 100
    return t.dropna(subset=["nifty_gap"])


def ctx_of(row, first15=None):
    return {"adr_pct": {s: row["adr_" + s] for s in SYMS if pd.notna(row["adr_" + s])},
            "adr_vol_x": {s: row["vx_" + s] for s in SYMS}, "nifty_gap_pct": row["nifty_gap"],
            "vix_pct": row["vix"] if pd.notna(row["vix"]) else 0, "brent_pct": row["brent"], "usdinr_pct": row["usdinr"],
            "first15_vol_x": first15}


def part_a(T):
    rows = []
    for day, r in T.iterrows():
        for s in SYMS:
            if pd.isna(r["adr_" + s]) or pd.isna(r["oc_" + s]):
                continue
            g = A.classify_regime(s, ctx_of(r))
            d = {"up": 1, "down": -1}.get(g["direction"], 0)
            reg = g["regime"] if g["regime"] != 1 else (1 if g["trigger"] == "gap" else 1.5)
            rows.append({"regime": reg, "day": day, "gap_right": float(np.sign(r["gap_" + s]) == d) if d else np.nan,
                         "oc_dir": d * r["oc_" + s] if d else np.nan, "abs_oc": abs(r["oc_" + s])})
    df = pd.DataFrame(rows); mid = df["day"].sort_values().iloc[len(df) // 2]
    print(f"A. Daily, {T.index[0].date()} - {T.index[-1].date()} ({df['day'].nunique()} days x 5 stocks)")
    print("| Regime | Stock-days | Share | Gap the regime's way | After the open the same way | Avg open->close | Halves |\n|---|---|---|---|---|---|---|")
    names = {1: "1 macro shock (Nifty gap 1.2%+)", 1.5: "1 macro shock (oil / rupee only)", 2: "2 sector catalyst", 3: "3 stock catalyst", 4: "4 normal", 0: "0 unclear"}
    for k in (1, 1.5, 2, 3, 4, 0):
        g = df[df.regime == k]
        if k in (1, 1.5, 2, 3) and len(g):
            print(f"| {names[k]} | {len(g)} | {len(g) / len(df) * 100:.0f}% | {g.gap_right.mean() * 100:.0f}% | {(g.oc_dir > 0).mean() * 100:.0f}% | "
                  f"{g.oc_dir.mean():+.2f}% | {g[g.day < mid].oc_dir.mean():+.2f} / {g[g.day >= mid].oc_dir.mean():+.2f} |")
        else:
            print(f"| {names[k]} | {len(g)} | {len(g) / len(df) * 100:.0f}% | - | - | (range {g.abs_oc.mean():.2f}%) | - |")


def sim(sym, side, intra, past, t, day, cfg, exit_rule, vwap=None, stop_spot=None, tgt_pct=10.0):
    """Buy at bar t's close (+5 min). exit_rule: 'pct' (tgt_pct on the premium), 'vwap' (spot touches VWAP), 'hold'."""
    half = cfg["assumed_spread_pct"] / 200
    spot = float(intra.loc[t, "Close"]); t5 = t + pd.Timedelta(minutes=5)
    op = suggest_contract(sym, spot, side, hist_vol(past["Close"]), None, cfg, day)
    entry = option_mid(op, spot, t5, cfg) * (1 + half)
    qty = max(int(25000 // entry), 1)
    target = exit_for_net_target(entry, qty, tgt_pct, cfg["charges"])["exit_premium"] if exit_rule == "pct" else None
    sq = pd.Timestamp(f"{day} 15:20", tz=IST)
    d = 1 if side == "loser" else -1
    exit_p, status = None, "SQUARED_OFF"
    after = intra[(intra.index > t) & (intra.index <= sq)]
    for ts, b in after.iterrows():
        best, worst = (b["High"], b["Low"]) if d > 0 else (b["Low"], b["High"])
        if stop_spot is not None and (worst - stop_spot) * d <= 0:
            exit_p, status = option_mid(op, stop_spot, ts, cfg) * (1 - half), "STOP"; break
        if exit_rule == "pct" and option_mid(op, best, ts, cfg) * (1 - half) >= target:
            exit_p, status = target, "TARGET"; break
        if exit_rule == "vwap" and (best - float(vwap[ts])) * d >= 0:
            exit_p, status = option_mid(op, float(vwap[ts]), ts, cfg) * (1 - half), "TARGET"; break
    if exit_p is None:
        exit_p = option_mid(op, float(after["Close"].iloc[-1]) if len(after) else spot, sq, cfg) * (1 - half)
    net = (exit_p - entry) * qty - round_trip_charges(entry, exit_p, qty, cfg["charges"])["total"]
    return {"day": day, "sym": sym, "status": status, "net": net, "pct": net / (entry * qty) * 100}


def part_b(T, D):
    cfg = load_config()
    raw = yf.download([s + ".NS" for s in SYMS], period="60d", interval="5m", group_by="ticker", progress=False, auto_adjust=False)
    raw.index = raw.index.tz_convert(IST)
    res = []
    for s in SYMS:
        i = raw[s + ".NS"].dropna(subset=["Close"]); dly = D[s + ".NS"]
        rs = A.rsi(i["Close"])
        days = sorted(set(i.index.date))
        f15 = {dd: i[i.index.date == dd].head(3)["Volume"].sum() for dd in days}
        for k, day in enumerate(days):
            ts = pd.Timestamp(day)
            if ts not in T.index or k < 5:
                continue
            bars = i[i.index.date == day]; past = dly[dly.index.date < day]
            if len(bars) < 20 or len(past) < 30:
                continue
            f15x = f15[day] / np.mean([f15[x] for x in days[max(0, k - 20):k]])
            g = A.classify_regime(s, ctx_of(T.loc[ts], {s: f15x}))
            vb = A.vwap_bands(bars); vw = vb["vwap"]
            d = {"up": 1, "down": -1}.get(g["direction"], 0)
            side = "loser" if d > 0 else "gainer"
            add = lambda name, tr: res.append({**tr, "rule": name})
            if g["regime"] == 1:
                t = bars.index[bars.index.strftime("%H:%M") == "09:30"]
                if len(t):
                    nm = "1 macro (Nifty gap 1.2%+)" if g["trigger"] == "gap" else "1 macro (oil / rupee only)"
                    add(nm + ": with the gap at 09:30, 10% target", sim(s, side, i, past, t[0], day, cfg, "pct"))
            elif g["regime"] == 2:
                w = bars[(bars.index.strftime("%H:%M") >= "09:30") & (bars.index.strftime("%H:%M") <= "13:00")]
                for t, b in w.iterrows():
                    if (d > 0 and b["Low"] <= vw[t] * 1.001 and b["Close"] > vw[t]) or (d < 0 and b["High"] >= vw[t] * 0.999 and b["Close"] < vw[t]):
                        add("2 sector: VWAP pullback with the ADRs, 10% target", sim(s, side, i, past, t, day, cfg, "pct")); break
            elif g["regime"] == 3:
                hi, lo = bars.head(3)["High"].max(), bars.head(3)["Low"].min()
                w = bars.iloc[3:][bars.iloc[3:].index.strftime("%H:%M") <= "11:30"]
                for t, b in w.iterrows():
                    brk = 1 if b["Close"] > hi else -1 if b["Close"] < lo else 0
                    if brk:
                        nm = "3 stock: ORB + 2x opening volume, 10% target" if f15x >= 2 else "3 stock: ORB without the volume, 10% target"
                        add(nm, sim(s, "loser" if brk > 0 else "gainer", i, past, t, day, cfg, "pct")); break
            elif g["regime"] == 4:
                atr = A.atr14(past); pv = {"high": float(past["High"].iloc[-1]), "low": float(past["Low"].iloc[-1]), "close": float(past["Close"].iloc[-1])}
                done = set()
                for j in range(6, len(bars)):
                    t = bars.index[j]
                    if not "09:45" <= t.strftime("%H:%M") <= "14:00":
                        continue
                    ex = A.detect_exhaustion(bars.iloc[:j + 1], rs[rs.index <= t], atr, pv)
                    if not ex["side"]:
                        continue
                    sd = "gainer" if ex["side"] == "up" else "loser"  # buy the reversal
                    for need in (1, 2, 3):
                        if ex["count"] >= need and need not in done:
                            done.add(need)
                            add(f"4 normal: exhaustion ({need}+ checks) -> VWAP, 1.25 ATR stop",
                                sim(s, sd, i, past, t, day, cfg, "vwap", vw, ex["stop_spot"]))
                            add(f"4 normal: exhaustion ({need}+ checks) -> VWAP, no stop",
                                sim(s, sd, i, past, t, day, cfg, "vwap", vw))
                            add(f"4 normal: exhaustion ({need}+ checks), 10% target, no stop",
                                sim(s, sd, i, past, t, day, cfg, "pct"))
    R = pd.DataFrame(res); days = sorted(R.day.unique()); mid = days[len(days) // 2]
    print(f"\nB. 5-minute data, {days[0]} - {days[-1]} ({len(days)} days), bought options, Rs 25k per trade")
    print("| Rule | Trades | Hit | Avg/trade | Net | Half 1 / Half 2 |\n|---|---|---|---|---|---|")
    for name, g in sorted(R.groupby("rule"), key=lambda kv: kv[0]):
        print(f"| {name} | {len(g)} | {(g.status == 'TARGET').mean() * 100:.0f}% | {g.pct.mean():+.2f}% | Rs {g.net.sum():+,.0f} | "
              f"{g[g.day < mid].net.sum() / 1000:+.1f}k / {g[g.day >= mid].net.sum() / 1000:+.1f}k |")


def part_c(T, D):
    """2 years of HOURLY bars: options bought at the end of the first hour (10:15), 10% target or 15:20, no stop-loss."""
    cfg = load_config()
    raw = yf.download([s + ".NS" for s in SYMS], period="730d", interval="1h", group_by="ticker", progress=False, auto_adjust=False)
    raw.index = raw.index.tz_convert(IST)
    res = []
    for s in SYMS:
        i = raw[s + ".NS"].dropna(subset=["Close"]); dly = D[s + ".NS"]
        for day in sorted(set(i.index.date)):
            ts = pd.Timestamp(day)
            bars = i[i.index.date == day]; past = dly[dly.index.date < day]
            if ts not in T.index or len(bars) < 5 or len(past) < 30 or pd.isna(T.loc[ts, "adr_" + s]):
                continue
            g = A.classify_regime(s, ctx_of(T.loc[ts]))
            d = {"up": 1, "down": -1}.get(g["direction"], 0)
            if g["regime"] not in (1, 2, 3) or not d:
                continue
            name = {1: "1 macro (Nifty gap 1.2%+)" if g.get("trigger") == "gap" else "1 macro (oil / rupee only)",
                    2: "2 sector catalyst", 3: "3 stock catalyst"}[g["regime"]]
            first_hour = (float(bars["Close"].iloc[0]) / float(bars["Open"].iloc[0]) - 1) * d  # did the first hour agree?
            for mode, dd in (("WITH", d), ("AGAINST (fade)", -d)):
                tr = sim(s, "loser" if dd > 0 else "gainer", i, past, bars.index[0], day, cfg, "pct")
                res.append({**tr, "rule": f"{name}: {mode}", "agree": first_hour > 0})
    R = pd.DataFrame(res); days = sorted(R.day.unique()); mid = days[len(days) // 2]
    print(f"\nC. Hourly data, {days[0]} - {days[-1]}, option bought at 10:15, 10% target, no stop-loss, Rs 25k per trade")
    print("| Rule | Trades | Days | Hit | Avg/trade | Net | Half 1 / Half 2 |\n|---|---|---|---|---|---|---|")
    for name, g in sorted(R.groupby("rule"), key=lambda kv: kv[0]):
        for lab, gg in (("", g), (" + first hour agreed with the trade", g[g.agree == ("WITH" in name)])):
            if len(gg):
                print(f"| {name}{lab} | {len(gg)} | {gg.day.nunique()} | {(gg.status == 'TARGET').mean() * 100:.0f}% | {gg.pct.mean():+.2f}% | "
                      f"Rs {gg.net.sum():+,.0f} | {gg[gg.day < mid].net.sum() / 1000:+.1f}k / {gg[gg.day >= mid].net.sum() / 1000:+.1f}k |")


if __name__ == "__main__":
    D = daily([s + ".NS" for s in SYMS] + [p.adr for p in A.PAIRS.values()] + ["^NSEI", "^INDIAVIX", "INR=X", "BZ=F"])
    T = context_table(D)
    part_a(T)
    part_b(T, D)
    part_c(T, D)
