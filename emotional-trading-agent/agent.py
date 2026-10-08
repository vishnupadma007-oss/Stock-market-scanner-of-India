"""Arjun: an emotional trading agent who runs a desk of AI specialists, chasing 1% a day net of charges.

    python agent.py                               # one intraday cycle on paper (morning meeting + decisions)
    python agent.py --loop                        # run the whole trading day: desk checks every 15 min, square-off at 15:10
    python agent.py --mode swing RELIANCE TCS     # delivery trades instead of intraday
    python agent.py --boss claude --team grok     # Claude as the boss, Grok for the specialists
    python agent.py --live --loop                 # real orders via Zerodha (asks you once to confirm)
"""

import argparse
import datetime as dt
import json
import sys
import time
from pathlib import Path
from zoneinfo import ZoneInfo

import market_data
import risk
from broker import PaperBroker, ZerodhaBroker
from council import SPECIALISTS, arjun_decides, run_council, strategist_plan
from llm import make_llm
from persona import Emotions

IST = ZoneInfo("Asia/Kolkata")
DEFAULT_WATCHLIST = ["RELIANCE", "HDFCBANK", "ICICIBANK", "INFY", "TCS", "LT", "BHARTIARTL", "SBIN", "ITC", "SUNPHARMA"]
MARKET_OPEN, LAST_ENTRY, SQUARE_OFF, MARKET_CLOSE = dt.time(9, 15), dt.time(14, 45), dt.time(15, 10), dt.time(15, 30)


def now_ist():
    return dt.datetime.now(IST)


def market_open(t=None):
    t = t or now_ist()
    return t.weekday() < 5 and MARKET_OPEN <= t.time() <= MARKET_CLOSE  # NSE holidays not included


