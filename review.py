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

import numpy as np
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
    if "strategy" not in df:  # logs from before the strategy column: all scanner (movers) trades
        df["strategy"] = ""
    for col in NUMERIC:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    closed = df[df["status"].isin(["TARGET", "SQUARED_OFF"])].copy()
    cost = (closed["entry_ask"] * closed["qty"]).replace(0.0, np.nan)
    closed["net_pct"] = (closed["net_pnl"] / cost * 100.0).fillna(0.0)
    closed["hit"] = closed["status"] == "TARGET"
    # Claude's TRADE/SKIP calls are kept in their own file (the watcher rewrites the trade log).
    verdicts = path.parent / "claude_verdicts.csv"
    if verdicts.exists() and not closed.empty:
        v = pd.read_csv(verdicts, dtype=str).drop_duplicates(["date", "contract"], keep="last")
        closed = closed.merge(v[["date", "contract", "verdict"]], on=["date", "contract"], how="left")
        closed["claude_verdict"] = closed["verdict"].fillna(closed["claude_verdict"]).fillna("")
        closed = closed.drop(columns="verdict")
    return closed


def last_change_date(path: Path = CHANGES) -> str:
    if not path.exists():
        return "0000-00-00"
    try:
        dates = re.findall(r"^\|\s*(\d{4}-\d{2}-\d{2})", path.read_text(encoding="utf-8"), re.M)
        return max(dates) if dates else "0000-00-00"
    except Exception:
        return "0000-00-00"


def _stats(g: pd.DataFrame) -> str:
    if g.empty:
        return "0 trades"
    return (f"{len(g)} trades, {g['hit'].mean() * 100:.0f}% hit target, "
            f"avg {g['net_pct'].mean():+.2f}% of premium, net ₹{g['net_pnl'].sum():,.0f}")


def _risk_summary(df: pd.DataFrame) -> str:
    """Institutional risk & payoff asymmetry metrics: Profit Factor, Win/Loss Payoff,
    Required Breakeven Hit Rate, and Max Drawdown."""
    if df.empty:
        return ""
    pnl = df["net_pnl"].fillna(0.0)
    wins = pnl[pnl > 0]
    losses = pnl[pnl < 0]
    gross_win = float(wins.sum()) if len(wins) else 0.0
    gross_loss = abs(float(losses.sum())) if len(losses) else 0.0
    pf = f"{gross_win / gross_loss:.2f}" if gross_loss > 0 else "∞"
    avg_win = float(wins.mean()) if len(wins) else 0.0
    avg_loss = abs(float(losses.mean())) if len(losses) else 0.0
    be_hit = f"{avg_loss / (avg_win + avg_loss) * 100:.1f}%" if (avg_win + avg_loss) > 0 else "n/a"
    cum = pnl.cumsum()
    peak = np.maximum.accumulate(np.r_[0.0, cum.to_numpy()])[1:]
    max_dd = float((cum - peak).min()) if len(cum) else 0.0
    return (f"Profit factor {pf}, avg win ₹{avg_win:,.0f} vs avg loss ₹-{avg_loss:,.0f} "
            f"(break-even hit rate {be_hit}), max drawdown ₹{max_dd:,.0f}")


def _breakdown(df: pd.DataFrame, title: str, key) -> list[str]:
    lines = [f"**{title}**", ""]
    for name, g in df.groupby(key, observed=True):
        lines.append(f"- {name}: {_stats(g)}")
    return lines + [""]


NEWS_STRATEGIES = ("results", "intel", "news", "results-gap", "preopen", "spurt", "quiet-spurt", "quiet-spurt-news")


def team_of(strategy: pd.Series) -> pd.Series:
    return strategy.isin(NEWS_STRATEGIES).map({True: "news", False: "movers"})


