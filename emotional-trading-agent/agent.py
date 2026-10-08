"""Arjun: an emotional trading agent with a research council.

    python agent.py                                # paper-trade the default watchlist
    python agent.py RELIANCE TCS HDFCBANK          # pick the stocks
    python agent.py --live                         # real orders via Zerodha (asks you first)

One run = one trading session: check stops and targets, convene the council, let Arjun decide,
run every decision through the risk manager, place orders, and write the day's report.
"""

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

import openai

import market_data
import risk
from broker import PaperBroker, ZerodhaBroker
from council import arjun_decides, run_council
from llm import LLM
from persona import Emotions

DEFAULT_WATCHLIST = ["RELIANCE", "HDFCBANK", "ICICIBANK", "INFY", "TCS", "LT", "BHARTIARTL", "SBIN", "ITC", "SUNPHARMA"]


def main():
    ap = argparse.ArgumentParser(description="Arjun, an emotional trading agent with a research council")
    ap.add_argument("symbols", nargs="*", help="NSE symbols to review (default: a large-cap watchlist)")
    ap.add_argument("--capital", type=float, default=100_000, help="Capital the risk manager sizes against (₹)")
    ap.add_argument("--live", action="store_true", help="Trade real money through Zerodha Kite Connect")
    ap.add_argument("--rounds", type=int, default=2, help="Council rounds (1 = no debate)")
    ap.add_argument("--model", help="Grok model ID (default: GROK_MODEL or grok-4.3)")
    ap.add_argument("--no-search", action="store_true", help="Analysts don't use live web search")
    args = ap.parse_args()

    symbols = [s.upper().removesuffix(".NS") for s in (args.symbols or DEFAULT_WATCHLIST)]
    today = dt.date.today().isoformat()
    limits = risk.Limits(capital=args.capital)
    llm = LLM(args.model, web_search=not args.no_search)
    broker = ZerodhaBroker() if args.live else PaperBroker(args.capital)
    emotions = Emotions()
    if (emotions.s["updated"] or "")[:10] != today:
        emotions.new_day()
    log = {"date": today, "broker": broker.name, "symbols": symbols}

    print(f"📈 Arjun's desk, {today}. Broker: {broker.name}. Mood: {emotions.mood}.")

    # 1. Market data, including anything already held.
    portfolio = broker.portfolio()
    print("\n📊 Fetching prices...")
    snapshot = market_data.snapshot(sorted(set(symbols) | set(portfolio["positions"])))
    if not snapshot:
        sys.exit("No market data; check your internet connection or the symbols.")

    # 2. Stops and targets that were hit since the last run, and how they make him feel.
    log["exits"] = []
    for sym, pnl, reason in broker.check_exits(snapshot):
        emotions.on_trade_closed(pnl, args.capital)
        log["exits"].append({"symbol": sym, "pnl": pnl, "reason": reason})
        print(f"   {'✅' if pnl >= 0 else '❌'} {sym} closed: {reason}, P&L ₹{pnl:,.0f}  → mood now: {emotions.mood}")
    emotions.save()
    portfolio = broker.portfolio()

    # 3. The council meets.
    views = run_council(llm, symbols, {s: snapshot[s] for s in symbols if s in snapshot}, today, args.rounds)
    if not views:
        sys.exit("Every analyst failed; nothing to decide on.")
    log["council"] = views

    # 4. Arjun decides.
    print("\n🧍 Arjun is deciding...")
    decision = arjun_decides(llm, emotions, symbols, snapshot, views, portfolio, limits.describe(), today)
    log["decision"] = decision
    print(f"\n💭 Arjun: \"{decision.get('feeling', '')}\"")
    print(f"\n🌏 View: {decision.get('market_view', '')}")
    for d in decision.get("decisions", []):
        levels = f" entry {d.get('entry')} SL {d.get('stop_loss')} TGT {d.get('target')}" if d.get("action") == "BUY" else ""
        print(f"   • {d.get('action', '?'):4} {d.get('symbol')}{levels} (conviction {d.get('conviction')}): {d.get('rationale', '')[:140]}")

    # 5. Risk manager.
    orders, rejected = risk.review(decision.get("decisions", []), snapshot, portfolio, emotions, limits,
                                   broker.realized_today())
    log["orders"], log["rejected"] = orders, rejected
    print("\n🛡️  Risk manager:")
    for r in rejected:
        print(f"   ✋ {r['action']} {r['symbol']} vetoed: {r['reason']}")
    for o in orders:
        extra = f" @ ₹{o['entry']} SL {o['stop_loss']} TGT {o['target']}, risking ₹{o['risk_rupees']:,.0f} ({o['size_note']})" if o["side"] == "BUY" else ""
        print(f"   ✔️  {o['side']} {o['qty']} {o['symbol']}{extra}")

    # 6. Execute. Real money always needs a human yes.
    log["executions"] = []
    if orders and args.live:
        if input("\n⚠️  Send these orders to Zerodha with REAL money? Type YES to confirm: ").strip() != "YES":
            print("Not sent.")
            orders = []
    for o in orders:
        last = snapshot[o["symbol"]]["last_price"]
        try:
            if o["side"] == "SELL":
                pnl = broker.sell(o["symbol"], last, "Arjun exited: " + o["reason"][:100])
                emotions.on_trade_closed(pnl, args.capital)
                msg = f"SELL {o['qty']} {o['symbol']} @ ₹{last}, P&L ₹{pnl:,.0f}"
            elif args.live:
                msg = broker.buy(o, o["entry"])
            elif last <= o["entry"]:
                msg = broker.buy(o, last)  # A limit buy at or above the market fills at the market.
            else:
                msg = f"paper BUY {o['symbol']} not filled: last ₹{last} is above the ₹{o['entry']} limit"
        except Exception as e:
            msg = f"{o['side']} {o['symbol']} FAILED: {type(e).__name__}: {e}"
        log["executions"].append(msg)
        print(f"   📨 {msg}")

    # 7. Journal and report.
    if decision.get("journal"):
        emotions.add_journal(decision["journal"])
    emotions.save()
    log["emotions_after"] = {k: v for k, v in emotions.s.items() if k != "journal"}
    path = write_report(log, emotions)
    print(f"\n📓 Journal: {decision.get('journal', '')}\n📄 Report: {path}\n   Mood now: {emotions.mood}")


