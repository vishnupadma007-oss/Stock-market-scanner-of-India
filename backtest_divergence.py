"""Divergence recovery (user, 16 Nov 2026): Nifty opens one way, the stock opens the other way (often because its ADR fell
or rose overnight) -> buy the stock's recovery in the Nifty's direction. 2 years of hourly bars; entry at the 09:15 open
or at 10:15; 10% net target, no stop-loss, 15:20 square-off, Rs 25k per trade, ITM1 option, all charges.
Usage: python backtest_divergence.py"""
import warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd, yfinance as yf
from agents import adr_team as A
from agents.config import load_config
from agents.costs import exit_for_net_target, round_trip_charges
from agents.indicators import hist_vol
from agents.options import suggest_contract
from backtest_reversal import IST, option_mid

cfg = load_config(); half = cfg["assumed_spread_pct"] / 200


def trade(s, side, i, past, day, entry_t, spot, after_from):
    op = suggest_contract(s, spot, side, hist_vol(past["Close"]), None, cfg, day)
    e = option_mid(op, spot, entry_t, cfg) * (1 + half); q = max(int(25000 // e), 1)
    tg = exit_for_net_target(e, q, 10.0, cfg["charges"])["exit_premium"]; d = 1 if side == "loser" else -1
    sq = pd.Timestamp(f"{day} 15:20", tz=IST); x = None; hit = False
    for ts, b in i[(i.index >= after_from) & (i.index <= sq)].iterrows():
        if option_mid(op, b["High"] if d > 0 else b["Low"], ts, cfg) * (1 - half) >= tg:
            x, hit = tg, True; break
    if x is None:
        x = option_mid(op, float(i[i.index <= sq]["Close"].iloc[-1]), sq, cfg) * (1 - half)
    return (x - e) * q - round_trip_charges(e, x, q, cfg["charges"])["total"], hit


def run(symbols):
    raw = yf.download([s + ".NS" for s in symbols] + ["^NSEI"], period="730d", interval="1h", group_by="ticker", progress=False, auto_adjust=False)
    dl = yf.download([s + ".NS" for s in symbols] + ["^NSEI"], period="3y", interval="1d", group_by="ticker", progress=False, auto_adjust=False)
    raw.index = raw.index.tz_convert(IST)
    nd = dl["^NSEI"].dropna(subset=["Close"]); nd.index = pd.to_datetime(nd.index).tz_localize(None).normalize()
    ngap = (nd["Open"] / nd["Close"].shift(1) - 1) * 100
    rows = []
    for s in symbols:
        if s + ".NS" not in raw.columns.get_level_values(0):
            continue
        i = raw[s + ".NS"].dropna(subset=["Close"]); d = dl[s + ".NS"].dropna(subset=["Close"])
        d.index = pd.to_datetime(d.index).tz_localize(None).normalize()
        sgap = (d["Open"] / d["Close"].shift(1) - 1) * 100
        for day in sorted(set(i.index.date)):
            ts = pd.Timestamp(day)
            if ts not in sgap.index or ts not in ngap.index:
                continue
            g, n = sgap[ts], ngap[ts]
            if pd.isna(g) or pd.isna(n) or abs(n) < 0.3 or abs(g) < 0.5 or g * n > 0 or abs(g) > 8:
                continue
            bars = i[i.index.date == day]; past = d[d.index < ts]
            if len(bars) < 5 or len(past) < 30:
                continue
            dn = 1 if n > 0 else -1  # recovery = the Nifty's direction
            side = "loser" if dn > 0 else "gainer"
            b0 = bars.index[0]; o = float(bars["Open"].iloc[0]); c1 = float(bars["Close"].iloc[0])
            turned = (c1 / o - 1) * dn > 0  # first hour already recovering
            n0, h0 = trade(s, side, i, past, day, b0 + pd.Timedelta(minutes=1), o, b0)
            n1, h1 = trade(s, side, i, past, day, b0 + pd.Timedelta(minutes=60), c1, b0 + pd.Timedelta(minutes=60))
            size = "stock gap 0.5-1.5%" if abs(g) < 1.5 else "stock gap 1.5%+"
            rows += [{"day": day, "sym": s, "entry": "09:15 open", "size": size, "turned": turned, "net": n0, "hit": h0},
                     {"day": day, "sym": s, "entry": "10:15", "size": size, "turned": turned, "net": n1, "hit": h1}]
    return pd.DataFrame(rows)


def table(R, title):
    days = sorted(R.day.unique()); mid = days[len(days) // 2]
    print(f"\n{title} ({len(days)} days)")
    print("| Stock gap | Entry | Filter | Trades | Hit | Avg Rs | Net | Half 1 / Half 2 |\n|---|---|---|---|---|---|---|---|")
    for (size, entry), g in R.groupby(["size", "entry"]):
        for lab, gg in (("all", g), ("first hour recovering", g[g.turned]) if entry == "10:15" else ("all", None)):
            if gg is None or not len(gg):
                continue
            print(f"| {size} | {entry} | {lab} | {len(gg)} | {gg.hit.mean() * 100:.0f}% | {gg.net.mean():+,.0f} | Rs {gg.net.sum():+,.0f} | "
                  f"{gg[gg.day < mid].net.sum() / 1000:+.1f}k / {gg[gg.day >= mid].net.sum() / 1000:+.1f}k |")


if __name__ == "__main__":
    table(run(list(A.PAIRS)), "Five ADR stocks: Nifty opens one way (0.3%+), the stock the other way (0.5%+) -> buy the recovery")
    table(run(load_config()["universe"]), "All 76 F&O stocks, same rule")
