"""Backtest of the mover-reversal option strategy on past 5-minute data (Yahoo, ~60 days).

Replays each trading day every 15 minutes through the same agents the watcher uses
(regime -> scanner -> chart reader -> options -> risk -> decision), opens at most
`max_trades_per_day` paper trades, and exits at the net target or at square-off. No stop-loss.

Option prices are simulated with Black-Scholes at a constant volatility, with the bid-ask gap
from config. Real premiums also move with implied volatility, so treat results as an
estimate of the edge, not exact P&L.

The Macro agent (sector, crude, rupee) and the Forecast agent are tested when `use_macro` /
`use_forecast` are on. The News agent is not: there is no free history of intraday news.

Usage:  python backtest_reversal.py [--intraday intra.pkl --daily daily.pkl] [--set use_macro=true]
"""
import argparse
from datetime import datetime, time
from zoneinfo import ZoneInfo

import pandas as pd
import yaml
import yfinance as yf

from agents.chart_reader import read_chart
from agents.config import load_config
from agents.costs import round_trip_charges
from agents import macro as macro_agent
from agents.decision import decide
from agents.forecast import reversal_target
from agents.indicators import hist_vol, intraday_sigma_per_min
from agents.options import black_scholes, suggest_contract
from agents.regime import assess
from agents.risk import plan
from agents.scanner import stock_profile
from agents.sectors import SECTORS, sector_of

IST = "Asia/Kolkata"
MACRO_TICKERS = [yahoo for _, yahoo in SECTORS.values()] + ["CL=F", "INR=X"]


def load_macro(intraday_path=None, daily_path=None):
    """Sector indices, crude oil and USD/INR, as {ticker: (intraday, daily)}."""
    if intraday_path:
        intra, daily = pd.read_pickle(intraday_path), pd.read_pickle(daily_path)
    else:
        intra = yf.download(MACRO_TICKERS, period="60d", interval="5m", group_by="ticker", progress=False)
        daily = yf.download(MACRO_TICKERS, period="1y", interval="1d", group_by="ticker", progress=False)
    intra.index = intra.index.tz_convert(IST)
    return {tk: (intra[tk].dropna(subset=["Close"]), daily[tk].dropna(subset=["Close"]))
            for tk in MACRO_TICKERS if tk in intra.columns.get_level_values(0)}


def change_at(series: tuple, t, day) -> float | None:
    """Today's % change of a macro series at time t (vs its last close before `day`)."""
    if series is None:
        return None
    intra, daily = series
    now, prev = intra[intra.index <= t], daily[daily.index.date < day]
    if now.empty or prev.empty:
        return None
    return (float(now["Close"].iloc[-1]) / float(prev["Close"].iloc[-1]) - 1) * 100


def load(intraday_path, daily_path, symbols):
    if intraday_path:
        intra, daily = pd.read_pickle(intraday_path), pd.read_pickle(daily_path)
    else:
        tickers = [s + ".NS" for s in symbols] + ["^NSEI"]
        intra = yf.download(tickers, period="60d", interval="5m", group_by="ticker", progress=False, auto_adjust=False)
        daily = yf.download(tickers, period="1y", interval="1d", group_by="ticker", progress=False, auto_adjust=False)
    intra.index = intra.index.tz_convert(IST)
    frames = {}
    for tk in intra.columns.get_level_values(0).unique():
        i = intra[tk].dropna(subset=["Close"])
        d = daily[tk].dropna(subset=["Close"])
        if len(i) and len(d) > 25:
            frames[tk.removesuffix(".NS")] = (i, d)
    return frames


def option_mid(option, spot, now, cfg):
    expiry_close = datetime.combine(option["expiry"], time(15, 30), ZoneInfo(IST)).timestamp()
    years = max((expiry_close - now.timestamp()) / (365 * 86400), 1 / 365)
    price, _ = black_scholes(spot, option["strike"], years, cfg["risk_free_rate"], option["iv_used"],
                             option["type"] == "CE")
    return price


