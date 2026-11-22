"""Squeeze team idea (user, 22 Nov 2026): every F&O stock now and then goes quiet for a while (a "stagnation" on the
5/10/15-minute chart). Inside that quiet patch, count the candles: more green than red -> the stock is likely to break
UP (buy a CALL); more red than green -> DOWN (buy a PUT). Enhanced with: breakout of the quiet range on extra volume,
volume on green vs red candles, VWAP side and 9/21-EMA.

Quiet patch = the last N 5-minute candles span at most `tight` x the stock's usual 5-minute candle range (median of
the last 20 days' bars at that point), i.e. a tight box.
Vote      = greens - reds among the N candles (>= `vote`), and buying volume > selling volume (the other way for PUTs).
Entry     = "box"   : at the close of the candle that ends the quiet patch (no breakout needed)
            "break" : the first candle within 6 bars that closes outside the box the vote's way on 1.2x the box's
                      average volume
Filters   = optional: price the right side of VWAP and 9-EMA the right side of 21-EMA.
Trade     = buy the ATM option (Black-Scholes premium, as in the other backtests), target X% net of all charges,
            no stop-loss, square-off 15:20, one trade per stock per day, entries 09:45-14:30, Rs 25,000 per trade.
Baseline  = the same breakouts with NO candle vote, to see whether counting candles adds anything.

5-minute bars from Yahoo (~60 days), every F&O stock. Usage: python backtest_squeeze.py
"""
import warnings; warnings.filterwarnings("ignore")
import itertools, os, pickle, sys
import numpy as np, pandas as pd, yfinance as yf
from agents import data
from agents.config import load_config
from agents.costs import exit_for_net_target, round_trip_charges
from agents.indicators import hist_vol
from agents.options import black_scholes, strike_step, suggest_contract
from agents.squeeze import day_signals
from backtest_reversal import IST, option_mid

