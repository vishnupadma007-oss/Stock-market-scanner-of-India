"""ADR team timing (user, 16 Nov 2026): enter at the 09:15 open or at 10:15? 2 years of hourly bars, 10% target, no stop-loss."""
import warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd, yfinance as yf
import backtest_adr_regimes as B
from agents import adr_team as A
from agents.config import load_config
from agents.costs import exit_for_net_target, round_trip_charges
from agents.indicators import hist_vol
from agents.options import suggest_contract
from backtest_reversal import IST, option_mid
D = B.daily([s+".NS" for s in B.SYMS]+[p.adr for p in A.PAIRS.values()]+["^NSEI","^INDIAVIX","INR=X","BZ=F"])
T = B.context_table(D); cfg = load_config(); half = cfg["assumed_spread_pct"]/200
raw = yf.download([s+".NS" for s in B.SYMS], period="730d", interval="1h", group_by="ticker", progress=False, auto_adjust=False)
raw.index = raw.index.tz_convert(IST)
def trade(s, side, i, past, day, entry_t, spot, after_from):
    op = suggest_contract(s, spot, side, hist_vol(past["Close"]), None, cfg, day)
    e = option_mid(op, spot, entry_t, cfg)*(1+half); q = max(int(25000//e),1)
    tg = exit_for_net_target(e, q, 10.0, cfg["charges"])["exit_premium"]; d = 1 if side=="loser" else -1
    sq = pd.Timestamp(f"{day} 15:20", tz=IST); x=None; st="SQ"
    for ts,b in i[(i.index>=after_from)&(i.index<=sq)].iterrows():
        if option_mid(op, b["High"] if d>0 else b["Low"], ts, cfg)*(1-half) >= tg: x, st = tg, "T"; break
    if x is None: x = option_mid(op, float(i[i.index<=sq]["Close"].iloc[-1]), sq, cfg)*(1-half)
    net = (x-e)*q - round_trip_charges(e,x,q,cfg["charges"])["total"]
    return net, st
rows=[]
for s in B.SYMS:
    i = raw[s+".NS"].dropna(subset=["Close"]); dly = D[s+".NS"]
    for day in sorted(set(i.index.date)):
        ts = pd.Timestamp(day); bars = i[i.index.date==day]; past = dly[dly.index.date<day]
        if ts not in T.index or len(bars)<5 or len(past)<30 or pd.isna(T.loc[ts,"adr_"+s]): continue
        g = A.classify_regime(s, B.ctx_of(T.loc[ts])); d = {"up":1,"down":-1}.get(g["direction"],0)
        if not d or g["regime"] not in (1,3) or (g["regime"]==1 and g.get("trigger")!="gap"): continue
        name = "stock catalyst" if g["regime"]==3 else "macro gap 1.2%+"
        b0 = bars.index[0]; o = float(bars["Open"].iloc[0])
        fh = (float(bars["Close"].iloc[0])/o-1)*d  # first hour vs the move
        for mode, dd in (("WITH", d), ("AGAINST", -d)):
            side = "loser" if dd>0 else "gainer"
            n0, s0 = trade(s, side, i, past, day, b0+pd.Timedelta(minutes=1), o, b0)  # at the 09:15 open
            n1, s1 = trade(s, side, i, past, day, b0+pd.Timedelta(minutes=60), float(bars["Close"].iloc[0]), b0+pd.Timedelta(minutes=60))
            rows += [{"rule":name,"mode":mode,"when":"09:15 open","net":n0,"hit":s0=="T","day":day,"turned":fh<0},
                     {"rule":name,"mode":mode,"when":"10:15","net":n1,"hit":s1=="T","day":day,"turned":fh<0}]
R = pd.DataFrame(rows); days = sorted(R.day.unique()); mid = days[len(days)//2]
print("| Regime | Direction | Entry | Trades | Hit | Net | Half 1 / Half 2 |\n|---|---|---|---|---|---|---|")
for (r,m,w),g in R.groupby(["rule","mode","when"]):
    print(f"| {r} | {m} | {w} | {len(g)} | {g.hit.mean()*100:.0f}% | Rs {g.net.sum():+,.0f} | {g[g.day<mid].net.sum()/1000:+.1f}k / {g[g.day>=mid].net.sum()/1000:+.1f}k |")
