"""ADR stocks' daily swing (user, 16 Nov 2026): "after a rise there is a pullback, after a fall a recovery".

On the five ADR stocks, buy a PUT when the stock has risen from its open by its usual daily stretch
(k x the median of its last 20 days' high-from-open), or a CALL when it has fallen by its usual stretch,
once a 5-minute candle turns. Small target (2% / 3% net of charges), several trades a day, one open trade per stock,
no stop-loss, square-off 15:20. Variant "adr": skip fading the move the ADR pointed to overnight (|ADR| >= 1%).

5-minute bars (Yahoo, ~60 days) and Black-Scholes premiums as in the other backtests. Rs 25,000 per trade.
Usage: python backtest_adr_swing.py
"""
import warnings; warnings.filterwarnings("ignore")
import itertools
import numpy as np, pandas as pd, yfinance as yf
import backtest_adr_regimes as B
from agents.config import load_config
from agents.costs import exit_for_net_target, round_trip_charges
from agents.indicators import hist_vol
from agents.options import suggest_contract
from backtest_reversal import IST, option_mid

CAPITAL = 25000


def load():
    D = B.daily([s + ".NS" for s in B.SYMS] + [p.adr for p in B.A.PAIRS.values()] + ["^NSEI", "^INDIAVIX", "INR=X", "BZ=F"])
    T = B.context_table(D)
    raw = yf.download([s + ".NS" for s in B.SYMS], period="60d", interval="5m", group_by="ticker", progress=False,
                      auto_adjust=False)
    raw.index = raw.index.tz_convert(IST)
    return D, T, raw


def run(D, T, raw, k, tgt, use_adr, from_t="09:30", until_t="14:45", cfg=None):
    cfg = cfg or load_config(); half = cfg["assumed_spread_pct"] / 200
    out = []
    for s in B.SYMS:
        i = raw[s + ".NS"].dropna(subset=["Close"]); dly = D[s + ".NS"].dropna(subset=["Close"])
        stretch_up = ((dly["High"] / dly["Open"] - 1) * 100).rolling(20).median().shift(1)
        stretch_dn = ((1 - dly["Low"] / dly["Open"]) * 100).rolling(20).median().shift(1)
        for day in sorted(set(i.index.date)):
            ts = pd.Timestamp(day); bars = i[i.index.date == day]
            if ts not in stretch_up.index or pd.isna(stretch_up.loc[ts]) or len(bars) < 40:
                continue
            past = dly[dly.index < ts]; hv = hist_vol(past["Close"])
            adr = T.loc[ts, "adr_" + s] if ts in T.index else np.nan
            o = float(bars["Open"].iloc[0]); up_th, dn_th = k * stretch_up.loc[ts], k * stretch_dn.loc[ts]
            busy_until = None
            for n in range(1, len(bars)):
                t = bars.index[n]; hm = t.strftime("%H:%M")
                if hm < from_t or hm > until_t or (busy_until is not None and t <= busy_until):
                    continue
                c, pc = float(bars["Close"].iloc[n]), float(bars["Close"].iloc[n - 1])
                mv = (c / o - 1) * 100
                if mv >= up_th and c < pc:
                    side, d = "gainer", -1      # risen -> pullback -> PUT
                elif -mv >= dn_th and c > pc:
                    side, d = "loser", 1        # fallen -> recovery -> CALL
                else:
                    continue
                if use_adr and pd.notna(adr) and abs(adr) >= 1.0 and np.sign(adr) == -d:
                    continue                   # the ADR said this move is real: don't fade it
                entry_t = t + pd.Timedelta(minutes=5)
                op = suggest_contract(s, c, side, hv, None, cfg, day)
                e = option_mid(op, c, entry_t, cfg) * (1 + half); q = max(int(CAPITAL // e), 1)
                tg = exit_for_net_target(e, q, tgt, cfg["charges"])["exit_premium"]
                sq = pd.Timestamp(f"{day} 15:20", tz=IST); x = None; st = "SQ"; xt = sq
                for bt, b in bars[(bars.index >= entry_t) & (bars.index <= sq)].iterrows():
                    if option_mid(op, b["High"] if d > 0 else b["Low"], bt, cfg) * (1 - half) >= tg:
                        x, st, xt = tg, "T", bt; break
                if x is None:
                    x = option_mid(op, float(bars[bars.index <= sq]["Close"].iloc[-1]), sq, cfg) * (1 - half)
                net = (x - e) * q - round_trip_charges(e, x, q, cfg["charges"])["total"]
                out.append({"sym": s, "day": day, "t": hm, "dir": d, "net": net, "hit": st == "T"})
                busy_until = xt
    return pd.DataFrame(out)


def summary(r: pd.DataFrame) -> dict:
    if r.empty:
        return {"trades": 0}
    days = sorted(r.day.unique()); mid = days[len(days) // 2]
    a, b = r[r.day < mid], r[r.day >= mid]
    return {"trades": len(r), "per_day": round(len(r) / len(days), 1), "hit%": round(100 * r.hit.mean()),
            "net": round(r.net.sum()), "avg_win": round(r[r.net > 0].net.mean()), "avg_loss": round(r[r.net <= 0].net.mean()),
            "worst": round(r.net.min()), "half1": round(a.net.sum()), "half2": round(b.net.sum())}


if __name__ == "__main__":
    D, T, raw = load(); cfg = load_config()
    rows = []
    for k, tgt, use_adr in itertools.product((0.6, 0.8, 1.0, 1.3), (2.0, 3.0), (False, True)):
        rows.append({"k": k, "target%": tgt, "adr_filter": use_adr, **summary(run(D, T, raw, k, tgt, use_adr, cfg=cfg))})
    pd.set_option("display.width", 200)
    print(pd.DataFrame(rows).to_string(index=False))
