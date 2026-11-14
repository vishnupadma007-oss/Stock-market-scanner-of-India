"""ADR team idea (user, 14 Nov 2026): trade only INFY, WIPRO, HDFCBANK, ICICIBANK, DRREDDY on the overnight (ADR) forecast.
Usage: python backtest_adr_team.py"""
import numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
from agents import overnight as o
from agents.config import load_config
from agents.options import suggest_contract
from agents.indicators import hist_vol, intraday_sigma_per_min
from agents.risk import plan
from backtest_reversal import option_mid, run_trade, IST
import yfinance as yf
F = list(o.ADRS)
# (a) 2 years daily: does the stock keep going after the open in the ADR-forecast direction?
tab = o.gap_table(F, 2); cut = tab.index[int(len(tab)*0.5)]
m = o.fit(tab[tab.index < cut], F)
data = o._daily([s+".NS" for s in F], 2)
rows=[]
for s in F:
    d=data[s+".NS"]; oc=(d["Close"]/d["Open"]-1)*100; rng=(d["High"]-d["Low"])/d["Open"]*100
    for day,r in tab[tab.index>=cut].iterrows():
        if day not in oc.index or pd.isna(r.get(s)): continue
        p=o.predict_gap(s,m,r["spx"],r["brent"],r.get("adr_"+s))
        rows.append({"s":s,"day":day,"p":p,"gap":r[s],"oc_dir":np.sign(p)*oc[day],"rng":rng[day]})
df=pd.DataFrame(rows)
print("Daily, last 12 months (model fitted on the year before):")
print(f"  typical day range high-low: {df.rng.median():.1f}%  (2%+ on {(df.rng>=2).mean()*100:.0f}% of days)")
for lo in (0.0,0.5,1.0):
    g=df[df.p.abs()>=lo]
    print(f"  forecast >= {lo}%: n={len(g)} gap right {(np.sign(g.p)==np.sign(g.gap)).mean()*100:.0f}% | after the open, same way: right {(g.oc_dir>0).mean()*100:.0f}% avg {g.oc_dir.mean():+.2f}%")
# (b) 60 days 5-min: buy an option at 09:30 with / against the forecast, 5% and 10% targets, no stop, 15:20 exit
cfg=load_config(); half=cfg["assumed_spread_pct"]/200
intra=yf.download([s+".NS" for s in F],period="60d",interval="5m",group_by="ticker",progress=False,auto_adjust=False)
intra.index=intra.index.tz_convert(IST)
m2=o.fit(tab[tab.index < tab.index[-60]], F)
res=[]
for s in F:
    i=intra[s+".NS"].dropna(subset=["Close"]); dly=data[s+".NS"]
    for day in sorted(set(i.index.date)):
        ts=pd.Timestamp(day)
        if ts not in tab.index: continue
        r=tab.loc[ts]; p=o.predict_gap(s,m2,r["spx"],r["brent"],r.get("adr_"+s))
        t=pd.Timestamp(f"{day} 09:30",tz=IST); h=i[i.index<=t]
        if h.empty or h.index[-1].date()!=day: continue
        past=dly[dly.index.date<day]; spot=float(h["Close"].iloc[-1])
        for mode,dd in (("with",np.sign(p)),("against",-np.sign(p))):
            if dd==0: continue
            side="loser" if dd>0 else "gainer"
            for tgt in (5.0,10.0):
                c={**cfg,"net_target_pct":tgt}
                op=suggest_contract(s,spot,side,hist_vol(past["Close"]),None,c,day)
                op["est_premium"]=round(option_mid(op,spot,t,c)*(1+half),2)
                pl=plan(op,0,t.to_pydatetime(),c,sigma_per_min=intraday_sigma_per_min(h.tail(400)))
                pl["qty"]=max(int(25000//op["est_premium"]),1)
                from agents.costs import exit_for_net_target
                pl["target_premium"]=exit_for_net_target(op["est_premium"],pl["qty"],tgt,c["charges"])["exit_premium"]
                tr=run_trade(s,side,op,pl,i,t,day,c,half)
                res.append({**tr,"mode":mode,"tgt":tgt,"big":abs(p)>=0.5,"day":day})
R=pd.DataFrame(res); mid=sorted(R.day.unique())[len(R.day.unique())//2]
print(f"\n60 days x 5 stocks, option bought 09:30, Rs 25k each, no stop-loss, 15:20 exit ({R.day.nunique()} days):")
for (tgt,mode),g in R.groupby(["tgt","mode"]):
    for lab,gg in (("all",g),("forecast>=0.5%",g[g.big])):
        print(f"  {tgt:4.0f}% target {mode:7} {lab:15} n={len(gg):3} hit {(gg.status=='TARGET').mean()*100:3.0f}% avg {gg.net_pct.mean():+6.2f}% net Rs {gg.net_pnl.sum():+9,.0f} halves {gg[gg.day<mid].net_pnl.sum():+8,.0f}/{gg[gg.day>=mid].net_pnl.sum():+8,.0f}")