CAPITAL = 25000
INDICES = {"NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "NIFTYNXT50", "NIFTYFPI"}
CACHE = os.environ.get("SQUEEZE_CACHE", "")


def fno_symbols() -> list[str]:
    return sorted(s for s in data.nse_lot_sizes() if s not in INDICES)


def load(symbols):
    if CACHE and os.path.exists(CACHE):
        return pickle.load(open(CACHE, "rb"))
    tick = [s + ".NS" for s in symbols]
    i5 = yf.download(tick, period="60d", interval="5m", group_by="ticker", progress=False, auto_adjust=False, threads=True)
    i5.index = i5.index.tz_convert(IST)
    dly = yf.download(tick, period="1y", interval="1d", group_by="ticker", progress=False, auto_adjust=False, threads=True)
    out = (i5, dly)
    if CACHE:
        pickle.dump(out, open(CACHE, "wb"))
    return out


def run(i5, dly, symbols, n=6, tight=1.0, vote=2, entry="break", filt=True, tgt=10.0, use_vote=True, cfg=None,
        strike_steps=None, min_dte=None):
    """strike_steps: strikes in the money (1 = ITM1, 0 = ATM, -1 = one out of the money; None = config's choice);
    min_dte: roll to next month when expiry is closer than this many days (more days = less theta and gamma)."""
    cfg = cfg or load_config(); half = cfg["assumed_spread_pct"] / 200
    if min_dte is not None:
        cfg = {**cfg, "min_days_to_expiry": min_dte}
    out = []
    for s in symbols:
        try:
            i = i5[s + ".NS"].dropna(subset=["Close"]); d = dly[s + ".NS"].dropna(subset=["Close"])
        except KeyError:
            continue
        if i.empty or d.empty:
            continue
        rng = (i["High"] - i["Low"])
        days = sorted(set(i.index.date))
        for day in days[20:]:
            bars = i[i.index.date == day].copy()
            if len(bars) < 40:
                continue
            past = rng[(i.index.date < day) & (i.index.date >= days[max(days.index(day) - 20, 0)])]
            typ = float(past.median()) if len(past) else float(rng.median())
            for j, dd, _ in day_signals(bars, typ, n, tight, vote, entry, filt, use_vote):
                t = bars.index[j]; spot = float(bars["Close"].iloc[j]); entry_t = t + pd.Timedelta(minutes=5)
                hv = hist_vol(d[d.index.date < day]["Close"])
                op = suggest_contract(s, spot, "loser" if dd > 0 else "gainer", hv, None, cfg, day)
                if strike_steps is not None:
                    stp = strike_step(spot); atm = round(spot / stp) * stp
                    op = {**op, "strike": atm - strike_steps * stp if dd > 0 else atm + strike_steps * stp}
                yrs = max(op["days_to_expiry"], 1) / 365
                g0 = black_scholes(spot, op["strike"], yrs, cfg["risk_free_rate"], op["iv_used"], dd > 0)
                e = option_mid(op, spot, entry_t, cfg) * (1 + half); q = max(int(CAPITAL // e), 1)
                tg = exit_for_net_target(e, q, tgt, cfg["charges"])["exit_premium"]
                sq = pd.Timestamp(f"{day} 15:20", tz=IST); x = None; hit = False
                for bt, b in bars[(bars.index >= entry_t) & (bars.index <= sq)].iterrows():
                    if option_mid(op, b["High"] if dd > 0 else b["Low"], bt, cfg) * (1 - half) >= tg:
                        x, hit = tg, True; break
                if x is None:
                    x = option_mid(op, float(bars[bars.index <= sq]["Close"].iloc[-1]), sq, cfg) * (1 - half)
                net = (x - e) * q - round_trip_charges(e, x, q, cfg["charges"])["total"]
                move = (float(bars[bars.index <= sq]["Close"].iloc[-1]) / spot - 1) * 100 * dd
                out.append({"sym": s, "day": day, "t": t.strftime("%H:%M"), "dir": dd, "net": net, "hit": hit,
                            "move_to_close": move, "delta": abs(g0.delta), "theta_pct": g0.theta / max(g0.price, 0.05) * 100,
                            "gamma_pct": g0.gamma * spot * 0.01 / max(abs(g0.delta), 1e-6) * 100, "dte": op["days_to_expiry"]})
    return pd.DataFrame(out)


def summary(r: pd.DataFrame) -> dict:
    if r.empty:
        return {"trades": 0}
    days = sorted(r.day.unique()); mid = days[len(days) // 2]
    a, b = r[r.day < mid], r[r.day >= mid]
    return {"trades": len(r), "per_day": round(len(r) / len(days), 1), "hit%": round(100 * r.hit.mean()),
            "right_way%": round(100 * (r.move_to_close > 0).mean()), "net": round(r.net.sum()),
            "avg": round(r.net.mean()), "worst": round(r.net.min()), "half1": round(a.net.sum()), "half2": round(b.net.sum())}


if __name__ == "__main__":
    syms = fno_symbols(); cfg = load_config()
    print(f"{len(syms)} F&O stocks", file=sys.stderr)
    i5, dly = load(syms)
    rows = []
    votes = {6: (2, 4), 9: (3, 5), 12: (4, 6)}  # a small lead, or a big one (e.g. 5 green of 6)
    grid = [(n, t, v, e, f, 10.0) for n in votes for t in (0.5, 0.8) for v in votes[n] for e in ("break", "box")
            for f in (True, False)]
    for n, tight, vote, entry, filt, tgt in grid:
        rows.append({"n": n, "tight": tight, "vote": vote, "entry": entry, "filter": filt, "target%": tgt,
                     **summary(run(i5, dly, syms, n, tight, vote, entry, filt, tgt, cfg=cfg))})
        print(rows[-1], file=sys.stderr)
    for n, tight in itertools.product((6, 9, 12), (0.5, 0.8)):
        rows.append({"n": n, "tight": tight, "vote": "none (baseline)", "entry": "break", "filter": False, "target%": 10.0,
                     **summary(run(i5, dly, syms, n, tight, 0, "break", False, 10.0, use_vote=False, cfg=cfg))})
    pd.set_option("display.width", 250)
    print(pd.DataFrame(rows).to_string(index=False))
