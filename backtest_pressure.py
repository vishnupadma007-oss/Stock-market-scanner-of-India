"""Price-pressure in a flat line (user, 23 Nov 2026): the stock trades almost flat, but each little move is an uptick
(it keeps trying to go up a few paise and never really goes down); after a while it jumps up. Mirror for down.

Real tick data is not available to us historically, so this tests the idea on 1-minute candles (Yahoo keeps ~30 days):
  flat    : the last W one-minute candles span at most `tight` x sqrt(W) x the stock's usual 1-minute range
            (median over the previous days in the data);
  pressure: up-closes - down-closes >= `lead` (each candle's close vs the one before = the "upticks"),
            lows keep rising: share of candles whose low >= the previous low >= `hold`,
            and the price sits in the top third of the flat range (bottom third for down);
  entry   : "now"   - at the close of the window (before the jump),
            "jump"  - first 1-minute close above the flat range (below for down) within 5 minutes, on 1.5x volume.
Trade: ITM1 option at Black-Scholes, 15% net target (or the target given), no stop-loss, square-off 15:20, one trade per
stock per day, entries 09:45-14:30, Rs 25,000 a trade. Baseline: the same flat lines without the pressure test.
Also reported: how far the stock moved the expected way within 15 minutes.

Usage: python backtest_pressure.py
"""
import warnings; warnings.filterwarnings("ignore")
import os, pickle, sys
from datetime import datetime, timedelta
import numpy as np, pandas as pd, yfinance as yf
from agents.config import load_config
from agents.costs import exit_for_net_target, round_trip_charges
from agents.indicators import hist_vol
from agents.options import suggest_contract
from backtest_reversal import IST, option_mid
from backtest_squeeze import fno_symbols

CAPITAL = 25000
CACHE = os.environ.get("PRESSURE_CACHE", "")


def load(symbols):
    if CACHE and os.path.exists(CACHE):
        return pickle.load(open(CACHE, "rb"))
    tick = [s + ".NS" for s in symbols]
    parts, end = [], datetime.now()
    for k in range(4):  # Yahoo: 1-minute bars in 7-day pieces, last 30 days only
        e, s = end - timedelta(days=7 * k), end - timedelta(days=7 * (k + 1))
        if (end - s).days > 29:
            s = end - timedelta(days=29)
        try:
            p = yf.download(tick, start=s, end=e, interval="1m", group_by="ticker", progress=False, auto_adjust=False,
                            threads=True)
            if not p.empty:
                parts.append(p)
        except Exception as ex:
            print("piece", k, ex, file=sys.stderr)
    m1 = pd.concat(parts).sort_index(); m1 = m1[~m1.index.duplicated()]
    m1.index = m1.index.tz_convert(IST)
    dly = yf.download(tick, period="1y", interval="1d", group_by="ticker", progress=False, auto_adjust=False, threads=True)
    out = (m1, dly)
    if CACHE:
        pickle.dump(out, open(CACHE, "wb"))
    return out


def day_signals(bars, typ, w=20, tight=0.6, lead=6, hold=0.7, entry="now", use_pressure=True):
    o, h, l, c, v = (bars[k].to_numpy(float) for k in ("Open", "High", "Low", "Close", "Volume"))
    hm = bars.index.strftime("%H:%M")
    for k in range(w + 1, len(bars)):
        a = k - w
        hi, lo = h[a:k].max(), l[a:k].min()
        if hi - lo > tight * typ * w ** 0.5 or hi <= lo:
            continue
        dc = np.sign(np.diff(c[a - 1:k]))
        ups, downs = int((dc > 0).sum()), int((dc < 0).sum())
        hl = np.mean(l[a:k] >= l[a - 1:k - 1]); lh = np.mean(h[a:k] <= h[a - 1:k - 1])
        pos = (c[k - 1] - lo) / (hi - lo)
        if use_pressure:
            if ups - downs >= lead and hl >= hold and pos >= 2 / 3:
                d = 1
            elif downs - ups >= lead and lh >= hold and pos <= 1 / 3:
                d = -1
            else:
                continue
        else:
            d = 0
        j = dd = None
        if entry == "now":
            j, dd = k - 1, d
        else:
            avg_v = v[a:k].mean()
            for m in range(k, min(k + 5, len(bars))):
                if (c[m] > hi and d >= 0) or (c[m] < lo and d <= 0):
                    if v[m] >= 1.5 * avg_v:
                        j, dd = m, (1 if c[m] > hi else -1)
                    break
        if j is None or not dd or not ("09:45" <= hm[j] <= "14:30"):
            continue
        yield j, dd
        return