def write_report(log, emotions):
    d = log["decision"]
    lines = [f"# Arjun's trading session, {log['date']}", "",
             f"Broker: {log['broker']}. Mood after the session: **{emotions.mood}**.", "",
             "## How Arjun feels", "", f"> {d.get('feeling', '')}", "",
             "## Market view", "", d.get("market_view", ""), ""]
    if log["exits"]:
        lines += ["## Positions closed since last run", ""]
        lines += [f"- {e['symbol']}: {e['reason']}, P&L ₹{e['pnl']:,.0f}" for e in log["exits"]] + [""]
    lines += ["## Decisions", "", "| Action | Symbol | Entry | Stop | Target | Conviction | Why |", "|---|---|---|---|---|---|---|"]
    for x in d.get("decisions", []):
        why = str(x.get("rationale", "")).replace("|", "/").replace("\n", " ")
        lines.append(f"| {x.get('action')} | {x.get('symbol')} | {x.get('entry', '')} | {x.get('stop_loss', '')} "
                     f"| {x.get('target', '')} | {x.get('conviction', '')} | {why} |")
    lines += ["", "## Risk manager", ""]
    lines += [f"- Vetoed {r['action']} {r['symbol']}: {r['reason']}" for r in log["rejected"]] or ["- No vetoes"]
    lines += ["", "## Executions", ""] + ([f"- {m}" for m in log["executions"]] or ["- None"])
    lines += ["", "## Council", ""]
    for name, v in log["council"].items():
        lines += [f"### {name}", "", v.get("summary", ""), ""]
        for sym, view in (v.get("views") or {}).items():
            lines.append(f"- **{sym}**: {view.get('stance')} ({view.get('conviction')}/5). {view.get('reason', '')}")
        if v.get("changed_mind"):
            lines.append(f"- *Changed mind:* {v['changed_mind']}")
        if v.get("key_risks"):
            lines.append(f"- *Risks:* {'; '.join(map(str, v['key_risks']))}")
        lines.append("")
    lines += ["## Journal", "", d.get("journal", ""), "", "---",
              "*Generated by an AI agent. Not investment advice.*"]

    out = Path("output")
    out.mkdir(exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y-%m-%d_%H%M")
    (out / f"session_{stamp}.json").write_text(json.dumps(log, indent=2, default=str))
    path = out / f"session_{stamp}.md"
    path.write_text("\n".join(lines))
    return path


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print()
    except openai.APIConnectionError as e:
        sys.exit(f"Could not reach the xAI API: {e}")