def scoreboard(df: pd.DataFrame, day: str, capitals: dict, chances: dict) -> list[str]:
    """Movers team vs news team: chances found, trades, hit rate, money made, return on own capital."""
    out = ["## Team scoreboard: movers vs news", "",
           "| Team | Chances today | Trades today | Net today | Trades so far | Hit target | Avg per trade | Net so far | Return on capital |",
           "|---|---|---|---|---|---|---|---|---|"]
    teams = team_of(df["strategy"]) if not df.empty and "strategy" in df else pd.Series(dtype=str)
    for team, capital in capitals.items():
        g = df[teams == team] if not df.empty and not teams.empty else df
        t = g[g["date"] == day] if not g.empty and "date" in g else g
        if g.empty:
            out.append(f"| {team} | {chances.get(team, 0)} | 0 | ₹0 | 0 | - | - | ₹0 | 0.0% |")
            continue
        out.append(f"| {team} | {chances.get(team, 0)} | {len(t)} | ₹{t['net_pnl'].sum():,.0f} | {len(g)} | "
                   f"{g['hit'].mean() * 100:.0f}% | {g['net_pct'].mean():+.2f}% | ₹{g['net_pnl'].sum():,.0f} | "
                   f"{g['net_pnl'].sum() / capital * 100:+.1f}% |")
    return out + ["", "Chances = setups that passed the team's checks (movers: trades + setups held while busy; "
                      "news: new results/forecast ideas). Judge a winner only after 30+ trades per team.", ""]


def review(df: pd.DataFrame, day: str, since: str, capitals: dict | None = None,
           chances: dict | None = None) -> str:
    out = [f"# Evening review: {day}", ""]
    if capitals:
        out += scoreboard(df, day, capitals, chances or {})
    if df.empty:
        return "\n".join(out + ["No closed paper trades yet."])

    today = df[df["date"] == day] if "date" in df else pd.DataFrame()
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
            f"Worst trade {df['net_pct'].min():+.2f}%, best {df['net_pct'].max():+.2f}%",
            _risk_summary(df), ""]

    reviewed = df[df["claude_verdict"].isin(["TRADE", "SKIP"])]
    if not reviewed.empty:
        out += ["## Rules only vs Claude-confirmed", "",
                f"- Rules only (every signal): {_stats(df)}"]
        for verdict, g in reviewed.groupby("claude_verdict"):
            label = "Claude said TRADE (taken)" if verdict == "TRADE" else "Claude said SKIP (avoided)"
            out.append(f"- {label}: {_stats(g)}")
        out.append("")

    out += ["## Where it wins and loses", ""]
    if "strategy" in df and df["strategy"].ne("").any():
        out += _breakdown(df, "By team", team_of(df["strategy"]))
        out += _breakdown(df, "By strategy", df["strategy"].replace("", "reversal"))
    out += _breakdown(df, "By side", "side")
    out += _breakdown(df, "By entry hour", df["opened"].str[:2] + ":00")
    out += _breakdown(df, "By bid-ask gap", pd.cut(df["spread_pct"], [0, 0.5, 1, 100],
                                                   labels=["under 0.5%", "0.5-1%", "over 1%"]))
    if "oi_type" in df and df["oi_type"].ne("").any():
        out += _breakdown(df, "By crowd positioning (futures OI)", df["oi_type"].replace("", "not recorded"))
    out += _breakdown(df, "By forecast chance", pd.cut(df["hit_probability"], [0, 70, 85, 100],
                                                       labels=["under 70%", "70-85%", "over 85%"]))

    n_since = int((df["date"] > since).sum()) if "date" in df else 0
    out += ["## Ready to change the strategy?", ""]
    if n_since >= MIN_TRADES_FOR_PROPOSAL:
        out.append(f"READY: {n_since} trades since the last strategy change ({since}). "
                   "Look for a pattern above, test it, and propose it to the user.")
    else:
        out.append(f"NOT YET: {n_since} of {MIN_TRADES_FOR_PROPOSAL} trades since the last strategy change "
                   f"({since}). Too few to tell skill from luck, so no changes.")
    return "\n".join(out) + "\n"


