"""Evening review of the paper trades in journal/paper_trades.csv.

Writes journal/reviews/<date>.md with today's results, the running totals, rules-only vs
Claude-confirmed results, and breakdowns that show where the strategy wins and loses. It
also says whether enough trades have built up since the last strategy change to justify
proposing a new one (see journal/strategy_changes.md).

Usage:  python review.py [--date YYYY-MM-DD]
"""
import argparse
import re
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
TRADES = ROOT / "journal" / "paper_trades.csv"
CHANGES = ROOT / "journal" / "strategy_changes.md"
REVIEWS = ROOT / "journal" / "reviews"
MIN_TRADES_FOR_PROPOSAL = 30
NUMERIC = ["qty", "entry_ask", "exit_bid", "spread_pct", "hit_probability", "chart_score", "net_pnl"]


def load(path: Path = TRADES) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path, dtype=str).fillna("")
    for col in NUMERIC:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    closed = df[df["status"].isin(["TARGET", "SQUARED_OFF"])].copy()
    closed["net_pct"] = closed["net_pnl"] / (closed["entry_ask"] * closed["qty"]) * 100
    closed["hit"] = closed["status"] == "TARGET"
    return closed


def last_change_date(path: Path = CHANGES) -> str:
    dates = re.findall(r"^\|\s*(\d{4}-\d{2}-\d{2})", path.read_text(), re.M) if path.exists() else []
    return max(dates) if dates else "0000-00-00"


def _stats(g: pd.DataFrame) -> str:
    return (f"{len(g)} trades, {g['hit'].mean() * 100:.0f}% hit target, "
            f"avg {g['net_pct'].mean():+.2f}% of premium, net ₹{g['net_pnl'].sum():,.0f}")


def _breakdown(df: pd.DataFrame, title: str, key) -> list[str]:
    lines = [f"**{title}**", ""]
    for name, g in df.groupby(key, observed=True):
        lines.append(f"- {name}: {_stats(g)}")
    return lines + [""]


def review(df: pd.DataFrame, day: str, since: str) -> str:
    out = [f"# Evening review: {day}", ""]
    if df.empty:
        return "\n".join(out + ["No closed paper trades yet."])

    today = df[df["date"] == day]
    out += ["## Today", ""]
    if today.empty:
        out += ["No trades closed today.", ""]
    else:
        out += [_stats(today), ""]
        for _, t in today.iterrows():
            out.append(f"- {t['symbol']} {t['contract']}: {t['status']} at {t['closed']}, "
                       f"₹{t['entry_ask']} -> ₹{t['exit_bid']}, net ₹{t['net_pnl']:,.0f} "
                       f"({t['net_pct']:+.2f}%), Claude said {t['claude_verdict'] or 'n/a'}")
        out.append("")

    out += ["## All paper trades so far", "", _stats(df),
            f"Worst trade {df['net_pct'].min():+.2f}%, best {df['net_pct'].max():+.2f}%", ""]

    reviewed = df[df["claude_verdict"].isin(["TRADE", "SKIP"])]
    if not reviewed.empty:
        out += ["## Rules only vs Claude-confirmed", "",
                f"- Rules only (every signal): {_stats(df)}"]
        for verdict, g in reviewed.groupby("claude_verdict"):
            label = "Claude said TRADE (taken)" if verdict == "TRADE" else "Claude said SKIP (avoided)"
            out.append(f"- {label}: {_stats(g)}")
        out.append("")

    out += ["## Where it wins and loses", ""]
    out += _breakdown(df, "By side", "side")
    out += _breakdown(df, "By entry hour", df["opened"].str[:2] + ":00")
    out += _breakdown(df, "By bid-ask gap", pd.cut(df["spread_pct"], [0, 0.5, 1, 100],
                                                   labels=["under 0.5%", "0.5-1%", "over 1%"]))
    out += _breakdown(df, "By forecast chance", pd.cut(df["hit_probability"], [0, 70, 85, 100],
                                                       labels=["under 70%", "70-85%", "over 85%"]))

    n_since = int((df["date"] > since).sum())
    out += ["## Ready to change the strategy?", ""]
    if n_since >= MIN_TRADES_FOR_PROPOSAL:
        out.append(f"READY: {n_since} trades since the last strategy change ({since}). "
                   "Look for a pattern above, test it, and propose it to the user.")
    else:
        out.append(f"NOT YET: {n_since} of {MIN_TRADES_FOR_PROPOSAL} trades since the last strategy change "
                   f"({since}). Too few to tell skill from luck, so no changes.")
    return "\n".join(out) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=date.today().isoformat())
    args = ap.parse_args()
    df = load()
    text = review(df, args.date, last_change_date())
    REVIEWS.mkdir(parents=True, exist_ok=True)
    (REVIEWS / f"{args.date}.md").write_text(text)
    if not df.empty:  # P&L as a fraction of capital, for QuantForge's metrics.py
        from agents.config import load_config
        capital = load_config()["capital"]
        df.assign(pnl=df["net_pnl"] / capital)[["date", "pnl"]].to_csv(REVIEWS / "pnl_for_metrics.csv", index=False)
    print(text)


if __name__ == "__main__":
    main()