class Desk:
    def __init__(self, args):
        self.args = args
        self.mode = args.mode
        self.symbols = [s.upper().removesuffix(".NS") for s in (args.symbols or DEFAULT_WATCHLIST)]
        self.today = now_ist().date().isoformat()
        self.team = make_llm(args.team, args.team_model, web_search=not args.no_search)
        self.boss = (self.team if (args.boss or self.team.name) == self.team.name and not args.boss_model
                     else make_llm(args.boss or self.team.name, args.boss_model, web_search=not args.no_search))
        self.broker = ZerodhaBroker() if args.live else PaperBroker(args.capital)
        self.emotions = Emotions()
        if (self.emotions.s["updated"] or "")[:10] != self.today:
            self.emotions.new_day()
        self.day_path = Path(f"state/day_{self.today}_{self.mode}.json")
        self.day = json.loads(self.day_path.read_text()) if self.day_path.exists() else {}
        self.limits = risk.Limits(mode=self.mode, daily_target_pct=args.target)
        self.log = {"date": self.today, "mode": self.mode, "broker": self.broker.name, "symbols": self.symbols,
                    "boss": f"{self.boss.name}:{self.boss.model}", "team": f"{self.team.name}:{self.team.model}",
                    "cycles": []}

    def save_day(self):
        self.day_path.parent.mkdir(parents=True, exist_ok=True)
        self.day_path.write_text(json.dumps(self.day, indent=2, default=str))

    # ---- one look at the market -------------------------------------------------

    def refresh(self):
        held = self.broker.portfolio()["positions"]
        snap = market_data.snapshot(sorted(set(self.symbols) | set(held)), intraday=self.mode == "intraday")
        for sym, px in self.broker.ltp(list(snap)).items():  # live: the broker's price beats Yahoo's
            snap[sym]["last_price"] = px
        return snap

    def record_exits(self, closed, cycle):
        for sym, net, charges, reason in closed:
            self.emotions.on_trade_closed(net, self.limits.capital)
            cycle["exits"].append({"symbol": sym, "net": net, "charges": charges, "reason": reason})
            print(f"   {'✅' if net >= 0 else '❌'} {sym}: {reason}, net ₹{net:,.0f} (charges ₹{charges:,.0f})"
                  f"  → mood: {self.emotions.mood}")
        self.emotions.save()

    def cycle(self, desk_check):
        t = now_ist()
        cycle = {"time": t.strftime("%H:%M"), "exits": []}
        self.log["cycles"].append(cycle)
        print(f"\n{'─' * 70}\n⏱️  {t:%H:%M} IST {'desk check' if desk_check else 'morning session'}")
        snapshot = self.refresh()
        if not snapshot:
            print("   No market data this cycle.")
            return
        if "start_equity" not in self.day:
            self.day["start_equity"] = self.broker.equity(snapshot)
            self.save_day()
        self.limits.capital = self.day["start_equity"]

        self.record_exits(self.broker.check_exits(snapshot), cycle)
        realized = self.broker.realized_today()
        print(f"   💰 Today: ₹{realized:,.0f} net of ₹{self.limits.target_rupees:,.0f} target. Mood: {self.emotions.mood}")

        positions = self.broker.portfolio()["positions"]
        stale = any(p.get("product") == "MIS" and str(p.get("opened", ""))[:10] < self.today for p in positions.values())
        if self.mode == "intraday" and ((t.weekday() < 5 and t.time() >= SQUARE_OFF) or stale):
            self.record_exits(self.broker.square_off(snapshot), cycle)
            return
        portfolio = self.broker.portfolio()
        no_new_entries = self.mode == "intraday" and t.time() >= LAST_ENTRY and market_open(t)
        if desk_check and not portfolio["positions"] and (no_new_entries or realized >= self.limits.target_rupees):
            print("   Nothing to manage and no new entries allowed; skipping the desk check.")
            return

        # Morning meeting and plan: once a day, cached so a restart doesn't pay for it twice.
        quotes = {s: snapshot[s] for s in self.symbols if s in snapshot}
        if "council" not in self.day:
            council = run_council(self.team, self.symbols, quotes, self.today, self.mode, self.args.rounds)
            if not council:
                sys.exit("Every specialist failed; nothing to decide on.")
            self.day["council"] = council
            self.save_day()
        council = self.day["council"]
        money = risk.money_brief(self.limits, realized, snapshot, self.symbols)
        if "plan" not in self.day:
            print("\n📐 Strategist is writing the trading plan")
            self.day["plan"] = strategist_plan(self.team, self.today, self.mode, self.symbols, quotes, council,
                                               portfolio, money)
            self.save_day()
            plan = self.day["plan"]
            print(f"   Regime: {plan.get('regime', '')}")
            for s in plan.get("strategies", []):
                print(f"   ♟️  {s.get('name')}: {str(s.get('why', ''))[:140]}")
            print(f"   🎯 {str(plan.get('target_math', ''))[:300]}")
        cycle["plan_used"] = True

        print("\n🧍 Arjun is deciding...")
        decision = arjun_decides(self.boss, self.emotions, self.symbols, snapshot, council, self.day["plan"],
                                 portfolio, money, self.limits.describe(), self.today, self.mode,
                                 self.limits.daily_target_pct, desk_check=desk_check)
        cycle["decision"] = decision
        print(f"\n💭 Arjun: \"{decision.get('feeling', '')}\"")
        print(f"   Plan: {decision.get('plan_verdict', '')}. {str(decision.get('plan_comment', ''))[:200]}")
        for d in decision.get("decisions", []):
            if d.get("action") in ("SKIP", "HOLD"):
                continue
            levels = (f" entry {d.get('entry')} SL {d.get('stop_loss')} TGT {d.get('target')}"
                      if d.get("action") in ("BUY", "SHORT") else "")
            print(f"   • {d.get('action'):5} {d.get('symbol')}{levels} (conv {d.get('conviction')}): "
                  f"{str(d.get('rationale', ''))[:120]}")

        decisions = decision.get("decisions", [])
        if no_new_entries:
            decisions = [d for d in decisions if (d.get("action") or "").upper() not in ("BUY", "SHORT")]
        orders, rejected = risk.review(decisions, snapshot, portfolio, self.emotions, self.limits, realized)
        cycle["orders"], cycle["rejected"] = orders, rejected
        print("\n🛡️  Risk manager:")
        for r in rejected:
            print(f"   ✋ {r['action']} {r['symbol']}: {r['reason']}")
        for o in orders:
            extra = (f" @ ₹{o['entry']} SL {o['stop_loss']} TGT {o['target']}: win ₹{o['net_win']:,.0f} / lose "
                     f"₹{o['net_loss']:,.0f} net, charges ≈ ₹{o['charges_at_target']:,.0f} ({o['size_note']})"
                     if o["action"] != "EXIT" else "")
            print(f"   ✔️  {o['action']} {o['qty']} {o['symbol']}{extra}")
        cycle["executions"] = self.execute(orders, snapshot, cycle)
        if decision.get("journal"):
            self.emotions.add_journal(decision["journal"])
        self.emotions.save()

    def execute(self, orders, snapshot, cycle):
        msgs = []
        if orders and self.args.live and not market_open():
            print("   Market is closed; no live orders sent.")
            return msgs
        for o in orders:
            sym, last = o["symbol"], snapshot[o["symbol"]]["last_price"]
            try:
                if o["action"] == "EXIT":
                    net, charges = self.broker.close(sym, last, "Arjun exited: " + o["reason"][:100])
                    self.emotions.on_trade_closed(net, self.limits.capital)
                    cycle["exits"].append({"symbol": sym, "net": net, "charges": charges, "reason": "Arjun exited"})
                    msg = f"EXIT {sym} @ ₹{last}: net ₹{net:,.0f} (charges ₹{charges:,.0f})"
                elif self.args.live:
                    msg = self.broker.open(o, o["entry"])
                elif (o["side"] == "LONG" and last <= o["entry"]) or (o["side"] == "SHORT" and last >= o["entry"]):
                    msg = self.broker.open(o, last)  # a limit order at or through the market fills at the market
                else:
                    msg = f"paper {o['action']} {sym} not filled: last ₹{last} hasn't reached the ₹{o['entry']} limit"
            except Exception as e:
                msg = f"{o['action']} {sym} FAILED: {type(e).__name__}: {e}"
            msgs.append(msg)
            print(f"   📨 {msg}")
        return msgs

    # ---- the day -------------------------------------------------------------------

    def run(self):
        a = self.args
        print(f"📈 Arjun's desk, {self.today}. Mode: {self.mode}. Broker: {self.broker.name}. "
              f"Boss: {self.log['boss']}. Team: {len(SPECIALISTS)} specialists on {self.log['team']}.")
        print(f"   {self.emotions.mission_summary(self.limits.daily_target_pct)}")
        if not market_open() and not a.live:
            print("   ⚠️  The market is closed: paper fills will use the latest available prices.")
        if a.live and input("\n⚠️  LIVE: Arjun will place real-money orders through Zerodha today without asking "
                            "again. Type YES to allow: ").strip() != "YES":
            sys.exit("Not confirmed. Nothing was sent.")

        self.cycle(desk_check="council" in self.day and "plan" in self.day)
        while a.loop and self.mode == "intraday" and now_ist().time() < SQUARE_OFF and market_open():
            wake = now_ist() + dt.timedelta(minutes=a.interval)
            if wake.time() > SQUARE_OFF:
                wake = wake.replace(hour=SQUARE_OFF.hour, minute=SQUARE_OFF.minute, second=0)
            print(f"\n😴 Next desk check at {wake:%H:%M} IST (Ctrl+C to stop)")
            time.sleep(max((wake - now_ist()).total_seconds(), 0))
            self.cycle(desk_check=True)  # the last wake is at 15:10, which squares off
        self.finish()

    def finish(self):
        positions = self.broker.portfolio()["positions"]
        mis_open = any(p.get("product") == "MIS" for p in positions.values())
        day_over = self.mode == "swing" or (not mis_open and (now_ist().time() >= SQUARE_OFF or not market_open()))
        realized = self.broker.realized_today()
        if day_over and self.day.get("start_equity") and not self.day.get("verdict"):
            pct, hit = self.emotions.on_day_end(self.today, self.day["start_equity"], realized,
                                                self.limits.daily_target_pct)
            self.day["verdict"] = {"net": realized, "pct": pct, "hit": hit}
            self.save_day()
            self.emotions.save()
            print(f"\n🏁 Day {'WON' if hit else 'not won'}: {pct:+.2f}% net (target {self.limits.daily_target_pct}%).")
        self.log["day"] = {"start_equity": self.day.get("start_equity"), "realized_net": realized,
                           "verdict": self.day.get("verdict"), "open_positions": positions,
                           "mission": self.emotions.mission_summary(self.limits.daily_target_pct)}
        self.log["council"], self.log["plan"] = self.day.get("council"), self.day.get("plan")
        self.log["emotions_after"] = {k: v for k, v in self.emotions.s.items() if k not in ("journal", "days")}
        path = write_report(self.log, self.emotions)
        print(f"\n📄 Report: {path}\n   Mood: {self.emotions.mood}. {self.log['day']['mission']}")


