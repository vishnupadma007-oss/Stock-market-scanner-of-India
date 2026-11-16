"""Results-day trades WITH the news after the stock has already faded (16 Nov 2026, EICHERMOT lesson).

Live, the worst news-team losses (EICHERMOT -11.2k, MPHASIS -25.9k, DIVISLAB -17.2k, SBIN -7.2k) were bought in the
news direction when the stock had already given back 1.5%+ from the day's high (low for a PUT) and sat under VWAP.
This checks it on ~2 years of results days (journal/results_history, gap 1%+ either way), hourly Yahoo bars:
enter WITH the gap at the close of each of the first three hourly bars, hold to 15:15, split by how far the
stock has already come back from its extreme.
Usage: python backtest_results_fade.py
"""
import json, glob, os, warnings; warnings.filterwarnings("ignore")
import pandas as pd, yfinance as yf

rows = []
days = {}
for f in glob.glob("journal/results_history/*.json"):
    s = os.path.basename(f)[:-5]
    for r in json.load(open(f)):
        re = r.get("reaction") or {}
        if re.get("reaction_day") and re.get("gap_pct") is not None and abs(re["gap_pct"]) >= 1.0:
            days.setdefault(s, []).append((re["reaction_day"], 1 if re["gap_pct"] > 0 else -1))
raw = yf.download([s + ".NS" for s in days], period="730d", interval="1h", group_by="ticker", progress=False, auto_adjust=False)
raw.index = raw.index.tz_convert("Asia/Kolkata")
for s, lst in days.items():
    i = raw[s + ".NS"].dropna(subset=["Close"])
    for day, d in lst:
        b = i[i.index.strftime("%Y-%m-%d") == day]
        if len(b) < 6:
            continue
        end = float(b["Close"].iloc[-1])
        for n in range(3):
            up = b.iloc[: n + 1]; px = float(up["Close"].iloc[-1])
            tp = (up["High"] + up["Low"] + up["Close"]) / 3; vw = float((tp * up["Volume"]).sum() / up["Volume"].sum())
            ext = float(up["High"].max()) if d > 0 else float(up["Low"].min())
            gave = (ext / px - 1) * 100 * d          # % given back from the extreme, >= 0
            rest = b.iloc[n + 1:]
            best = (float(rest["High"].max()) / px - 1) * 100 if d > 0 else (1 - float(rest["Low"].min()) / px) * 100
            rows.append({"sym": s, "day": day, "bar": n, "gave": gave, "under_vwap": (px / vw - 1) * 100 * d < -0.5,
                         "to_close": (end / px - 1) * 100 * d, "best": best})
r = pd.DataFrame(rows)
r["faded"] = (r.gave >= 1.5) | r.under_vwap
mid = sorted(r.day.unique())[len(r.day.unique()) // 2]
r["half"] = (r.day >= mid).map({False: "1st", True: "2nd"})
g = r.groupby(["faded", "half"]).agg(n=("to_close", "size"), avg_to_close=("to_close", "mean"),
                                     win=("to_close", lambda x: (x > 0).mean()), best_0_5=("best", lambda x: (x >= 0.5).mean()))
print(g.round(2)); print(r.groupby("faded").to_close.describe().round(2))