def simulate(frames, cfg, step_min=15, macro=None):
    macro = macro or {}
    nifty_i, nifty_d = frames.pop("^NSEI")
    days = sorted(set(nifty_i.index.date))
    half_spread = cfg["assumed_spread_pct"] / 200
    trades = []

    for day in days:
        n_today = nifty_i[nifty_i.index.date == day]
        taken, count = set(), 0
        for t in pd.date_range(f"{day} {cfg['entry_start']}", f"{day} {cfg['entry_end']}", freq=f"{step_min}min", tz=IST):
            if count >= cfg["max_trades_per_day"]:
                break
            n_now = n_today[n_today.index <= t]
            if n_now.empty:
                continue
            n_daily = pd.concat([nifty_d[nifty_d.index.date < day]["Close"], pd.Series([n_now["Close"].iloc[-1]])])
            mkt = assess(pd.DataFrame({"Close": n_daily.values}), None, cfg)

            rows = []
            for sym, (intra, daily) in frames.items():
                hist = intra[(intra.index <= t)]
                past = daily[daily.index.date < day]
                if hist.empty or hist.index[-1].date() != day or len(past) < 25:
                    continue
                prof = stock_profile(past)
                ltp = float(hist["Close"].iloc[-1])
                prof.update(ltp=ltp, chg_1d=(ltp / float(past["Close"].iloc[-1]) - 1) * 100)
                if prof["turnover_cr"] >= cfg["min_turnover_cr"]:
                    rows.append((sym, prof, hist, past))

            gainers = sorted((r for r in rows if r[1]["chg_1d"] >= cfg["min_move_pct"]), key=lambda r: -r[1]["chg_1d"])
            losers = sorted((r for r in rows if r[1]["chg_1d"] <= -cfg["min_move_pct"]), key=lambda r: r[1]["chg_1d"])
            for side, group in (("gainer", gainers[:cfg["top_n"]]), ("loser", losers[:cfg["top_n"]])):
                for sym, prof, hist, past in group:
                    if sym in taken or count >= cfg["max_trades_per_day"]:
                        continue
                    chart = read_chart(hist.tail(400), prof, side)
                    if chart["score"] < cfg["min_chart_score"] + mkt["threshold_adj"]:
                        continue
                    option = suggest_contract(sym, prof["ltp"], side, hist_vol(past["Close"]), None, cfg, day)
                    mid = option_mid(option, prof["ltp"], t, cfg)
                    option["est_premium"] = round(mid * (1 + half_spread), 2)  # buy at the ask
                    forecast = reversal_target(hist.tail(400), float(past["Close"].iloc[-1]), side) \
                        if cfg.get("use_forecast") else None
                    risk = plan(option, count, t.to_pydatetime(), cfg,
                                sigma_per_min=intraday_sigma_per_min(hist.tail(400)), forecast=forecast)
                    extras = []
                    if cfg.get("use_macro"):
                        sector_ticker = SECTORS[sector_of(sym)][1]
                        extras.append(macro_agent.assess(
                            sym, side, prof["chg_1d"], change_at(macro.get(sector_ticker), t, day),
                            change_at(macro.get("CL=F"), t, day), change_at(macro.get("INR=X"), t, day), cfg))
                    if decide(side, mkt, chart, risk, None, cfg, extras)["verdict"] != "TRADE":
                        continue
                    trades.append(run_trade(sym, side, option, risk, frames[sym][0], t, day, cfg, half_spread))
                    taken.add(sym)
                    count += 1
    return pd.DataFrame(trades)