def run(m1, dly, symbols, w=20, tight=0.6, lead=6, hold=0.7, entry="now", tgt=15.0, use_pressure=True, cfg=None):
    cfg = cfg or load_config(); half = cfg["assumed_spread_pct"] / 200
    out = []
    for s in symbols:
        try:
            i = m1[s + ".NS"].dropna(subset=["Close"]); d = dly[s + ".NS"].dropna(subset=["Close"])
        except KeyError:
            continue
        if i.empty:
            continue
        rng = i["High"] - i["Low"]; days = sorted(set(i.index.date))
        for n_day, day in enumerate(days[2:], start=2):
            bars = i[i.index.date == day]
            if len(bars) < 200:
                continue
            past = rng[np.isin(i.index.date, days[max(n_day - 5, 0):n_day])]
            typ = float(past.median()) if len(past) else 0
            if typ <= 0:
                continue
            for j, dd in day_signals(bars, typ, w, tight, lead, hold, entry, use_pressure):
                t = bars.index[j]; spot = float(bars["Close"].iloc[j]); entry_t = t + pd.Timedelta(minutes=1)
                hv = hist_vol(d[d.index.date < day]["Close"])
                op = suggest_contract(s, spot, "loser" if dd > 0 else "gainer", hv, None, cfg, day)
                e = option_mid(op, spot, entry_t, cfg) * (1 + half); q = max(int(CAPITAL // e), 1)
                tg = exit_for_net_target(e, q, tgt, cfg["charges"])["exit_premium"]
                sq = pd.Timestamp(f"{day} 15:20", tz=IST); x = None; hit = False
                after = bars[(bars.index >= entry_t) & (bars.index <= sq)]
                for bt, b in after.iterrows():
                    if option_mid(op, b["High"] if dd > 0 else b["Low"], bt, cfg) * (1 - half) >= tg:
                        x, hit = tg, True; break
                if x is None:
                    x = option_mid(op, float(after["Close"].iloc[-1]) if len(after) else spot, sq, cfg) * (1 - half)
                net = (x - e) * q - round_trip_charges(e, x, q, cfg["charges"])["total"]
                nxt = bars[(bars.index > t) & (bars.index <= t + pd.Timedelta(minutes=15))]
                best15 = ((nxt["High"].max() / spot - 1) if dd > 0 else (1 - nxt["Low"].min() / spot)) * 100 if len(nxt) else 0
                end15 = (float(nxt["Close"].iloc[-1]) / spot - 1) * 100 * dd if len(nxt) else 0
                out.append({"sym": s, "day": day, "t": t.strftime("%H:%M"), "dir": dd, "net": net, "hit": hit,
                            "best15": best15, "end15": end15})
    return pd.DataFrame(out)


def summary(r):
    if r.empty:
        return {"trades": 0}
    days = sorted(r.day.unique()); mid = days[len(days) // 2]
    w = r[r.net > 0]
    return {"trades": len(r), "per_day": round(len(r) / len(days), 1), "hit%": round(100 * r.hit.mean()),
            "win%": round(100 * len(w) / len(r)), "right_way_15m%": round(100 * (r.end15 > 0).mean()),
            "best_15m%": round(r.best15.mean(), 2), "net": round(r.net.sum()), "avg": round(r.net.mean()),
            "half1": round(r[r.day < mid].net.sum()), "half2": round(r[r.day >= mid].net.sum())}


if __name__ == "__main__":
    syms = fno_symbols(); cfg = load_config()
    m1, dly = load(syms)
    print(f"{len(syms)} stocks, {len(set(m1.index.date))} days of 1-minute bars", file=sys.stderr)
    rows = []
    for w in (15, 30):
        for tight in (0.4, 0.6):
            for lead, hold in ((w // 3, 0.7), (w // 2, 0.8)):
                for entry in ("now", "jump"):
                    rows.append({"W": w, "tight": tight, "lead": lead, "hold": hold, "entry": entry,
                                 **summary(run(m1, dly, syms, w, tight, lead, hold, entry, cfg=cfg))})
                    print(rows[-1], file=sys.stderr)
            rows.append({"W": w, "tight": tight, "lead": "baseline", "hold": "-", "entry": "jump",
                         **summary(run(m1, dly, syms, w, tight, 0, 0, "jump", use_pressure=False, cfg=cfg))})
    pd.set_option("display.width", 250)
    print(pd.DataFrame(rows).to_string(index=False))
