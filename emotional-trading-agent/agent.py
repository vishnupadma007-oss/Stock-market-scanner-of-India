"""Arjun: an emotional trading agent who runs a desk of AI specialists, chasing 1% a day net of charges.

    python agent.py                        # one look: meeting + decisions now, no monitoring
    python agent.py --session              # today's session: watch every tick from 9:15 to 15:10
    python agent.py --autopilot            # around the clock: news every 10 min, 8:00 meeting, trading session
    python agent.py --autopilot --live     # the same with real orders through Zerodha

How the work is split:
  code (free, every few seconds)   prices, armed entries, stops, targets, trailing stops, square-off
  watcher AI (cheap, every 10 min) news, day and night
  team + Arjun (expensive)         the 8:00 meeting, then only when something happens: a sharp move,
                                   important news, or a periodic review. A daily AI budget caps the spend.
"""

import argparse
import datetime as dt
import json
import sys
import time
from pathlib import Path
from zoneinfo import ZoneInfo

import market_data
import news
import risk
from broker import PaperBroker, ZerodhaBroker
from council import SPECIALISTS, arjun_decides, run_council, strategist_plan
from feed import BrokerFeed, YahooFeed
from llm import Budget, BudgetExceeded, make_llm
from persona import Emotions
from reflex import Reflex

IST = ZoneInfo("Asia/Kolkata")
DEFAULT_WATCHLIST = ["RELIANCE", "HDFCBANK", "ICICIBANK", "INFY", "TCS", "LT", "BHARTIARTL", "SBIN", "ITC", "SUNPHARMA"]
MORNING_MEETING = dt.time(8, 0)
MARKET_OPEN, FIRST_ENTRY, LAST_ENTRY = dt.time(9, 15), dt.time(9, 20), dt.time(14, 45)
SQUARE_OFF, MARKET_CLOSE = dt.time(15, 10), dt.time(15, 30)
HOLIDAYS_FILE = Path("holidays.txt")  # optional: one YYYY-MM-DD per line (NSE trading holidays)


def now_ist():
    return dt.datetime.now(IST)


def holidays():
    if not HOLIDAYS_FILE.exists():
        return set()
    return {line.strip() for line in HOLIDAYS_FILE.read_text().splitlines() if line.strip()[:1].isdigit()}


def trading_day(d):
    return d.weekday() < 5 and d.isoformat() not in holidays()


def market_open(t=None):
    t = t or now_ist()
    return trading_day(t.date()) and MARKET_OPEN <= t.time() <= MARKET_CLOSE


def last_close(t):
    """When the previous trading session ended (for "news since the last close")."""
    d = t.date() - dt.timedelta(days=1)
    for _ in range(7):
        if trading_day(d):
            break
        d -= dt.timedelta(days=1)
    return dt.datetime.combine(d, MARKET_CLOSE, IST)