def write_report(log, emotions):
    day, plan, council = log["day"], log.get("plan") or {}, log.get("council") or {}
    lines = [f"# Arjun's desk, {log['date']} ({log['mode']})", "",
             f"Broker: {log['broker']}. Boss: {log['boss']}. Team: {log['team']}.", "",
             f"**Net P&L today: ₹{day['realized_net']:,.0f}** on start-of-day equity ₹{day['start_equity'] or 0:,.0f}. "
             + (f"Verdict: {day['verdict']['pct']:+.2f}% ({'target hit' if day['verdict']['hit'] else 'target missed'})."
                if day.get("verdict") else "Day still open."), "",
             f"{day['mission']}", "", f"Mood after the session: **{emotions.mood}**.", ""]
    agenda = council.get("agenda") or {}
    if agenda:
        lines += ["## Morning agenda", ""] + [f"- 📰 {h}" for h in agenda.get("headlines", [])]
        lines += [f"- ❓ {q}" for q in agenda.get("agenda", [])] + [""]
    minutes = council.get("minutes") or {}
    if minutes:
        lines += ["## Council minutes", "", minutes.get("market_read", ""), "",
                  "| Stock | Consensus | Strength | For | Against | Dissent |", "|---|---|---|---|---|---|"]
        for sym, m in (minutes.get("per_symbol") or {}).items():
            cell = lambda x: str(x).replace("|", "/").replace("\n", " ")
            lines.append(f"| {sym} | {m.get('consensus')} | {m.get('strength')} | {cell(m.get('for', ''))} | "
                         f"{cell(m.get('against', ''))} | {cell(', '.join(m.get('dissenters') or []))} |")
        lines.append("")
    if plan:
        lines += ["## Strategist's plan", "", f"**Regime:** {plan.get('regime', '')}", ""]
        lines += [f"- **{s.get('name')}**: {s.get('why')}" for s in plan.get("strategies", [])]
        lines += ["", f"**Target math:** {plan.get('target_math', '')}", ""]
        for t in plan.get("trades", []):
            lines.append(f"- {t.get('direction')} {t.get('symbol')} ({t.get('strategy')}): entry {t.get('entry')}, "
                         f"SL {t.get('stop_loss')}, TGT {t.get('target')}. Trigger: {t.get('trigger')}. {t.get('why')}")
        lines += [f"- Avoid: {x}" for x in plan.get("avoid", [])] + [f"- Rule: {x}" for x in plan.get("rules_for_today", [])]
        lines.append("")
    for c in log["cycles"]:
        d = c.get("decision") or {}
        lines += [f"## {c['time']} IST", ""]
        if d:
            lines += [f"> {d.get('feeling', '')}", "", f"Plan verdict: {d.get('plan_verdict')}. {d.get('plan_comment', '')}", ""]
            for x in d.get("decisions", []):
                lines.append(f"- {x.get('action')} {x.get('symbol')}"
                             + (f" entry {x.get('entry')} SL {x.get('stop_loss')} TGT {x.get('target')}"
                                if x.get("action") in ("BUY", "SHORT") else "")
                             + f": {x.get('rationale', '')}")
        lines += [f"- ✋ Vetoed {r['action']} {r['symbol']}: {r['reason']}" for r in c.get("rejected", [])]
        lines += [f"- 📨 {m}" for m in c.get("executions", [])]
        lines += [f"- {'✅' if e['net'] >= 0 else '❌'} {e['symbol']} {e['reason']}: net ₹{e['net']:,.0f} "
                  f"(charges ₹{e['charges']:,.0f})" for e in c["exits"]]
        if d.get("journal"):
            lines += ["", f"*Journal:* {d['journal']}"]
        lines.append("")
    views = council.get("views") or {}
    if views:
        lines += ["## Specialists' final views", ""]
        for name, v in views.items():
            lines += [f"### {name}", "", v.get("summary", ""), ""]
            for sym, view in (v.get("views") or {}).items():
                lines.append(f"- **{sym}**: {view.get('stance')} ({view.get('conviction')}/5). {view.get('reason', '')}")
            if v.get("changed_mind"):
                lines.append(f"- *Changed mind:* {v['changed_mind']}")
            lines.append("")
    lines += ["---", "*Generated by an AI agent. Not investment advice.*"]

    out = Path("output")
    out.mkdir(exist_ok=True)
    stamp = now_ist().strftime("%Y-%m-%d_%H%M")
    (out / f"session_{stamp}.json").write_text(json.dumps(log, indent=2, default=str))
    path = out / f"session_{stamp}.md"
    path.write_text("\n".join(lines))
    return path