def grok_scorecard(df: pd.DataFrame) -> str:
    """Grok's observe-only TRADE/SKIP views (journal/grok_verdicts.csv) against how the trades ended:
    it earns a say in trade decisions only if its SKIPs lose and its TRADEs win more than the rest."""
    path = ROOT / "journal" / "grok_verdicts.csv"
    if not path.exists() or df.empty:
        return ""
    v = pd.read_csv(path, dtype=str).fillna("")
    m = v.merge(df[["date", "contract", "net_pnl", "net_pct"]], on=["date", "contract"], how="inner")
    if m.empty:
        return ""
    lines = [f"\n## Grok's views (observe only): {len(m)} closed trades\n"]
    for verdict, g in m.groupby("verdict"):
        lines.append(f"- {verdict or 'no view'}: {len(g)} trades, avg {g['net_pct'].mean():+.2f}% of premium, "
                     f"net ₹{g['net_pnl'].sum():,.0f}")
    lines.append("\nGrok helps only if its SKIP trades did clearly worse than its TRADE trades.\n")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=date.today().isoformat())
    args = ap.parse_args()
    from agents.config import load_config
    cfg = load_config()
    df = load()
    held_path = ROOT / "journal" / "held_setups.csv"
    held = pd.read_csv(held_path, dtype=str) if held_path.exists() else pd.DataFrame(columns=["date"])
    held = held[held["date"] == args.date] if "date" in held.columns else held
    ideas_path = ROOT / "journal" / "news_ideas.csv"
    ideas = pd.read_csv(ideas_path, dtype=str) if ideas_path.exists() else pd.DataFrame(columns=["date"])
    opened = pd.read_csv(TRADES, dtype=str).fillna("") if TRADES.exists() else pd.DataFrame(columns=["date"])
    opened = opened[opened["date"] == args.date] if "date" in opened.columns else opened
    opened_teams = team_of(opened["strategy"]) if "strategy" in opened else pd.Series("movers", index=opened.index)
    chances = {"movers": int((opened_teams == "movers").sum()) + len(held),
               "news": int((ideas["date"] == args.date).sum()) if "date" in ideas.columns else 0}
    capitals = {team: (cfg.get("teams") or {}).get(team, {}).get("capital", cfg["capital"]) for team in ("movers", "news")}
    text = review(df, args.date, last_change_date(), capitals, chances)
    guard_path = ROOT / "journal" / "news_guard.csv"
    if guard_path.exists():
        guard = pd.read_csv(guard_path, dtype=str)
        guard = guard[guard["date"] == args.date]
        if not guard.empty:
            text += (f"\n## Movers setups stopped by the News Guard: {len(guard)}\n\n"
                     + "\n".join(f"- {r.time} {r.symbol} ({r.side}, chart {r.chart_score}): {r.reason}"
                                  for r in guard.itertuples())
                     + "\n\nCheck how each stock moved afterwards: did the guard save a loss or cost a win?\n")
    if not held.empty:
        text += (f"\n## Setups held while a trade was open: {len(held)}\n\n"
                 + "\n".join(f"- {r.time} {r.symbol} {r.contract} (score {r.score})" for r in held.itertuples())
                 + "\n")
    text += grok_scorecard(df)
    REVIEWS.mkdir(parents=True, exist_ok=True)
    (REVIEWS / f"{args.date}.md").write_text(text, encoding="utf-8")
    if not df.empty and "strategy" in df:
        teams = team_of(df["strategy"])
        for team, capital in capitals.items():
            g = df[teams == team]
            if not g.empty:
                g.assign(pnl=g["net_pnl"] / capital)[["date", "pnl"]].to_csv(REVIEWS / f"pnl_for_metrics_{team}.csv",
                                                                             index=False)
    print(text)


if __name__ == "__main__":
    main()