class Desk:
    def __init__(self, args):
        self.args = args
        self.mode = args.mode
        self.symbols = [s.upper().removesuffix(".NS") for s in (args.symbols or DEFAULT_WATCHLIST)]
        ws = not args.no_search
        self.budget = Budget(args.daily_budget)
        self.team = make_llm(args.team, args.team_model, ws, self.budget)
        same_boss = (args.boss or self.team.name) == self.team.name and not args.boss_model
        self.boss = self.team if same_boss else make_llm(args.boss or self.team.name, args.boss_model, ws, self.budget)
        self.watcher = make_llm(args.watch or self.team.name, args.watch_model, ws, self.budget, tier="watcher")
        self.broker = ZerodhaBroker() if args.live else PaperBroker(args.capital)
        self.feed = BrokerFeed(self.broker) if args.live else YahooFeed()
        self.tick_seconds = args.tick or self.feed.default_tick
        self.emotions = Emotions()
        self.reflex = Reflex(shock_pct=args.shock)
        self.limits = risk.Limits(mode=self.mode, daily_target_pct=args.target)
        self._snap, self._snap_time = {}, None
        self.open_day(now_ist().date())

    # ---- day bookkeeping ------------------------------------------------------------

    def open_day(self, date):
        self.today = date.isoformat()
        self._budget_notes = set()
        if (self.emotions.s["updated"] or "")[:10] != self.today:
            self.emotions.new_day()
            self.emotions.save()
        self.day_path = Path(f"state/day_{self.today}_{self.mode}.json")
        self.day = json.loads(self.day_path.read_text()) if self.day_path.exists() else {}
        self.reflex.arm(self.day.get("armed", []))
        self.log = {"date": self.today, "mode": self.mode, "broker": self.broker.name, "symbols": self.symbols,
                    "boss": f"{self.boss.name}:{self.boss.model}", "team": f"{self.team.name}:{self.team.model}",
                    "watcher": f"{self.watcher.name}:{self.watcher.model}", "cycles": [], "events": []}

    def save_day(self):
        self.day["armed"] = self.reflex.armed
        self.day_path.parent.mkdir(parents=True, exist_ok=True)
        self.day_path.write_text(json.dumps(self.day, indent=2, default=str))

    def event(self, text):
        line = f"{now_ist():%H:%M:%S} {text}"
        self.log["events"].append(line)
        print(f"   {line}")

    # ---- prices -----------------------------------------------------------------------

    def watch_symbols(self, positions=None):
        if positions is None:
            positions = self.broker.portfolio()["positions"]
        return sorted(set(self.symbols) | set(positions))

    def full_snapshot(self, max_age_min=5):
        """Indicators for the AI (slow: a few seconds per stock), cached for a few minutes."""
        t = now_ist()
        if not self._snap or not self._snap_time or t - self._snap_time > dt.timedelta(minutes=max_age_min):
            self._snap = market_data.snapshot(self.watch_symbols(), intraday=self.mode == "intraday")
            self._snap_time = t
        for sym, px in self.broker.ltp(list(self._snap)).items():  # live: the broker's price beats Yahoo's
            self._snap[sym]["last_price"] = px
        return self._snap

    def ensure_equity(self, snapshot=None):
        if "start_equity" not in self.day:
            self.day["start_equity"] = self.broker.equity(snapshot if snapshot is not None else self.full_snapshot())
            self.save_day()
        self.limits.capital = self.day["start_equity"]

    # ---- thinking (AI) ------------------------------------------------------------------

    def morning_meeting(self):
        """Council and plan, once a day (cached, so a restart doesn't pay twice), then Arjun's call."""
        snapshot = self.full_snapshot(max_age_min=0)
        if not snapshot:
            print("   No market data; meeting postponed.")
            return False
        self.ensure_equity(snapshot)
        quotes = {s: snapshot[s] for s in self.symbols if s in snapshot}
        overnight = news.since(last_close(now_ist()))
        portfolio = self.broker.portfolio()
        money = risk.money_brief(self.limits, self.broker.realized_today(), snapshot, self.symbols)
        if "council" not in self.day:
            council = run_council(self.team, self.symbols, quotes, self.today, self.mode, self.args.rounds, overnight)
            if not council:
                print("   Every specialist failed; meeting postponed.")
                return False
            self.day["council"] = council
            self.save_day()
        if "plan" not in self.day:
            print("\n📐 Strategist is writing the trading plan")
            self.day["plan"] = strategist_plan(self.team, self.today, self.mode, self.symbols, quotes,
                                               self.day["council"], portfolio, money)
            self.save_day()
            plan = self.day["plan"]
            print(f"   Regime: {plan.get('regime', '')}")
            for s in plan.get("strategies", []):
                print(f"   ♟️  {s.get('name')}: {str(s.get('why', ''))[:140]}")
            print(f"   🎯 {str(plan.get('target_math', ''))[:300]}")
        if "morning_decision" not in self.day:
            self.decide("morning meeting: set today's trades and armed setups", role="morning")
            self.day["morning_decision"] = now_ist().isoformat(timespec="seconds")
            self.save_day()
        return True

    def decide(self, reason, role="intraday", prices=None):
        snapshot = dict(self.full_snapshot())
        for sym, px in (prices or {}).items():
            if sym in snapshot:
                snapshot[sym] = {**snapshot[sym], "last_price": px}
        self.ensure_equity(snapshot)
        realized = self.broker.realized_today()
        portfolio = self.broker.portfolio()
        money = risk.money_brief(self.limits, realized, snapshot, self.symbols)
        meeting = self.day.get("morning_decision") or now_ist().isoformat(timespec="seconds")
        fresh_news = [n for n in news.since(dt.datetime.fromisoformat(meeting)) if (n.get("materiality") or 0) >= 3]
        print(f"\n🧍 Arjun is thinking ({reason})...")
        decision = arjun_decides(self.boss, self.emotions, self.symbols, snapshot, self.day["council"],
                                 self.day["plan"], portfolio, money, self.limits.describe(), self.today, self.mode,
                                 self.limits.daily_target_pct, reason=reason, armed=self.reflex.armed,
                                 news=fresh_news[-15:], role=role)
        cycle = {"time": now_ist().strftime("%H:%M"), "reason": reason, "decision": decision, "exits": []}
        self.log["cycles"].append(cycle)
        print(f"💭 Arjun: \"{decision.get('feeling', '')}\"")

        now_t = now_ist()
        act_now = market_open(now_t) or (not self.args.live and not self.args.autopilot)
        immediate, armed = [], []
        for d in decision.get("decisions", []):
            action = (d.get("action") or "").upper()
            if action not in ("BUY", "SHORT", "EXIT"):
                continue
            if action != "EXIT" and d.get("symbol") in portfolio["positions"]:
                continue  # already in it; the stop, target and trailing stop manage it from here
            if d.get("valid_until") and str(d["valid_until"]) < now_t.strftime("%H:%M"):
                continue
            triggered = d.get("trigger_above") is not None or d.get("trigger_below") is not None
            if triggered or not act_now or (action != "EXIT" and market_open(now_t) and now_t.time() < FIRST_ENTRY):
                armed.append({k: d.get(k) for k in ("symbol", "action", "entry", "stop_loss", "target", "conviction",
                                                    "trigger_above", "trigger_below", "valid_until", "rationale")})
            else:
                immediate.append(d)
        self.reflex.arm(armed)
        self.save_day()
        for a in armed:
            when = (f"above {a['trigger_above']}" if a.get("trigger_above") is not None else
                    f"below {a['trigger_below']}" if a.get("trigger_below") is not None else "at the open")
            print(f"   🎯 armed: {a['action']} {a['symbol']} {when}"
                  + (f" until {a['valid_until']}" if a.get("valid_until") else "")
                  + (f", SL {a['stop_loss']} TGT {a['target']}" if a["action"] != "EXIT" else ""))
        if immediate:
            self.trade(immediate, snapshot, cycle)
        if decision.get("journal"):
            self.emotions.add_journal(decision["journal"])
        self.emotions.save()
        return decision

    def budget_note(self, e):
        key = str(e).split("'")[1] if "'" in str(e) else str(e)
        if key not in self._budget_notes:
            self._budget_notes.add(key)
            print(f"   💸 {e}. The code engine keeps trading the armed plan and managing open positions.")

    def safe_decide(self, reason, role="intraday", prices=None):
        try:
            return self.decide(reason, role, prices)
        except BudgetExceeded as e:
            self.budget_note(e)
        except Exception as e:  # An AI outage must never stop the stops and targets.
            print(f"   ⚠️  Arjun couldn't think this time: {type(e).__name__}: {str(e)[:200]}")

    # ---- doing (code) -------------------------------------------------------------------

    def record_exits(self, closed, cycle=None):
        for sym, net, charges, reason in closed:
            self.emotions.on_trade_closed(net, self.limits.capital)
            if cycle is not None:
                cycle["exits"].append({"symbol": sym, "net": net, "charges": charges, "reason": reason})
            self.event(f"{'✅' if net >= 0 else '❌'} {sym}: {reason}, net ₹{net:,.0f} (charges ₹{charges:,.0f}) "
                       f"→ mood: {self.emotions.mood}")
        if closed:
            self.emotions.save()

    def trade(self, decisions, snapshot, cycle=None):
        t = now_ist()
        if self.mode == "intraday" and market_open(t) and t.time() >= LAST_ENTRY:
            decisions = [d for d in decisions if (d.get("action") or "").upper() == "EXIT"]
        orders, rejected = risk.review(decisions, snapshot, self.broker.portfolio(), self.emotions, self.limits,
                                       self.broker.realized_today())
        if cycle is not None:
            cycle["orders"], cycle["rejected"] = orders, rejected
        for r in rejected:
            self.event(f"✋ {r['action']} {r['symbol']} vetoed: {r['reason']}")
        if orders and self.args.live and not market_open(t):
            self.event("Market is closed; no live orders sent.")
            return
        for o in orders:
            sym, last = o["symbol"], snapshot[o["symbol"]]["last_price"]
            try:
                if o["action"] == "EXIT":
                    net, charges = self.broker.close(sym, last, "Arjun exited: " + o["reason"][:100])
                    self.record_exits([(sym, net, charges, "Arjun exited")], cycle)
                    continue
                if self.args.live:
                    msg = self.broker.open(o, o["entry"])
                elif (o["side"] == "LONG" and last <= o["entry"]) or (o["side"] == "SHORT" and last >= o["entry"]):
                    msg = self.broker.open(o, last)  # a limit order at or through the market fills at the market
                else:
                    msg = f"paper {o['action']} {sym} not filled: last ₹{last} hasn't reached the ₹{o['entry']} limit"
                msg += (f" | SL {o['stop_loss']} TGT {o['target']}, win ₹{o['net_win']:,.0f} / lose ₹{o['net_loss']:,.0f}"
                        f" net ({o['size_note']})")
            except Exception as e:
                msg = f"{o['action']} {sym} FAILED: {type(e).__name__}: {e}"
            self.event(f"📨 {msg}")

    def tick(self):
        """One pass of the reflex engine. Returns sharp moves for the AI to look at."""
        t = now_ist()
        positions = self.broker.portfolio()["positions"]
        prices, bar_time = self.feed.prices(self.watch_symbols(positions))
        if not prices:
            return [], None
        light = {s: {"last_price": p} for s, p in prices.items()}
        closed = self.broker.check_exits(light)
        self.record_exits(closed)
        if closed:
            positions = self.broker.portfolio()["positions"]
        for sym, stop in self.reflex.trail(positions, prices):
            try:
                if self.broker.move_stop(sym, stop):
                    self.event(f"🔒 {sym} stop tightened to {stop}")
            except Exception as e:
                self.event(f"⚠️  {sym} stop move failed: {e}")
        if t.time() >= FIRST_ENTRY:
            fired, expired = self.reflex.due(prices, t, held=set(positions))
            for s in expired:
                self.event(f"⌛ {s['action']} {s['symbol']} setup dropped: {s['why']}")
            if fired:
                snapshot = {s: {**self._snap.get(s, {}), "last_price": p} for s, p in prices.items()}
                for s in fired:
                    self.event(f"⚡ {s['action']} {s['symbol']} triggered at ₹{s['entry']}")
                self.trade(fired, snapshot)
            self.save_day()
        return self.reflex.shocks(prices, t), bar_time

    # ---- the trading session --------------------------------------------------------------

    def session(self):
        """From now until 15:10: tick every few seconds, think when something happens, square off."""
        a = self.args
        print(f"\n{'═' * 70}\n🔔 Trading session {self.today}: ticking every {self.tick_seconds}s on {self.feed.name}")
        if not trading_day(now_ist().date()):
            print("   Not a trading day.")
            return
        if "plan" not in self.day or "morning_decision" not in self.day:
            if not self.safe_meeting():
                return
        if now_ist().time() < MARKET_OPEN:
            print(f"   Waiting for the {MARKET_OPEN:%H:%M} open.")
            time.sleep(self.until(MARKET_OPEN, 24 * 60))
        self.ensure_equity()
        last_ai = last_review = last_news = now_ist()
        while self.mode == "intraday" and now_ist().time() < SQUARE_OFF or self.mode == "swing" and market_open():
            try:
                shocks, bar_time = self.tick()
            except Exception as e:  # A bad tick (network, data) must not end the session.
                print(f"   ⚠️  tick failed: {type(e).__name__}: {str(e)[:150]}")
                shocks, bar_time = [], None
            t = now_ist()
            if bar_time is not None and t.time() >= FIRST_ENTRY and bar_time.date() != t.date():
                print(f"   No prices for today (latest bar {bar_time:%Y-%m-%d}). Market holiday? Ending the session.")
                return
            reasons = [f"sharp move: {s} {m:+.2f}% in {self.reflex.window.seconds // 60} min" for s, m in shocks]
            if t - last_news >= dt.timedelta(minutes=a.news_every):
                last_news = t
                for item in self.watch_news():
                    if (item.get("materiality") or 0) >= 4:
                        reasons.append(f"important news: {item['headline']}")
            if t - last_review >= dt.timedelta(minutes=a.review_every):
                reasons.append("scheduled review")
            if reasons and t - last_ai >= dt.timedelta(minutes=a.ai_cooldown):
                last_ai = t
                if "scheduled review" in reasons:
                    last_review = t
                if self.budget.exhausted("intraday"):
                    self.budget_note(BudgetExceeded("AI budget for 'intraday' used up today"))
                else:
                    self.safe_decide("; ".join(reasons))
            time.sleep(self.tick_seconds)
        if self.mode == "intraday":
            snapshot = {s: {"last_price": p} for s, p in self.feed.prices(self.watch_symbols())[0].items()}
            self.record_exits(self.broker.square_off(snapshot))
            self.reflex.arm([])
            self.save_day()
        self.finish()

    def safe_meeting(self):
        try:
            return self.morning_meeting()
        except BudgetExceeded as e:
            self.budget_note(e)
        except Exception as e:
            print(f"   ⚠️  Morning meeting failed: {type(e).__name__}: {str(e)[:200]}")
        return False

    def watch_news(self):
        try:
            items = news.watch(self.watcher, self.symbols)
        except BudgetExceeded as e:
            self.budget_note(e)
            return []
        except Exception as e:
            print(f"   ⚠️  News check failed: {type(e).__name__}: {str(e)[:150]}")
            return []
        for i in items:
            print(f"   📰 [{i.get('materiality')}] {i['headline']}")
        if not items:
            print(f"   📰 {now_ist():%H:%M} nothing new")
        return items

    # ---- around the clock -------------------------------------------------------------------

    def autopilot(self):
        a = self.args
        print(f"🤖 Autopilot. News every {a.night_every} min outside market hours, meeting at "
              f"{MORNING_MEETING:%H:%M}, session {MARKET_OPEN:%H:%M}-{SQUARE_OFF:%H:%M}. "
              f"AI budget ${self.budget.limit:.2f}/day. Ctrl+C to stop.")
        while True:
            t = now_ist()
            if t.date().isoformat() != self.today:
                self.open_day(t.date())
            done = self.day.get("verdict") is not None or self.day.get("session_done")
            if trading_day(t.date()) and MORNING_MEETING <= t.time() < SQUARE_OFF and not done:
                if "morning_decision" not in self.day:
                    print(f"\n🌅 {t:%H:%M} Morning meeting")
                    self.safe_meeting()
                if t.time() >= MARKET_OPEN:
                    self.session()
                    self.day["session_done"] = True
                    self.save_day()
                    continue
                self.watch_news()
                wait = self.until(MARKET_OPEN, a.night_every)
            else:
                print(f"\n🌙 {t:%a %H:%M} news check")
                self.watch_news()
                every = a.night_every if trading_day(t.date()) or t.weekday() == 6 else a.night_every * 6
                wait = self.until(MORNING_MEETING, every)
            time.sleep(wait)

    @staticmethod
    def until(at, every_min):
        """Seconds to sleep: the regular interval, or less if `at` comes first today or tomorrow."""
        t = now_ist()
        target = t.replace(hour=at.hour, minute=at.minute, second=0, microsecond=0)
        if target <= t:
            target += dt.timedelta(days=1)
        return max(1, min(every_min * 60, (target - t).total_seconds()))

    # ---- end of day ---------------------------------------------------------------------------

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
                           "mission": self.emotions.mission_summary(self.limits.daily_target_pct),
                           "ai_spend": self.budget.summary()}
        self.log["council"], self.log["plan"] = self.day.get("council"), self.day.get("plan")
        self.log["news"] = news.since(now_ist() - dt.timedelta(hours=24))
        self.log["emotions_after"] = {k: v for k, v in self.emotions.s.items() if k not in ("journal", "days")}
        path = write_report(self.log, self.emotions)
        print(f"\n📄 Report: {path}\n   Mood: {self.emotions.mood}. {self.log['day']['mission']}\n   {self.budget.summary()}")

    def run_once(self):
        self.header()
        if not market_open() and not self.args.live:
            print("   ⚠️  The market is closed: paper fills will use the latest available prices.")
        if self.day.get("morning_decision"):
            self.safe_decide("manual run", role="morning")
        else:
            self.safe_meeting()
        self.finish()

    def header(self):
        print(f"📈 Arjun's desk, {self.today}. Mode: {self.mode}. Broker: {self.broker.name}. Boss: {self.log['boss']}. "
              f"Team: {len(SPECIALISTS)} specialists on {self.log['team']}. Watcher: {self.log['watcher']}.")
        print(f"   {self.emotions.mission_summary(self.limits.daily_target_pct)}")


