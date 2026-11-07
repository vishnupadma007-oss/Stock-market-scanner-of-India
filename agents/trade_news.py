"""Trade News Monitor (user's request, 31 Oct 2026): watches every OPEN trade for news that arrives
after it was bought.

- Bad news for the trade (a CALL fears bad news, a PUT fears good news) -> sell now:
  the stock's own regulatory action, a major headline or a policy hit against it, a market-wide
  shock against the trade (crash for a CALL, rally for a PUT, any "extreme" day), or major
  geopolitical / domestic news against it.
- Good news for the trade -> raise the target once (by `raise_pct` of the premium), so a trade the
  news is pushing can run further than the planned target.

Only news published after the trade opened counts (what was known at entry was already weighed).
Reads the same intelligence log as the Data Analyzer (agents/intel.py: NSE filings, concalls,
policy rulebook, ET/Mint/BS/CNBC/Google News), so it sees what the rest of the desk sees.
"""
import json
import re
import time as _time
from datetime import datetime

from . import ai_helper, analyzer

DEFAULTS = {
    "enabled": True,
    "mode": "observe",        # observe: log what it would do; act: sell / raise the target
    "min_sentiment": 0.3,     # |tone| a headline needs to count
    "own_impact": 3,          # importance (1-3) of a stock's own headline that triggers an exit
    "market_impact": 3,       # importance of market / global news that triggers an exit
    "market_sentiment": 0.5,  # ...and how strongly it must point against the trade
    "raise_pct": 5.0,         # good news: target + this % of the entry premium (once per trade)
    "good_impact": 2,
    "use_ai": True,           # the word-list tone only nominates headlines; the AI helper decides
}

_ai_cache: dict = {}

AI_SYSTEM = ("You are the risk desk of an intraday options desk on NSE India. You get one open trade and "
             "headlines that arrived after it was bought. Decide only on news that is NEW and MATERIAL for "
             "this stock or the whole Indian market TODAY. Ongoing background stories (a war that has run "
             "for months, routine commentary, market-live blogs, foreign news without an India link) are "
             "HOLD. Reply with JSON only: {\"action\": \"EXIT\"|\"RAISE\"|\"HOLD\", \"reason\": \"...\"}. "
             "EXIT = this news will likely push the stock against the trade today. RAISE = it will likely "
             "push the stock clearly further in the trade's favour today.")


def ai_judge(trade: dict, headlines: list[str], now: datetime, cfg: dict | None = None) -> dict | None:
    """The AI helper's EXIT / RAISE / HOLD on new headlines for one trade (cached per headline set)."""
    key = (trade.get("symbol"), trade.get("date"), trade.get("opened"), tuple(headlines))
    if key in _ai_cache:
        return _ai_cache[key]
    want = "a CALL (profits if the stock rises)" if trade["side"] == "loser" else "a PUT (profits if the stock falls)"
    prompt = (f"Trade: {want} on {trade['symbol']} (NSE), bought {trade['date']} {trade['opened']} IST, "
              f"to be sold by 15:20 today. Time now {now:%H:%M}.\nNew headlines:\n- " + "\n- ".join(headlines))
    text, wait = None, float((cfg or {}).get("_ai_wait") or 0)  # replays pace calls (free-tier rate limit)
    for attempt in range(4 if wait else 1):
        try:
            if wait:
                _time.sleep(wait * (attempt + 1))
            text = ai_helper.ask(prompt, ai_helper_cfg(cfg), AI_SYSTEM)
            break
        except Exception:  # rate limit or network: no answer means no action
            text = None
    out = None
    if text:
        m = re.search(r"\{.*\}", text, re.S)
        try:
            j = json.loads(m.group(0)) if m else None
            if j and str(j.get("action", "")).upper() in ("EXIT", "RAISE", "HOLD"):
                out = {"action": j["action"].upper(), "reason": str(j.get("reason", ""))[:200]}
        except ValueError:
            pass
    if out is not None:
        _ai_cache[key] = out
    return out


