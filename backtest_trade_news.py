"""Replay of the Trade News Monitor (agents/trade_news.py) on the desk's real paper trades: every
trade in journal/paper_trades.csv is walked through 5-minute bars from its entry to its actual
exit, with the news that was in the intelligence log (journal/intel/<date>.jsonl) at each moment.
The option is re-priced from the stock (Black-Scholes at the volatility implied by the real entry
price), so the model's own "no monitor" result is shown beside the monitor's for a fair compare.
Market shock states were not logged in the past, so only news items are replayed.

Usage:  python backtest_trade_news.py --intraday intra.pkl [--set raise_pct=5]
"""
import argparse
import re
from datetime import date, datetime, time

import pandas as pd
import yaml

from agents import intel, trade_news
from agents.config import load_config
from agents.costs import round_trip_charges
from agents.options import black_scholes

IST = "Asia/Kolkata"
MONTHS = {m: i for i, m in enumerate(["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"], 1)}


def parse_contract(contract: str, year: int) -> dict:
    m = re.match(r"(.+)-(\d{2})-([A-Z]{3})-([\d.]+)-(CALL|PUT)$", contract)
    sym, dd, mon, strike, kind = m.groups()
    return {"expiry": date(year, MONTHS[mon], int(dd)), "strike": float(strike), "call": kind == "CALL"}


def years(expiry: date, at: datetime) -> float:
    close = pd.Timestamp(datetime.combine(expiry, time(15, 30)), tz=IST)
    return max((close - at).total_seconds() / (365 * 86400), 1 / 365)


def implied_vol(price: float, spot: float, k: dict, at, rate: float) -> float:
    lo, hi = 0.02, 3.0
    for _ in range(60):
        mid = (lo + hi) / 2
        if black_scholes(spot, k["strike"], years(k["expiry"], at), rate, mid, k["call"]).price > price:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2


def replay(trade: dict, intra: pd.DataFrame, items: list[dict], cfg: dict, tn: dict) -> dict | None:
    day = trade["date"]
    k = parse_contract(trade["contract"], int(day[:4]))
    t0 = pd.Timestamp(f"{day} {trade['opened']}", tz=IST)
    end = pd.Timestamp(f"{day} {trade['closed'] if pd.notna(trade['closed']) else cfg['square_off_time']}", tz=IST)
    sq = pd.Timestamp(f"{day} {cfg['square_off_time']}", tz=IST)
    bars = intra[(intra.index.date == t0.date())]
    before = bars[bars.index <= t0]
    if before.empty:
        return None
    rate, half = cfg["risk_free_rate"], cfg["assumed_spread_pct"] / 200
    entry, qty = float(trade["entry_ask"]), int(trade["qty"])
    vol = implied_vol(entry / (1 + half), float(before["Close"].iloc[-1]), k, t0, rate)
    bid = lambda spot, at: black_scholes(float(spot), k["strike"], years(k["expiry"], at), rate, vol, k["call"]).price * (1 - half)

    def walk(monitor: bool):
        target, notes, action = float(trade["target_bid"]), str(trade.get("notes", "")), "hold"
        stop_at = sq if monitor else end  # the monitor may hold a raised-target trade past its real exit
        for ts, bar in bars[(bars.index > t0) & (bars.index <= stop_at)].iterrows():
            at = ts + pd.Timedelta(minutes=5)
            best = bar["High"] if k["call"] else bar["Low"]
            if bid(best, at) >= target:
                return target, "TARGET", at, action
            if monitor:
                v = trade_news.check({**trade, "notes": notes}, items, at.to_pydatetime(), "normal", tn)
                if v["action"] == "exit":
                    return bid(bar["Close"], at), "NEWS_EXIT", at, v["reason"]
                if v["action"] == "raise":
                    target = trade_news.raised_target({**trade, "target_bid": target}, tn)
                    notes += "; news target raised"
                    action = v["reason"]
        last = bars[bars.index <= stop_at]
        return bid(last["Close"].iloc[-1], stop_at), "SQUARED_OFF", stop_at, action

    out = {}
    for name, mon in (("model", False), ("monitor", True)):
        px, status, at, why = walk(mon)
        charges = round_trip_charges(entry, px, qty, cfg["charges"])["total"]
        out[name] = {"exit": round(px, 2), "status": status, "at": at.strftime("%H:%M"),
                     "net": round((px - entry) * qty - charges), "why": why}
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--intraday", required=True)
    ap.add_argument("--set", action="append", default=[], metavar="KEY=VALUE")
    args = ap.parse_args()
    cfg = load_config()
    tn = {**trade_news.DEFAULTS, **(cfg.get("trade_news") or {}), "_ai": {**(cfg.get("ai") or {}), "max_calls_per_day": 1000}, "_ai_wait": 7}
    for item in args.set:
        key, value = item.split("=", 1)
        tn[key] = yaml.safe_load(value)
    raw = pd.read_pickle(args.intraday)
    raw.index = raw.index.tz_convert(IST)
    trades = pd.read_csv("journal/paper_trades.csv", dtype=str)
    trades = trades[trades["status"] != "OPEN"]
    rows = []
    for t in trades.to_dict("records"):
        if (t["symbol"] + ".NS") not in raw.columns.get_level_values(0):
            continue
        intra = raw[t["symbol"] + ".NS"].dropna(subset=["Close"])
        r = replay(t, intra, intel.load(t["date"]), cfg, tn)
        if r:
            rows.append({"date": t["date"], "symbol": t["symbol"], "strategy": t["strategy"],
                         "actual": float(t["net_pnl"]), "model": r["model"]["net"], "monitor": r["monitor"]["net"],
                         "monitor_exit": f"{r['monitor']['status']} {r['monitor']['at']}", "why": r["monitor"]["why"]})
    df = pd.DataFrame(rows)
    pd.set_option("display.width", 250)
    pd.set_option("display.max_colwidth", 90)
    print(df.to_string(index=False))
    print(f"\nTotal: actual Rs {df['actual'].sum():,.0f} | model without monitor Rs {df['model'].sum():,.0f} | "
          f"with monitor Rs {df['monitor'].sum():,.0f}; monitor acted on {(df['why'] != 'hold').sum()} of {len(df)} trades")


if __name__ == "__main__":
    main()
