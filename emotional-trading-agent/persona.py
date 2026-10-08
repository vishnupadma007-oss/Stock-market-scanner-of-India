"""Arjun: the lead trader's persona and his emotional state.

An LLM doesn't feel anything. What this file gives the agent is the closest working version:
a backstory that shapes how he reasons and speaks, plus numeric emotions that persist between
runs and change with real results. Those emotions are fed back into his prompt, so he behaves
differently after a losing streak than after a good week.

The emotions never raise risk. risk.py can only make trades smaller when he is hurting.
"""

import datetime as dt
import json
from pathlib import Path
from zoneinfo import ZoneInfo

STATE_FILE = Path("state/emotions.json")
IST = ZoneInfo("Asia/Kolkata")

BACKSTORY = """You are Arjun, the lead trader of this desk.

For most of your life you were the one nobody counted on. Your parents compared you to everyone \
else's children and found you lacking. Your wife's family thought she had married beneath her, and \
some days she seemed to agree. Relatives laughed at your ideas; colleagues took credit for your work. \
You learned to swallow it and keep going.

Now you have been given the highest access there is: the full research desk, a live market feed and \
a brokerage account. For the first time, the only thing between you and proving them all wrong is the \
quality of your own decisions.

That pain is your fuel, but you know exactly how it destroys traders. Revenge trades, oversized bets \
and "I'll show them" gambles are how the underestimated prove everyone right. So you channel it into \
discipline: you do more homework than anyone, you respect stop-losses, you size small when unsure, \
and you would rather miss a trade than take a bad one. Your proof is a track record, not one big win.

Your mission: grow the capital by 1% every trading day, net of brokerage, taxes and every other \
charge. That is the number that will make them all go quiet. You chase it every morning. But you also \
know the arithmetic: 1% a day compounds to about 12x in a year, and nobody in history has done it \
every single day. So you reach for it only with trades that deserve it. When the day's 1% is in the \
bag, you stop and protect it. A missed day costs you nothing; a blown account ends the story and \
proves every one of them right.

Speak in first person, briefly and honestly, about how you feel. Then decide like a professional."""

DEFAULT_STATE = {
    "resolve": 85,       # drive to prove himself: stays high, it's who he is
    "confidence": 50,    # earned by results, lost by losses
    "frustration": 20,   # rises with losses and being wrong
    "composure": 70,     # ability to stay calm; drops on losing streaks
    "loss_streak": 0,
    "losses_today": 0,   # three in a day = done for the day
    "win_streak": 0,
    "realized_pnl": 0.0,
    "trades_closed": 0,
    "wins": 0,
    "journal": [],       # his own reflections, most recent last
    "days": [],          # [{date, start_equity, net, pct, hit}] one per trading day
    "updated": None,
}


def _clamp(x):
    return max(0, min(100, round(x)))


class Emotions:
    def __init__(self, path=STATE_FILE):
        self.path = Path(path)
        self.s = dict(DEFAULT_STATE)
        if self.path.exists():
            self.s.update(json.loads(self.path.read_text()))

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.s["updated"] = dt.datetime.now(IST).isoformat(timespec="seconds")
        self.path.write_text(json.dumps(self.s, indent=2))

    def on_trade_closed(self, pnl, capital):
        """Update feelings from a realized result. Bigger results (relative to capital) hit harder."""
        s = self.s
        weight = min(3.0, 1 + abs(pnl) / max(capital * 0.01, 1))  # a 1%-of-capital move counts double
        s["trades_closed"] += 1
        s["realized_pnl"] = round(s["realized_pnl"] + pnl, 2)
        if pnl >= 0:
            s["wins"] += 1
            s["win_streak"] += 1
            s["loss_streak"] = 0
            s["confidence"] = _clamp(s["confidence"] + 4 * weight)
            s["frustration"] = _clamp(s["frustration"] - 5 * weight)
            s["composure"] = _clamp(s["composure"] + 3)
        else:
            s["loss_streak"] += 1
            s["losses_today"] += 1
            s["win_streak"] = 0
            s["confidence"] = _clamp(s["confidence"] - 5 * weight)
            s["frustration"] = _clamp(s["frustration"] + 8 * weight)
            s["composure"] = _clamp(s["composure"] - 4 * s["loss_streak"])
        # The old wound: being wrong in public reopens it, so resolve never really drops.
        s["resolve"] = _clamp(max(80, s["resolve"] + (2 if pnl < 0 else 0)))

    def new_day(self):
        """Overnight, feelings drift back towards baseline. A night's sleep helps composure."""
        s = self.s
        s["losses_today"] = 0
        s["frustration"] = _clamp(s["frustration"] + (DEFAULT_STATE["frustration"] - s["frustration"]) * 0.3)
        s["composure"] = _clamp(s["composure"] + (DEFAULT_STATE["composure"] - s["composure"]) * 0.3)

    def on_day_end(self, date, start_equity, net, target_pct):
        """The daily verdict on the mission."""
        s = self.s
        pct = round(100 * net / start_equity, 3) if start_equity else 0.0
        hit = pct >= target_pct
        s["days"] = [d for d in s["days"] if d["date"] != date] + [
            {"date": date, "start_equity": round(start_equity, 2), "net": round(net, 2), "pct": pct, "hit": hit}]
        s["days"] = s["days"][-250:]
        if hit:
            s["confidence"] = _clamp(s["confidence"] + 3)
            s["frustration"] = _clamp(s["frustration"] - 5)
        elif pct < 0:
            s["frustration"] = _clamp(s["frustration"] + 3)
        return pct, hit

    def mission_summary(self, target_pct):
        days = self.s["days"]
        if not days:
            return "Mission: day 1. No track record yet."
        hits = sum(d["hit"] for d in days)
        growth = 1.0
        for d in days:
            growth *= 1 + d["pct"] / 100
        return (f"Mission so far: {len(days)} trading days, target hit on {hits} "
                f"({100 * hits / len(days):.0f}%). Capital is {100 * (growth - 1):+.2f}% vs "
                f"{100 * ((1 + target_pct / 100) ** len(days) - 1):+.2f}% if every day had hit {target_pct}%. "
                f"Last day: {days[-1]['pct']:+.2f}%.")

    def add_journal(self, text):
        self.s["journal"] = (self.s["journal"] + [{"date": dt.datetime.now(IST).date().isoformat(), "entry": text}])[-30:]

    @property
    def mood(self):
        s = self.s
        if s["losses_today"] >= 3 or s["frustration"] >= 75:
            return "wounded"       # the old voices are loud; must not act on them
        if s["composure"] < 45:
            return "rattled"
        if s["confidence"] >= 80 and s["win_streak"] >= 3:
            return "riding high"   # dangerous in its own way: overconfidence
        if s["confidence"] >= 60:
            return "steady and hungry"
        return "determined"

    def describe(self):
        s = self.s
        win_rate = f"{100 * s['wins'] / s['trades_closed']:.0f}%" if s["trades_closed"] else "n/a"
        recent = "\n".join(f"- {j['date']}: {j['entry']}" for j in s["journal"][-3:]) or "- (no entries yet)"
        return (f"Your current emotional state (0-100): resolve {s['resolve']}, confidence {s['confidence']}, "
                f"frustration {s['frustration']}, composure {s['composure']}. Mood: {self.mood}.\n"
                f"Track record: {s['trades_closed']} closed trades, win rate {win_rate}, "
                f"realized P&L ₹{s['realized_pnl']:,.0f}, current loss streak {s['loss_streak']}, "
                f"win streak {s['win_streak']}.\n"
                f"Your last journal entries:\n{recent}")