def ai_helper_cfg(cfg: dict | None) -> dict:
    """The AI helper's settings (config.yaml -> ai), passed in as cfg["_ai"]."""
    return {"ai": (cfg or {}).get("_ai") or {}}


def _when(item: dict) -> str:
    return str(item.get("time", ""))[:16]


def check(trade: dict, items: list[dict], now: datetime, shock_state: str = "normal",
          cfg: dict | None = None) -> dict:
    """{"action": "exit" | "raise" | "hold", "reason": str} for one open trade.
    `trade`: a paper_trades.csv row (date, opened, symbol, side, notes). `items`: intel log items."""
    c = {**DEFAULTS, **(cfg or {})}
    sym, want = trade["symbol"], ("up" if trade["side"] == "loser" else "down")
    sign = 1 if want == "up" else -1
    since, until = f"{trade['date']} {trade['opened']}", now.strftime("%Y-%m-%d %H:%M")
    new = [i for i in items if since < _when(i) <= until]
    own = [i for i in new if sym in (i.get("symbols") or [])]
    against = lambda i: i.get("sentiment", 0) * sign <= -c["min_sentiment"]
    helps = lambda i: i.get("sentiment", 0) * sign >= c["min_sentiment"]

    bad = []
    if shock_state == "extreme" or (shock_state == "crash" and want == "up") or (shock_state == "rally" and want == "down"):
        bad.append(f"market shock ({shock_state})")
    for i in own:
        if i.get("kind") == "filing" and i.get("category") == "REGULATORY":
            bad.append(f"regulatory action: {i['headline'][:100]}")
        elif i.get("kind") == "policy" and i.get("impact", 0) >= 2 and against(i):
            bad.append(f"policy hit: {i['headline'][:100]}")
        elif i.get("impact", 0) >= c["own_impact"] and against(i):
            bad.append(f"bad news for the trade: {i['headline'][:100]}")
    for i in new:
        if i.get("scope") in ("market", "global") and i.get("impact", 0) >= c["market_impact"] \
                and i.get("sentiment", 0) * sign <= -c["market_sentiment"]:
            bad.append(f"market news against the trade: {i['headline'][:100]}")
    shock_bad = [b for b in bad if b.startswith("market shock")]
    if bad and c["use_ai"] and not shock_bad and ai_helper.available(ai_helper_cfg(c)):
        heads = list(dict.fromkeys(b.split(": ", 1)[-1] for b in bad))[:6]
        v = ai_judge(trade, heads, now, c)
        if v is None or v["action"] != "EXIT":
            bad = []  # nominated by the word list, not confirmed
        else:
            bad = [f"AI: {v['reason']} ({heads[0][:80]})"]
    if bad:
        return {"action": "exit", "reason": "; ".join(dict.fromkeys(bad))[:300]}

    if "news target raised" not in str(trade.get("notes", "")):
        good = [i for i in own if i.get("impact", 0) >= c["good_impact"] and helps(i)]
        view = analyzer.stock_view(sym, own, now) if own else None
        if good or (view and view["strong"] and view["direction"] == want):
            top = good[0]["headline"] if good else (view["reasons"] or [""])[0]
            if c["use_ai"] and ai_helper.available(ai_helper_cfg(c)):
                heads = [i["headline"] for i in good[:6]] or [top]
                v = ai_judge(trade, heads, now, c)
                if v is None or v["action"] != "RAISE":
                    return {"action": "hold", "reason": ""}
                return {"action": "raise", "reason": f"AI: {v['reason']} ({top[:80]})"}
            return {"action": "raise", "reason": f"good news for the trade: {top[:100]}"}
    return {"action": "hold", "reason": ""}


def raised_target(trade: dict, cfg: dict | None = None) -> float:
    """The new target bid after good news: old target + raise_pct of the entry premium, on the 0.05 tick."""
    c = {**DEFAULTS, **(cfg or {})}
    new = float(trade["target_bid"]) + float(trade["entry_ask"]) * c["raise_pct"] / 100
    return round(round(new * 20) / 20, 2)