def write_report(log, emotions):
    day, plan, council = log["day"], log.get("plan") or {}, log.get("council") or {}
    cell = lambda x: str(x).replace("|", "/").replace("\n", " ")
    lines = [f"# Arjun's desk, {log['date']} ({log['mode']})", "",
             f"Broker: {log['broker']}. Boss: {log['boss']}. Team: {log['team']}. Watcher: {log['watcher']}.", "",
             f"**Net P&L today: ₹{day['realized_net']:,.0f}** on start-of-day equity ₹{day['start_equity'] or 0:,.0f}. "
             + (f"Verdict: {day['verdict']['pct']:+.2f}% ({'target hit' if day['verdict']['hit'] else 'target missed'})."
                if day.get("verdict") else "Day still open."), "",
             day["mission"], "", f"{day['ai_spend']}.", "", f"Mood after the session: **{emotions.mood}**.", ""]
    if log.get("news"):
        lines += ["## News log (last 24 hours)", ""]
        lines += [f"- {n['seen_at'][5:16].replace('T', ' ')} [{n.get('materiality')}] {n['headline']} "
                  f"({n.get('direction')}; {', '.join(map(str, n.get('affects') or []))})" for n in log["news"][-40:]]
        lines.append("")
    agenda = council.get("agenda") or {}
    if agenda:
        lines += ["## Morning agenda", ""] + [f"- 📰 {h}" for h in agenda.get("headlines", [])]
        lines += [f"- ❓ {q}" for q in agenda.get("agenda", [])] + [""]
    minutes = council.get("minutes") or {}
    if minutes:
        lines += ["## Council minutes", "", minutes.get("market_read", ""), "",
                  "| Stock | Consensus | Strength | For | Against | Dissent |", "|---|---|---|---|---|---|"]
        for sym, m in (minutes.get("per_symbol") or {}).items():
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
    if log["events"]:
        lines += ["## Trading timeline", ""] + [f"- {e}" for e in log["events"]] + [""]
    for c in log["cycles"]:
        d = c.get("decision") or {}
        lines += [f"## Arjun at {c['time']} IST: {c.get('reason', '')}", "", f"> {d.get('feeling', '')}", "",
                  f"Plan verdict: {d.get('plan_verdict')}. {d.get('plan_comment', '')}", ""]
        for x in d.get("decisions", []):
            trig = (f" when above {x['trigger_above']}" if x.get("trigger_above") is not None else
                    f" when below {x['trigger_below']}" if x.get("trigger_below") is not None else "")
            lines.append(f"- {x.get('action')} {x.get('symbol')}{trig}"
                         + (f" entry {x.get('entry')} SL {x.get('stop_loss')} TGT {x.get('target')}"
                            if x.get("action") in ("BUY", "SHORT") else "")
                         + f": {x.get('rationale', '')}")
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
    ap.add_argument("--session", "--loop", action="store_true", help="Run today's session tick by tick until 15:10")
    ap.add_argument("--autopilot", action="store_true", help="Run around the clock: news, morning meeting, sessions")
    ap.add_argument("--mode", choices=["intraday", "swing"], default="intraday")
    ap.add_argument("--target", type=float, default=1.0, help="Daily net target, %% of start-of-day equity")
    ap.add_argument("--capital", type=float, default=100_000, help="Starting paper capital (₹)")
    ap.add_argument("--daily-budget", type=float, default=20.0, help="Max AI spend per day in USD (default 20)")
    ap.add_argument("--tick", type=float, help="Seconds between price checks (default: 3 live, 30 paper)")
    ap.add_argument("--review-every", type=int, default=30, help="Minutes between scheduled AI reviews in a session")
    ap.add_argument("--news-every", type=int, default=10, help="Minutes between news checks in a session")
    ap.add_argument("--night-every", type=int, default=10, help="Minutes between news checks outside market hours")
    ap.add_argument("--ai-cooldown", type=int, default=3, help="Minimum minutes between Arjun's intraday calls")
    ap.add_argument("--shock", type=float, default=1.0, help="%% move in 5 minutes that wakes the AI")
    ap.add_argument("--rounds", type=int, default=2, help="Council rounds (1 = no debate)")
    ap.add_argument("--boss", choices=["grok", "claude"], help="Provider for Arjun (default: same as team)")
    ap.add_argument("--team", choices=["grok", "claude"], help="Provider for moderator, specialists and strategist")
    ap.add_argument("--watch", choices=["grok", "claude"], help="Provider for the news watcher (default: same as team)")
    ap.add_argument("--boss-model", help="Model ID for Arjun")
    ap.add_argument("--team-model", help="Model ID for the team")
    ap.add_argument("--watch-model", help="Model ID for the news watcher (default for Claude: claude-haiku-5-5)")
    ap.add_argument("--no-search", action="store_true", help="Agents don't use live web search")
    ap.add_argument("--live", action="store_true", help="Trade real money through Zerodha Kite Connect")
    args = ap.parse_args()

    desk = Desk(args)
    if args.live and input("\n⚠️  LIVE: Arjun will place real-money orders through Zerodha without asking again"
                           + (" on every trading day until you stop him" if args.autopilot else " today")
                           + ". Type YES to allow: ").strip() != "YES":
        sys.exit("Not confirmed. Nothing was sent.")
    if args.autopilot:
        desk.autopilot()
    elif args.session:
        desk.header()
        desk.session()
    else:
        desk.run_once()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped. Open positions stay open (live: with their stop orders at the broker); run again to manage them.")