def run_trade(sym, side, option, risk, intra, t, day, cfg, half_spread):
    entry, target, qty = option["est_premium"], risk["target_premium"], risk["qty"]
    square_off = pd.Timestamp(f"{day} {cfg['square_off_time']}", tz=IST)
    if cfg.get("time_exit_minutes"):
        square_off = min(square_off, t + pd.Timedelta(minutes=cfg["time_exit_minutes"]))
    after = intra[(intra.index > t) & (intra.index <= square_off)]
    exit_bid, status, closed = None, "TIME_EXIT" if square_off < pd.Timestamp(f"{day} {cfg['square_off_time']}", tz=IST) else "SQUARED_OFF", square_off
    rule = cfg.get("early_exit")  # None, "entry_bar" or "vwap": sell when the chart turns against the trade
    d = 1 if side == "loser" else -1  # +1 = we hold a CALL, -1 = a PUT
    before = intra[(intra.index < t) & (intra.index.date == day)]
    if rule and before.empty:
        rule = None
    if rule:
        ref = float(before["Low"].iloc[-1] if d > 0 else before["High"].iloc[-1])
        today = intra[intra.index.date == day]
        typical = (today["High"] + today["Low"] + today["Close"]) / 3
        vwap = (typical * today["Volume"]).cumsum() / today["Volume"].cumsum().replace(0, float("nan"))
    prev_vol = float(before["Volume"].iloc[-1]) if len(before) else 0.0
    for ts, bar in after.iterrows():
        best_spot = bar["Low"] if side == "gainer" else bar["High"]
        if option_mid(option, best_spot, ts, cfg) * (1 - half_spread) >= target:
            exit_bid, status, closed = target, "TARGET", ts
            break
        close = float(bar["Close"])
        if rule == "entry_bar":
            broken = (close - ref) * d < 0
        elif rule == "vwap":
            broken = (close - float(vwap.get(ts, close))) * d < 0 and float(bar["Volume"]) > prev_vol \
                and (close - float(bar["Open"])) * d < 0
        else:
            broken = False
        prev_vol = float(bar["Volume"])
        if broken:  # sold at the bar's close
            exit_bid, status, closed = option_mid(option, close, ts + pd.Timedelta(minutes=5), cfg) * (1 - half_spread), "CHART_EXIT", ts
            break
    if exit_bid is None:
        last_spot = after["Close"].iloc[-1] if len(after) else option["strike"]
        exit_bid = option_mid(option, last_spot, square_off, cfg) * (1 - half_spread)
    charges = round_trip_charges(entry, exit_bid, qty, cfg["charges"])["total"]
    net = (exit_bid - entry) * qty - charges
    return {"date": day, "opened": t.strftime("%H:%M"), "closed": closed.strftime("%H:%M"), "symbol": sym,
            "side": side, "contract": option["contract"], "entry": entry, "exit": round(exit_bid, 2),
            "qty": qty, "status": status, "hit_probability": round(risk["hit_probability"]),
            "net_pnl": round(net, 2), "net_pct": round(net / (entry * qty) * 100, 2)}


def report(trades: pd.DataFrame) -> str:
    if trades.empty:
        return "No trades taken."
    hits = trades["status"] == "TARGET"
    lines = [
        f"Trades: {len(trades)} over {trades['date'].nunique()} days "
        f"({trades.groupby('date').size().mean():.1f}/day on days with a trade)",
        f"Reached 1%-net target: {hits.mean() * 100:.0f}%",
        f"Average net result per trade: {trades['net_pct'].mean():+.2f}% of premium "
        f"(winners {trades.loc[hits, 'net_pct'].mean():+.2f}%, "
        f"misses {trades.loc[~hits, 'net_pct'].mean():+.2f}%)" if (~hits).any() else "",
        f"Worst trade: {trades['net_pct'].min():+.2f}%   Best: {trades['net_pct'].max():+.2f}%",
        f"Total net P&L: ₹{trades['net_pnl'].sum():,.0f}",
        f"Average forecast chance: {trades['hit_probability'].mean():.0f}% vs actual {hits.mean() * 100:.0f}%",
    ]
    for side, g in trades.groupby("side"):
        lines.append(f"  {side}s: {len(g)} trades, {(g['status'] == 'TARGET').mean() * 100:.0f}% hit, "
                     f"avg {g['net_pct'].mean():+.2f}%")
    return "\n".join(l for l in lines if l)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--intraday")
    ap.add_argument("--daily")
    ap.add_argument("--macro-intraday")
    ap.add_argument("--macro-daily")
    ap.add_argument("--out", default="journal/backtest_trades.csv")
    ap.add_argument("--set", action="append", default=[], metavar="KEY=VALUE",
                    help="try a config change without editing config.yaml, e.g. --set sides=[loser]")
    args = ap.parse_args()
    cfg = load_config()
    for item in args.set:
        key, value = item.split("=", 1)
        cfg[key] = yaml.safe_load(value)
    macro = load_macro(args.macro_intraday, args.macro_daily) if cfg.get("use_macro") else None
    trades = simulate(load(args.intraday, args.daily, cfg["universe"]), cfg, macro=macro)
    trades.to_csv(args.out, index=False)
    print(report(trades))


if __name__ == "__main__":
    main()