def main():
    ap = argparse.ArgumentParser(description="Arjun: an emotional trading agent with a desk of AI specialists")
    ap.add_argument("symbols", nargs="*", help="NSE symbols (default: a large-cap watchlist)")
    ap.add_argument("--mode", choices=["intraday", "swing"], default="intraday")
    ap.add_argument("--target", type=float, default=1.0, help="Daily net target, %% of start-of-day equity")
    ap.add_argument("--capital", type=float, default=100_000, help="Starting paper capital (₹)")
    ap.add_argument("--loop", action="store_true", help="Run the whole intraday session until square-off")
    ap.add_argument("--interval", type=int, default=15, help="Minutes between desk checks with --loop")
    ap.add_argument("--rounds", type=int, default=2, help="Council rounds (1 = no debate)")
    ap.add_argument("--boss", choices=["grok", "claude"], help="Model provider for Arjun (default: same as team)")
    ap.add_argument("--team", choices=["grok", "claude"], help="Provider for specialists, moderator and strategist")
    ap.add_argument("--boss-model", help="Model ID for Arjun")
    ap.add_argument("--team-model", help="Model ID for the team")
    ap.add_argument("--no-search", action="store_true", help="Agents don't use live web search")
    ap.add_argument("--live", action="store_true", help="Trade real money through Zerodha Kite Connect")
    Desk(ap.parse_args()).run()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped. Open positions stay open; run again to manage them.")
