"""Market watcher: runs the rule-based agents on live INDmoney data all day and stays quiet
until something happens. It prints one line per event, so Claude (or you) only needs to
look when there is a signal:

    SIGNAL {...}   new paper trade opened; "team" says which team opened it:
                   movers = top gainers/losers reversal, news = filings/results/news forecasts
    EXIT {...}     paper trade closed (target reached, or square-off time)
    RESULT {...}   a company in our list filed results on NSE (figures read, priced-in check done)
    NEWS {...}     a major NSE filing (regulatory action, etc.); other filings only feed the analyzer
    POLICY {...}   a regulator/government move that clearly hits or helps some of our stocks
    SHOCK {...}    a market-wide rally or crash on big news: the movers team limits or stops reversals
    COMMODITY {...} a commodity moved sharply today (reported once per commodity per day)
    FORECAST {...} the Data Analyzer's outlook for a stock turned strong (new or changed), with priced-in check
    ERROR {...}    something needs attention (each distinct error at most once an hour)
    STATUS {...}   start of watching / market closed

Usage:  python watcher.py            (every 5 minutes during market hours)
        python watcher.py --once     (one scan, for testing)
"""
import argparse
import asyncio
import csv
import json
import sys
import threading
import time as clock
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from agents import (activity, analyzer, announcements, candles, commodities, concalls, daymode, expectations,
                    gapfollow, holidays, intel, macro, news, news_guard, newsfeed, policy, preopen,
                    psychology, reaction, shock, valuation)
from agents.chart_reader import read_chart
from agents.config import load_config
from agents.costs import round_trip_charges
from agents.decision import decide
from agents.forecast import reversal_target
from agents.indicators import intraday_sigma_per_min
from agents.indmoney import (IndMoney, LoginRequired, RateLimited, calls_last_hour,
                             set_hourly_budget)
from agents.market import context as market_context_view, headwind
from agents.momentum import early_signals, read_trend
from agents.regime import assess
from agents.risk import hit_probability, plan
from agents.scanner import stock_profile
from agents.sectors import SECTORS, sector_of

IST = ZoneInfo("Asia/Kolkata")
NIFTY_KEY, VIX_KEY = "INDI00012", "INDI00318"
TRADES = Path(__file__).resolve().parent / "journal" / "paper_trades.csv"
HELD = Path(__file__).resolve().parent / "journal" / "held_setups.csv"
FIELDS = ["date", "opened", "symbol", "side", "contract", "underlying_key", "derivative_id",
          "qty", "entry_ask", "target_bid", "spread_pct", "hit_probability", "chart_score", "oi_type",
          "status", "closed", "exit_bid", "charges", "net_pnl", "claude_verdict", "notes", "strategy",
          "valuation"]
FILINGS_LOG = Path(__file__).resolve().parent / "journal" / "announcements.csv"
IDEAS = Path(__file__).resolve().parent / "journal" / "news_ideas.csv"  # the news team's trade ideas

_errors_seen: dict[str, float] = {}
_errors_count: dict[str, int] = {}
_daily: dict = {}  # once-a-day lookups: results calendar, crude contract
_daily_lock = threading.RLock()
_trades_lock = threading.RLock()
_daily_candles: dict = {}  # (ind_key, date) -> daily candles; past days do not change intraday


_index_cache: dict = {}  # Nifty/VIX daily candles, refreshed every 15 minutes


async def index_candles(im: IndMoney):
    if clock.time() - _index_cache.get("at", 0) > 15 * 60:
        _index_cache.update(at=clock.time(), nifty=await im.candles(NIFTY_KEY, "1day", "1y"),
                            vix=await im.candles(VIX_KEY, "1day", "14d"))
    return _index_cache["nifty"], _index_cache["vix"]


async def daily_candles(im: IndMoney, key: str, today) -> "pd.DataFrame":
    if (key, today) not in _daily_candles:
        _daily_candles[(key, today)] = await im.candles(key, "1day", "1y")
    return _daily_candles[(key, today)]


def usdinr_change() -> float | None:
    """Today's USD/INR % change (INDmoney has no rupee quote; Yahoo is fine for this)."""
    try:
        import yfinance as yf
        d = yf.Ticker("INR=X").history(period="5d", interval="1d")["Close"]
        return float(d.iloc[-1] / d.iloc[-2] - 1) * 100
    except Exception:
        return None


def reset_daily(today: str) -> None:
    with _daily_lock:
        if _daily.get("date") != today:
            _daily.clear()
            # Filings already in the log were reported before (a restart must not report them again).
            if FILINGS_LOG.exists():
                with open(FILINGS_LOG, newline="", encoding="utf-8") as f:
                    seen = {r["seq_id"] for r in csv.DictReader(f) if r.get("seq_id")}
            else:
                seen = set()
            _daily.update(date=today, filings={}, seen_filings=seen, shocks_sent=set(), forecasts={},
                          expectations={}, intel_seen={i["id"] for i in intel.load(today)})


async def market_context(im: IndMoney, now: datetime, cfg: dict | None = None) -> dict:
    """Sector, commodity and rupee moves for the Macro and Commodities agents; results calendar
    for the News agent. Sharp commodity moves are reported once a day as COMMODITY events."""
    reset_daily(now.date().isoformat())
    if "commodity_keys" not in _daily:
        _daily.update(results=news.results_calendar(),
                      commodity_keys=await im.commodity_keys(commodities.COMMODITIES))
    ckeys = _daily["commodity_keys"]
    # Sector and commodity moves: every 10 minutes is fresh enough, and each instrument costs
    # one INDmoney call (17 of them every 2-minute scan would use the whole hourly allowance).
    if clock.time() - _daily.get("changes_at", 0) >= (cfg or {}).get("market_context_min", 10) * 60:
        _daily["changes"] = await im.day_changes([k for k, _ in SECTORS.values()] + list(ckeys.values()) + [VIX_KEY])
        _daily["changes_at"] = clock.time()
    changes = _daily["changes"]
    moves = {name: changes.get(key) for name, key in ckeys.items()}
    for s in commodities.shocks(moves, cfg or {}):
        if s["commodity"] not in _daily["shocks_sent"]:
            _daily["shocks_sent"].add(s["commodity"])
            emit("COMMODITY", s)
    return {"results": _daily["results"], "usdinr": usdinr_change(), "commodities": moves,
            "vix_pct": changes.get(VIX_KEY),
            "sectors": {name: changes.get(k) for name, (k, _) in SECTORS.items()}}


def log_filing(item: dict) -> None:
    new = not FILINGS_LOG.exists()
    FILINGS_LOG.parent.mkdir(exist_ok=True)
    with open(FILINGS_LOG, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["time", "symbol", "category", "subject", "text", "pdf", "seq_id"])
        if new:
            w.writeheader()
        w.writerow({k: item.get(k, "") for k in w.fieldnames})


_stock_keys: dict[str, str] = {}


def valuations(cfg: dict, now: datetime) -> dict[str, dict]:
    """Today's P/E and P/B snapshot (Yahoo, once a day; the morning brief usually saves it first)."""
    reset_daily(now.date().isoformat())
    if not _daily.get("valuations") and clock.time() >= _daily.get("valuations_retry", 0):
        _daily["valuations"] = valuation.snapshot(cfg["universe"], now.date())
        _daily["valuations_retry"] = clock.time() + 1800  # Yahoo down: try again in 30 minutes
    return _daily["valuations"]


def valuation_view(symbol: str) -> dict:
    return valuation.assess(symbol, _daily.get("valuations") or {})


def check_expectations(symbol: str, now: datetime, news_view: str | None = None) -> dict:
    """Expectations agent for one stock (run-up, hype, analyst targets): is the news priced in?
    Runs in the information thread with its own INDmoney session; once per stock per day,
    except a results reaction, which is always re-checked."""
    cached = _daily.setdefault("expectations", {}).get(symbol)
    if cached and not news_view:
        return cached

    async def go():
        async with IndMoney() as im:
            if symbol not in _stock_keys:
                _stock_keys[symbol] = await expectations.stock_key(im, symbol)
            return await expectations.for_symbol(im, symbol, _stock_keys[symbol], now.replace(tzinfo=None),
                                                 _index_cache.get("nifty"), news_view, valuation_view(symbol))
    try:
        result = asyncio.run(go())
    except Exception as e:
        if cached:  # keep the last good check (e.g. INDmoney's hourly limit was hit)
            return cached
        errors = leaf_errors(e)
        return {"error": f"{type(errors[0]).__name__}: {errors[0]}"[:200]}
    with _daily_lock:
        _daily.setdefault("expectations", {})[symbol] = result
    return result


def add_idea(symbol: str, direction: str, confidence: int, source: str, reason: str,
             expect: dict, now: datetime, expected_move_pct: float | None = None) -> None:
    """A trade idea for the news team. Confidence is cut when the move is already priced in."""
    if direction not in ("up", "down"):
        return
    with _daily_lock:
        adjusted = expectations.adjust_forecast({"direction": direction, "confidence": confidence}, expect)
        prev = (_daily.get("ideas") or {}).get(symbol)
        if prev and prev.get("source") == "results-gap" and source != "results-gap":
            return  # the market's own reaction to the results outranks a headline reading
        if "ideas_logged" not in _daily:  # what is already in today's log (a restart must not log it again)
            if IDEAS.exists():
                with open(IDEAS, newline="", encoding="utf-8") as f:
                    rows = list(csv.reader(f))
            else:
                rows = []
            _daily["ideas_logged"] = {(r[0], r[2], r[3]) for r in rows if len(r) > 3}
        key = (now.date().isoformat(), symbol, direction)
        if (prev is None or prev["direction"] != direction) and key not in _daily["ideas_logged"]:
            _daily["ideas_logged"].add(key)  # the review counts these as the news team's chances
            new = not IDEAS.exists()
            IDEAS.parent.mkdir(exist_ok=True)
            with open(IDEAS, "a", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                if new:
                    w.writerow(["date", "time", "symbol", "direction", "confidence", "source", "priced_in"])
                w.writerow([now.date().isoformat(), now.strftime("%H:%M"), symbol, direction,
                            adjusted["confidence"], source, expect.get("label", "")])
        _daily.setdefault("ideas", {})[symbol] = {
            "direction": direction, "confidence": adjusted["confidence"], "source": source, "reason": reason[:300],
            "priced_in": expect.get("label"), "at": now, "expected_move_pct": expected_move_pct}
        news_pending.set()  # the news team looks at it before the movers' next stock


# Set by a new news idea: the movers scan stops between stocks so the news team can act on it
# within a few INDmoney calls (each call is paced ~8 s apart), not after a whole scan.
news_pending = threading.Event()


def lag_seconds(item: dict, now: datetime) -> int | None:
    """Seconds from NSE publishing a filing to the watcher reporting it."""
    try:
        published = datetime.strptime(str(item["time"])[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=IST)
    except (KeyError, ValueError):
        return None
    return round((now - published).total_seconds())


def results_reaction(item: dict, now: datetime) -> dict:
    """Results Reaction analyst: expected gap/close from this stock's past results, plus tonight's
    global cues when the results came after the close."""
    if not item.get("figures"):
        return {"notes": ["Figures not read: no reaction estimate"]}
    try:
        filed = datetime.strptime(item["time"], "%Y-%m-%d %H:%M:%S")
        market_gap = 0.0
        if filed.time() > time(15, 30) or filed.time() < time(9, 15):
            if "market_gap" not in _daily:
                _daily["market_gap"] = reaction.expected_market_gap()["expected_nifty_gap_pct"]
            market_gap = _daily["market_gap"]
        return reaction.forecast(item["symbol"], item["figures"], filed, market_gap)
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"[:200], "notes": []}


def read_results(item: dict) -> dict:
    """One results reader: figures, highlights, sector KPIs and a first read of the quarter."""
    try:
        summary = announcements.results_summary(item["pdf"], item["symbol"])
        item = {**item, **summary, "read": announcements.score_results(summary["figures"], item["symbol"])}
        if item["category"] == "BOARD":
            item["category"] = "RESULTS" if summary.get("is_results") or summary["figures"] else "BOARD"
    except Exception as e:
        item = {**item, "read": {"view": "unread", "notes": [f"PDF not read: {type(e).__name__}"]}}
        if item["category"] == "BOARD":
            item["category"] = "RESULTS"  # cannot tell: report it so Claude reads it
    return item


def poll_filings(cfg: dict, now: datetime) -> None:
    """Announcements + Concall agents: new material NSE filings for our stocks. Results filings
    are read straight away and reported as RESULT events; major filings (regulatory) as NEWS;
    everything goes to the intelligence log for the Data Analyzer."""
    reset_daily(now.date().isoformat())
    if "filings_since" not in _daily:
        # From the previous session's close, so results filed overnight (or over a holiday) reach
        # the news team at the next open.
        prev = holidays.previous_trading_day(now.date() - timedelta(days=1))
        _daily.update(filings_since=f"{prev} 15:30:00", filings_from=prev)
    try:
        rows = announcements.fetch_feed(start=_daily["filings_from"], end=now.date())
    except Exception as e:
        emit("ERROR", {"error": f"NSE announcements feed: {type(e).__name__}"})
        return
    _daily["filings_from"] = now.date()  # overnight filings are in; from now on today's feed only (faster)
    universe = set(cfg["universe"])
    meets = [r for r in rows if f"concall-{r.get('seq_id')}" not in _daily["intel_seen"]]
    intel.append(concalls.items_from_rows(meets, universe), _daily["intel_seen"])
    new = [i for i in announcements.material(rows, universe, since=_daily["filings_since"])
           if i["seq_id"] not in _daily["seen_filings"]]
    for item in new:
        _daily["seen_filings"].add(item["seq_id"])
    # Results reading team: every results filing that arrived together is read at the same time
    # (PDF download, text layer, OCR for scans), so the fifth result is not kept waiting.
    to_read = [i for i in new if i["category"] in ("RESULTS", "BOARD") and i["pdf"].endswith(".pdf")]
    read = {}
    if to_read:
        workers = min(len(to_read), (cfg.get("news") or {}).get("results_workers", 10))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            read = dict(zip((i["seq_id"] for i in to_read), pool.map(read_results, to_read)))
    for item in new:
        if item["seq_id"] in read:
            item = read[item["seq_id"]]
        if item["category"] == "BOARD":  # a board meeting without results (dividend, fund-raising...)
            item["category"] = "GUIDANCE"
        with _daily_lock:
            _daily.setdefault("filings", {}).setdefault(item["symbol"], []).append(item)
        log_filing(item)
        if item["category"] == "RESULTS":
            view = item["read"]["view"]
            item["expectations"] = check_expectations(item["symbol"], now,
                                                      view if view in ("strong", "good", "weak") else None)
            item["reaction_forecast"] = results_reaction(item, now)
            rf = item["reaction_forecast"]
            if rf.get("chance_up_pct") is not None and rf.get("direction_reliable"):
                # The Reaction analyst learned from this stock's past results: trust its direction and odds.
                up = rf["expected_close_pct"] > 0
                add_idea(item["symbol"], "up" if up else "down",
                         rf["chance_up_pct"] if up else 100 - rf["chance_up_pct"], "results",
                         f"Results {view}; " + "; ".join(rf["notes"]), item["expectations"], now,
                         expected_move_pct=abs(rf["expected_close_pct"]))
            elif "direction_reliable" in rf:
                pass  # 3 years of history: figures alone do not tell the direction, so no trade idea from them
            elif view in ("strong", "good", "weak"):
                confidence = {"strong": 80, "good": 65, "weak": 70}[view]
                exp_close = abs((rf or {}).get("expected_close_pct") or 3.0)
                add_idea(item["symbol"], "up" if view != "weak" else "down", confidence, "results",
                         f"Results {view}: " + "; ".join(item["read"]["notes"]), item["expectations"], now,
                         expected_move_pct=exp_close)
            emit("RESULT", {**item, "lag_sec": lag_seconds(item, datetime.now(IST))})
        intel_item = announcements.to_intel(item)
        intel.append([intel_item], _daily["intel_seen"])
        if item["category"] != "RESULTS" and intel_item["impact"] >= 3:
            emit("NEWS", {**item, "lag_sec": lag_seconds(item, datetime.now(IST))})


def poll_news(cfg: dict, now: datetime) -> None:
    """News agent: Indian business and global/domestic macro headlines into the intelligence log."""
    reset_daily(now.date().isoformat())
    items, failed = newsfeed.fetch_all()
    new = intel.append(items, _daily["intel_seen"])
    # Policy Impact analyst: which of our stocks a regulator's or the government's move hits or helps.
    for item in new:
        impacts = policy.assess(item["headline"])
        if not impacts:
            continue
        intel.append(policy.to_intel(item, impacts), _daily["intel_seen"])
        if max(i["strength"] for i in impacts) >= 2:
            emit("POLICY", {"headline": item["headline"], "source": item["source"], "time": item["time"],
                            "impacts": sorted(impacts, key=lambda i: -i["strength"])})
    if len(failed) == len(newsfeed.FEEDS):
        emit("ERROR", {"error": "all news feeds unreachable"})


def run_analyzer(cfg: dict, now: datetime) -> None:
    """Data Analyzer: re-forecast every stock; report strong forecasts that are new or changed."""
    items = analyzer.recent_items(now)
    for symbol in cfg["universe"]:
        view = analyzer.stock_view(symbol, items, now, cfg)
        prev = _daily.get("forecasts", {}).get(symbol)
        if view["strong"] and (prev is None or prev["direction"] != view["direction"]
                               or view["confidence"] >= prev["confidence"] + 20):
            with _daily_lock:
                _daily.setdefault("forecasts", {})[symbol] = view
            expect = check_expectations(symbol, now)
            move = reaction.typical_move(symbol) or 2.0
            add_idea(symbol, view["direction"], view["confidence"], "intel",
                     "Analyzer: " + "; ".join(str(r) for r in view.get("reasons", [])[:3]), expect, now,
                     expected_move_pct=round(move * (view["confidence"] / 70.0), 2))
            if move:
                view = {**view, "usual_day_move_pct": move}
            emit("FORECAST", {**expectations.adjust_forecast(view, expect),
                              "priced_in": {k: expect.get(k) for k in ("priced_in", "label", "bar", "notes", "error")
                                            if expect.get(k) is not None},
                              "market": analyzer.market_mood(items, now)["mood"]})


_print_lock = threading.Lock()  # the information track and the scanner both print events


def emit(kind: str, payload: dict) -> None:
    with _print_lock:
        if kind == "ERROR":
            # The same error is shown once per 10 minutes, then with how often it repeated: on 27 Oct a
            # once-an-hour rule hid the news team failing every cycle for two hours.
            key = payload.get("error", "")[:120]
            _errors_count[key] = _errors_count.get(key, 0) + 1
            if clock.time() - _errors_seen.get(key, 0) < 600:
                return
            if _errors_count[key] > 1:
                payload = {**payload, "repeats": _errors_count[key] - 1}
            _errors_count[key] = 0
            _errors_seen[key] = clock.time()
        print(f"{kind} {json.dumps(payload, default=str)}", flush=True)


def filings_track(cfg: dict) -> None:
    """NSE filings watcher on its own thread: one feed call (about 1 s) covers every listed company,
    every `filings_poll_seconds`. Results are read at once, so news, the analyzer or a long
    market scan never delay a filing."""
    every = cfg.get("filings_poll_seconds", 10)
    while True:
        started = clock.time()
        now = datetime.now(IST)
        if holidays.is_trading_day(now.date()):
            try:
                poll_filings(cfg, now)
            except Exception as e:
                emit("ERROR", {"error": f"poll_filings: {type(e).__name__}: {e}"})
        clock.sleep(max(1.0, every - (clock.time() - started)))


def poll_exchange(cfg: dict, now: datetime) -> None:
    """NSE pre-open (saved once, from 09:08) and volume spurts (every 5 minutes in market hours),
    for the mover forecast and the evening review. Free NSE pages: no INDmoney calls."""
    reset_daily(now.date().isoformat())
    if now.time() >= time(9, 8) and preopen.load("preopen", now.date()) is None:
        preopen.save("preopen", now.date(), preopen.fetch_preopen(cfg["universe"]))
    if market_open(now) and clock.time() - _daily.get("spurts_at", 0) >= 300:
        _daily["spurts_at"] = clock.time()
        spurts = preopen.fetch_spurts(cfg["universe"])
        seen = preopen.load("spurts", now.date()) or {}
        for sp in spurts:  # keep the first sighting of each stock, with the time
            seen.setdefault(sp["symbol"], {**sp, "time": now.strftime("%H:%M")})
        preopen.save("spurts", now.date(), seen)
    pre = preopen.load("preopen", now.date()) or {}
    if pre and market_open(now) and clock.time() - _daily.get("activity_at", 0) >= 120:
        _daily["activity_at"] = clock.time()
        rows = activity.fetch(cfg["universe"], {s: p["prev_close"] for s, p in pre.items() if p.get("prev_close")})
        with _daily_lock:
            _daily["activity"] = rows
        activity.save(now.date(), now, rows)


def information_track(cfg: dict) -> None:
    """Runs beside the scanner: valuations, news and the Data Analyzer every `info_poll_seconds`
    (NSE filings have their own faster thread, `filings_track`)."""
    every = cfg.get("info_poll_seconds", 30)
    while True:
        started = clock.time()
        now = datetime.now(IST)
        if holidays.is_trading_day(now.date()):
            for step in (valuations, poll_news, run_analyzer, poll_exchange):
                try:
                    step(cfg, now)
                except Exception as e:  # one failing source must not stop the others
                    emit("ERROR", {"error": f"{step.__name__}: {type(e).__name__}: {e}"})
        clock.sleep(max(1.0, every - (clock.time() - started)))


def _trade_key(t: dict) -> tuple:
    return (t.get("date", ""), t.get("opened", ""), t.get("symbol", ""), t.get("contract", ""))


def load_trades() -> list[dict]:
    with _trades_lock:
        if not TRADES.exists():
            return []
        with open(TRADES, newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))


def save_trades(rows: list[dict], baseline_keys: set[tuple] | None = None) -> None:
    """Atomically writes `rows` to TRADES while preserving any concurrent on-disk updates
    (such as `claude_verdict` written by Claude or new trades appended by `paper_trade.py`
    while `cycle()` was running).
    """
    with _trades_lock:
        TRADES.parent.mkdir(exist_ok=True)
        disk_rows = load_trades() if TRADES.exists() else []
        disk_by_key = {_trade_key(r): r for r in disk_rows}
        merged = []
        seen_keys = set()
        for r in rows:
            k = _trade_key(r)
            seen_keys.add(k)
            on_disk = disk_by_key.get(k)
            if on_disk:
                if not r.get("claude_verdict") and on_disk.get("claude_verdict"):
                    r = {**r, "claude_verdict": on_disk["claude_verdict"]}
                if not r.get("notes") and on_disk.get("notes"):
                    r = {**r, "notes": on_disk["notes"]}
            merged.append(r)
        if baseline_keys is not None:
            for dr in disk_rows:
                dk = _trade_key(dr)
                if dk not in seen_keys and dk not in baseline_keys:
                    merged.append(dr)
        temp_path = TRADES.with_suffix(".tmp")
        with open(temp_path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS)
            w.writeheader()
            w.writerows(merged)
        temp_path.replace(TRADES)


def _t(hhmm: str) -> time:
    h, m = hhmm.split(":")
    return time(int(h), int(m))


async def manage_open_trades(im: IndMoney, trades: list[dict], now: datetime, cfg: dict) -> None:
    square_off = now.time() >= _t(cfg["square_off_time"])
    open_trades = [t for t in trades if t["status"] == "OPEN"]
    bids = {}
    fallbacks = {}
    for i in range(0, len(open_trades), 10):  # one quick quote call per 10 open options
        quotes = await im.quotes([t["derivative_id"] for t in open_trades[i:i + 10]])
        for k, v in quotes.items():
            if isinstance(v, dict):
                st = v.get("entity_stats", {}) or {}
                bids[k] = st.get("bid_price")
                fallbacks[k] = st.get("live_price") or st.get("ltp") or st.get("ask_price")
    for t in open_trades:
        did = t["derivative_id"]
        bid = bids.get(did)
        if not bid and square_off:
            # At 15:20 square-off, never strand a position OPEN overnight if bid_price is missing/zero
            bid = fallbacks.get(did) or float(t["entry_ask"])
        if not bid:
            continue
        bid = float(bid)
        if bid >= float(t["target_bid"]) or square_off:
            qty, entry = int(t["qty"]), float(t["entry_ask"])
            charges = round_trip_charges(entry, bid, qty, cfg["charges"])["total"]
            t.update(status="TARGET" if bid >= float(t["target_bid"]) else "SQUARED_OFF",
                     closed=now.strftime("%H:%M"), exit_bid=bid, charges=round(charges, 2),
                     net_pnl=round((bid - entry) * qty - charges, 2))
            emit("EXIT", {k: t[k] for k in ("symbol", "contract", "status", "entry_ask", "exit_bid", "qty", "net_pnl")})


GUARD_LOG = Path(__file__).resolve().parent / "journal" / "news_guard.csv"


def record_guard(now: datetime, symbol: str, side: str, chart_score: int, notes: list[str]) -> None:
    """Setups the News Guard stopped (once per stock per day), for the evening review."""
    key = (now.date().isoformat(), symbol, side)
    blocked = _daily.setdefault("guarded", set())
    if key in blocked:
        return
    blocked.add(key)
    new = not GUARD_LOG.exists()
    with open(GUARD_LOG, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["date", "time", "symbol", "side", "chart_score", "reason"])
        w.writerow([key[0], now.strftime("%H:%M"), symbol, side, chart_score, " | ".join(notes)])


def record_held(now: datetime, symbol: str, contract: str, score: int, ask: float) -> None:
    """A setup that passed every agent while a trade was already open (not traded)."""
    seen = set()
    if HELD.exists():
        with open(HELD, newline="", encoding="utf-8") as f:
            seen = {(r["date"], r["contract"]) for r in csv.DictReader(f)}
    if (now.date().isoformat(), contract) in seen:
        return
    new = not HELD.exists()
    HELD.parent.mkdir(exist_ok=True)
    with open(HELD, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["date", "time", "symbol", "contract", "score", "ask"])
        w.writerow([now.date().isoformat(), now.strftime("%H:%M"), symbol, contract, score, ask])


async def scan(im: IndMoney, trades: list[dict], now: datetime, cfg: dict, hold: bool = False,
               yield_to_news: bool = False) -> None:
    """hold=True: a trade is already open, so only record qualifying setups, do not open them.
    yield_to_news=True: stop between stocks when a new news idea arrives (the next cycle resumes)."""
    day = daymode.load(now.date())
    if day["mode"] == "no_trade":
        return
    cfg = daymode.apply(cfg, day)
    nifty, vix = await index_candles(im)
    if not nifty.empty and nifty.index[-1].date() < now.date() and now.time() >= time(9, 30):
        # No candle for today 15 minutes after the open: an unscheduled closure or a feed problem.
        emit("ERROR", {"error": f"Stale data: last Nifty candle is {nifty.index[-1].date()}, market may be closed"})
        return
    mkt = assess(nifty, vix, cfg)
    if mkt["no_trade"]:
        return

    ctx = await market_context(im, now, cfg)
    universe = set(cfg["universe"]) - set(day["avoid"])
    today = now.date().isoformat()
    taken = {t["contract"] for t in trades if t["date"] == today}
    # Same-symbol loss cooldown: do not re-enter the same (symbol, side) after a losing trade today
    stopped_out = {(t.get("symbol"), t.get("side")) for t in trades
                   if t.get("date") == today and team_of(t) == "movers"
                   and t.get("status") == "SQUARED_OFF" and float(t.get("net_pnl") or 0) < 0}
    trades_today = sum(t["date"] == today and team_of(t) == "movers" for t in trades)
    # Several trades at once (user, 27 Oct), each sized from the money still free; never two on one stock.
    free_now = float(cfg["capital"])
    open_now = open_count(trades, "movers")
    open_syms = {t.get("symbol") for t in trades if t["status"] == "OPEN" and team_of(t) == "movers"}
    slots = {"max_capital_per_trade": cfg["max_capital_per_trade"], "max_open_trades": max_open(cfg, "movers")}
    # The movers team picks trades from price only; news, filings and forecasts are the news team's
    # job. It borrows that knowledge as a safety brake (News Guard): serious news against a trade
    # makes it skip the stock (e.g. IRDAI's commission caps: PB Fintech -36% in a day).
    news_votes = team_cfg(cfg, "movers").get("news_votes", False)
    use_guard = not news_votes and team_cfg(cfg, "movers").get("news_guard", True)
    shared_news = analyzer.recent_items(now) if use_guard else []

    # Shock-day guard: on a market-wide rally or crash driven by big news, reversals are a trap.
    shock_view = shock.assess(ctx["sectors"].get("Market"), ctx.get("vix_pct"), ctx["sectors"],
                              shared_news or analyzer.recent_items(now), now, cfg)
    if shock_view["state"] != "normal":
        if _daily.setdefault("shock_sent", set()).isdisjoint({shock_view["state"]}):
            _daily["shock_sent"].add(shock_view["state"])
            emit("SHOCK", {"state": shock_view["state"], "notes": shock_view["notes"]})
        if shock_view["state"] == "extreme":
            return
    for side, category, ok in (("gainer", "top-gainers", mkt["gainers_ok"] and shock_view.get("gainers_ok", True)),
                               ("loser", "top-losers", mkt["losers_ok"] and shock_view.get("losers_ok", True))):
        if not ok:
            continue
        movers = [m for m in await im.movers(category, 50)
                  if m["symbol"] in universe and abs(m["change_pct"]) >= cfg["min_move_pct"]][:cfg["top_n"]]
        for m in movers:
            if yield_to_news and news_pending.is_set():
                return  # a fresh news idea: let the news team act first
            if (m["symbol"], side) in stopped_out or m["symbol"] in open_syms:
                continue
            try:
                daily = await daily_candles(im, m["ind_key"], now.date())
                intraday = await im.candles(m["ind_key"], "5minute", "7d")
                if len(daily) < 25 or intraday.empty:
                    continue
                profile = {**stock_profile(daily), "ltp": m["price"], "chg_1d": m["change_pct"]}
                chart = read_chart(intraday, profile, side)
                if chart["score"] < cfg["min_chart_score"] + mkt["threshold_adj"]:
                    continue  # skip the option-chain call for weak charts
                if use_guard:
                    guard = news_guard.check(m["symbol"], side, shared_news,
                                             _daily.get("filings", {}).get(m["symbol"], []), now, cfg,
                                             results_dates=(ctx.get("results") or {}).get(m["symbol"]))
                    if guard["block"]:
                        record_guard(now, m["symbol"], side, chart["score"], guard["notes"])
                        continue  # serious news against the trade: move on to the next stock

                option = await im.pick_contract(m["ind_key"], side, cfg, now.date(), budget=free_now)
                if option is None or option["contract"] in taken:
                    continue
                prev_close = m.get("previous_close") or m["price"] / (1 + m["change_pct"] / 100)
                forecast = reversal_target(intraday, float(prev_close), side)
                sized = {**cfg, "capital": free_now,
                         "max_capital_per_trade": capital_share(option, {"capital": free_now}, slots, open_now)}
                risk = plan(option, trades_today, now, sized, sigma_per_min=intraday_sigma_per_min(intraday),
                            spread_pct=option["spread_pct"], forecast=forecast)
                extras = []
                if news_votes:
                    extras.append(news.assess(m["symbol"], side, m["change_pct"], now.date(),
                                              await im.news(m["ind_key"]), ctx["results"], intraday, cfg,
                                              filings=_daily.get("filings", {}).get(m["symbol"], [])))
                if cfg.get("use_macro", True):
                    # Crude is handled with the other commodities below, so not passed here.
                    extras.append(macro.assess(m["symbol"], side, m["change_pct"],
                                               ctx["sectors"].get(sector_of(m["symbol"])), None,
                                               ctx["usdinr"], cfg))
                if news_votes:
                    extras.append(commodities.assess(m["symbol"], side, ctx["commodities"], cfg))
                    extras.append(analyzer.as_extra(
                        analyzer.stock_view(m["symbol"], analyzer.recent_items(now), now, cfg), side, cfg))
                crowd = psychology.assess(side, m["price"], m["change_pct"],
                                          await im.futures_oi_change(m["symbol"], option["expiry"]),
                                          m.get("52_week_high"), m.get("52_week_low"),
                                          m.get("circuit_upper_limit"), m.get("circuit_lower_limit"), cfg)
                extras.append(crowd)
                extras.append(candles.as_extra(intraday, side, cfg))  # observe mode until it proves itself
                value = valuation.as_extra(valuation_view(m["symbol"]), side, cfg)
                if news_votes:
                    extras.append(value)
                decision = decide(side, mkt, chart, risk, None, cfg, extras)
                if decision["verdict"] != "TRADE":
                    continue
                if hold:
                    record_held(now, m["symbol"], option["contract"], decision["score"], option["ask"])
                    continue

                row = {f: "" for f in FIELDS}
                row.update(date=today, opened=now.strftime("%H:%M"), symbol=m["symbol"], side=side,
                           contract=option["contract"], underlying_key=m["ind_key"],
                           derivative_id=option["derivative_id"], qty=risk["qty"], entry_ask=option["ask"],
                           target_bid=risk["target_premium"], spread_pct=round(option["spread_pct"], 2),
                           hit_probability=round(risk["hit_probability"]), chart_score=chart["score"],
                           oi_type=crowd["oi_type"], strategy="reversal", valuation=value["label"],
                           status="OPEN", notes=rolled_note(option))
                trades.append(row)
                taken.add(option["contract"])
                trades_today += 1
                open_now += 1
                open_syms.add(m["symbol"])
                free_now -= float(option["ask"]) * int(risk["qty"])
                if open_now >= slots["max_open_trades"] or free_now <= 0:
                    hold = True  # every slot (or all the money) in use: the rest of this scan only records setups
                emit("SIGNAL", {
                    "team": "movers",
                    **{k: row[k] for k in ("symbol", "side", "contract", "qty", "entry_ask", "target_bid",
                                           "spread_pct", "hit_probability", "chart_score")},
                    "spot": m["price"], "day_change_pct": m["change_pct"], "lot_size": option["lot_size"],
                    "net_profit_at_target": round(risk["net_profit"]), "square_off": cfg["square_off_time"],
                    "chart_signals": [s for s, _ in chart["signals"]], "market": mkt["notes"],
                    "news_and_macro": [n for e in extras for n in e["notes"]],
                    "news_driven": next((e["news_driven"] for e in extras if "news_driven" in e), None),
                    "decision_score": decision["score"],
                    "forecast": {"level": forecast.get("level") and round(forecast["level"], 2),
                                 "basis": forecast["basis"],
                                 "option_price_there": risk["forecast_premium"] and round(risk["forecast_premium"], 2)},
                    "day_mode": day["mode"], "rolled_from": option.get("rolled_from"),
                    "valuation": {"label": value["label"], "would_score": value["would_score"]},
                    "crowd": {"oi_type": crowd["oi_type"], "would_score": crowd["would_score"],
                              "would_block": crowd["would_block"]},
                })
            except (LoginRequired, RateLimited):
                raise
            except Exception as e:  # one bad reply must not stop the other stocks
                emit("ERROR", {"error": f"{m['symbol']}: {type(e).__name__}: {e}"})


async def results_gap_ideas(im: IndMoney, now: datetime, c: dict, done: set) -> None:
    """Results-gap follower (agents/gapfollow.py): stocks whose results came out after the last
    session (before today's open) and opened with a gap of `gap_min_pct`+ vs Nifty become ideas in
    the gap's direction once the first minutes extend it. One quotes call for all of them."""
    open_time = datetime.combine(now.date(), time(9, 15))
    syms = [s for s, items in (_daily.get("filings") or {}).items()
            if s not in done and s not in _daily.setdefault("gap_done", set())
            and any(i.get("category") == "RESULTS" and str(i.get("time", "")) < open_time.strftime("%Y-%m-%d %H:%M:%S")
                    for i in items)]
    if not syms:
        return
    for sym in syms:
        if sym not in _stock_keys:
            _stock_keys[sym] = await expectations.stock_key(im, sym)
    quotes = await im.quotes([_stock_keys[s] for s in syms] + [NIFTY_KEY])
    nifty = (quotes.get(NIFTY_KEY) or {}).get("entity_stats")
    for sym in syms:
        g = gapfollow.assess((quotes.get(_stock_keys[sym]) or {}).get("entity_stats") or {}, nifty, c["gap_min_pct"])
        if g is None:
            _daily["gap_done"].add(sym)  # no gap worth following today
            continue
        if not g["confirmed"]:
            continue  # look again on the next pass, until gap_until
        _daily["gap_done"].add(sym)
        exp_move = min(max(abs(g["gap_pct"]) * 1.2, 2.5), float(c.get("gap_max_move_pct", 8.0)))
        add_idea(sym, g["direction"], c["gap_confidence"], "results-gap",
                 f"Results gap {g['gap_pct']:+.1f}% vs Nifty, {g['since_open_pct']:+.1f}% since the open: "
                 f"results-day gaps carry on (61-75% in our data)", {"label": "results gap rule"}, now,
                 expected_move_pct=exp_move)
        _daily["ideas"][sym]["max_move"] = c["gap_max_move_pct"]


def preopen_early_ideas(now: datetime, c: dict, done: set, universe: set) -> None:
    """NSE pre-open early trade ideas: checks indicative open prices and order-book buy/sell
    imbalances at market open (09:15-09:45 IST) to forecast early opening runners."""
    if not c.get("preopen_rule", True) or not (time(9, 15) <= now.time() <= time(9, 45)):
        return
    data = preopen.load("preopen", now.date()) or {}
    for sym, p in data.items():
        if sym in done or sym not in universe:
            continue
        gap = p.get("gap_pct")
        ratio = p.get("buy_sell_ratio")
        if gap is None or abs(gap) < 1.0 or ratio is None:
            continue
        direction = None
        if gap >= 1.0 and ratio >= 1.35:
            direction = "up"
        elif gap <= -1.0 and ratio <= 0.75:
            direction = "down"
        if direction:
            has_filing = bool(_daily.get("filings", {}).get(sym))
            conf = 80 if has_filing else 75
            exp_move = max(abs(gap) * 1.1, 2.0)
            add_idea(sym, direction, conf, "preopen",
                     f"NSE pre-open order flow: gap {gap:+.1f}%, buy/sell ratio {ratio:.2f}x; strong opening order demand",
                     {"label": "NSE pre-open order imbalance"}, now, expected_move_pct=exp_move)


def volume_spurt_ideas(now: datetime, c: dict, done: set, universe: set) -> None:
    """NSE volume spurts early trade ideas: detects stocks surging 3x+ over 1-week volume
    during market hours and pairs with catalyst analysis to catch early intraday breakouts."""
    if not c.get("spurt_rule", True) or not market_open(now):
        return
    data = preopen.load("spurts", now.date()) or {}
    for sym, sp in data.items():
        if sym in done or sym not in universe:
            continue
        vx = sp.get("volume_x")
        chg = sp.get("change_pct")
        if vx is None or vx < 3.0 or chg is None or abs(chg) < 1.0:
            continue
        direction = "up" if chg > 0 else "down"
        has_news = bool(_daily.get("filings", {}).get(sym)) or bool(_daily.get("forecasts", {}).get(sym))
        conf = 80 if has_news else 70
        exp_move = max(abs(chg) * 0.8, 2.0)
        add_idea(sym, direction, conf, "spurt",
                 f"NSE volume spurt {vx:.1f}x normal volume ({chg:+.1f}%); aggressive institutional participation",
                 {"label": "NSE volume spurt"}, now, expected_move_pct=exp_move)


def capital_share(option: dict, cfg: dict, c: dict, open_now: int = 0) -> float:
    """A team's share of its free money (`cfg["capital"]`) for one new trade. The free money is
    split over the open-trade slots still empty (user, 27 Oct: as many trades as the money
    allows), so a first trade leaves money for the next ones; never above `max_capital_per_trade`.
    When one lot alone costs more than that share but the free money covers it, the trade buys
    exactly one lot (without this, after a few losses no normal lot fitted and the team stopped)."""
    slots = max(int(c.get("max_open_trades", 1)) - open_now, 1)
    share = min(float(c["max_capital_per_trade"]), 1.0 / slots)
    lot_cost = float(option.get("ask") or option.get("est_premium") or 0) * float(option.get("lot_size") or 1)
    if cfg["capital"] > 0 and lot_cost > cfg["capital"] * share:
        return min(1.0, lot_cost * 1.000001 / cfg["capital"])  # one lot (or blocked when it costs more than all)
    return share


def open_count(trades: list[dict], team: str) -> int:
    return sum(t["status"] == "OPEN" and team_of(t) == team for t in trades)


def max_open(cfg: dict, team: str) -> int:
    """How many trades the team may hold at once (each still needs free money for at least one lot)."""
    return int(team_cfg(cfg, team).get("max_open_trades", cfg.get("max_open_trades", 1)))


def team_full(trades: list[dict], cfg: dict, team: str) -> bool:
    return open_count(trades, team) >= max_open(cfg, team)


SKIPS_DIR = Path(__file__).parent / "journal" / "intel"  # git-ignored by day, committed each evening


def log_skip(now: datetime, sym: str, idea: dict, move: float, reason: str) -> None:
    """News-team ideas whose price already confirmed but which were not traded, with the reason."""
    path = SKIPS_DIR / f"news_skips-{now.date().isoformat()}.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    new = not path.exists()
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["time", "symbol", "direction", "confidence", "move_pct", "reason"])
        w.writerow([now.strftime("%H:%M"), sym, idea["direction"], idea["confidence"], round(move, 2), reason])


def rolled_note(option: dict) -> str:
    notes = []
    if option.get("rolled_from"):
        notes.append(f"Expiry week: next month's contract instead of {option['rolled_from']}")
    if option.get("otm_for_budget"):
        notes.append(f"{option['otm_for_budget']} strike(s) out of the money so one lot fits the free money")
    return "; ".join(notes)


NEWS_DEFAULTS = {
    "auto_trade": True,
    "min_confidence": 60,   # after the priced-in cut
    "confirm_pct": 0.5,     # the stock must already be moving the forecast's way by this much today
    "max_move_pct": 4.0,    # ...but not so far that the move is used up
    "max_age_min": 120,     # ideas older than this are dropped
    "min_trend_score": 60,  # Trend Checker: the chart must back the news's direction
    "trend_recheck_min": 5,  # a stock whose chart failed is looked at again after this long
    "target_mode": "forecast",  # user decision: 1% target removed; forecast how far the stock can move based on news
    "forecast_capture": 0.6,    # capture 60% of the forecasted underlying move on the option premium
    "min_forecast_move_pct": 1.5,
    "preopen_rule": True,       # use NSE pre-open order flow imbalances for early opening trades (09:15-09:45)
    "preopen_confirm_from": "09:30",  # ...traded only from here, while still moving the gap's way since the open
    "spurt_rule": True,         # use NSE volume spurts (3x+ volume) for early intraday momentum participation
    "gap_rule": False,      # results-gap follower (agents/gapfollow.py)
    "gap_from": "09:30", "gap_until": "10:30", "gap_min_pct": 1.0, "gap_confidence": 75, "gap_max_move_pct": 8.0,
    "early_entry": False,   # enter before confirm_pct on volume + order book (agents/momentum.early_signals)
    "activity_rule": True,  # F&O build-up the news's way (agents/activity.py): allows the early entry, +points on the trend
    "activity_min_oi_pct": 5.0,
    "activity_points": 15,
    "early_pct": 0.2,       # ...once the stock has moved at least this much the news's way
    "early_volume_x": 1.5,  # ...latest 5-min candle volume vs usual at that time of day
    "early_book_x": 1.5,    # ...NSE buyers vs sellers (sellers vs buyers for "down")
    "market_headwind_pct": 0.8,  # no CALL when Nifty is down this much on bad news (no PUT into such a rally)
    "min_premium": 5.0,     # no options cheaper than this: tiny premiums need huge quantities and wide spreads
    "max_capital_per_trade": 0.5,  # share of the team's free money one trade may use (no stop-loss, so size is the brake)
}


async def news_team(im: IndMoney, trades: list[dict], now: datetime, cfg: dict) -> None:
    """News team: trade the strongest results/forecast idea once the price confirms its direction.
    Buys a CALL for "up" and a PUT for "down"; forecasts the target price based on news, no stop-loss, same exits."""
    day = daymode.load(now.date())
    if day["mode"] == "no_trade":
        return
    avoid = set(day.get("avoid") or [])
    c = {**NEWS_DEFAULTS, **team_cfg(cfg, "news")}
    today = now.date().isoformat()
    universe = set(cfg["universe"]) - avoid
    done = {t["symbol"] for t in trades if t["date"] == today and team_of(t) == "news"} | avoid
    if c.get("gap_rule") and _t(c["gap_from"]) <= now.time() <= _t(c["gap_until"]):
        await results_gap_ideas(im, now, c, done)
    preopen_early_ideas(now, c, done, universe)
    volume_spurt_ideas(now, c, done, universe)
    # An idea whose priced-in check failed is not traded: unchecked is not "not priced in".
    ideas = sorted(((sym, i) for sym, i in (_daily.get("ideas") or {}).items()
                    if sym not in done and i["confidence"] >= c["min_confidence"] and i.get("priced_in")
                    and (now - i["at"]).total_seconds() <= c["max_age_min"] * 60),
                   key=lambda x: -x[1]["confidence"])[:10]
    if not ideas:
        return
    for sym, _ in list(ideas):
        if sym not in _stock_keys:
            try:
                _stock_keys[sym] = await expectations.stock_key(im, sym)
            except (LoginRequired, RateLimited):
                raise
            except Exception as e:  # one stock's lookup must not stop the whole team
                emit("ERROR", {"error": f"news team lookup {sym}: {type(e).__name__}: {e}"})
                ideas.remove((sym, _))
    if not ideas:
        return
    quotes = await im.quotes([_stock_keys[sym] for sym, _ in ideas] + [NIFTY_KEY, VIX_KEY])
    # Market Context agent: how Nifty is moving and why (geopolitics, policy, economy, flows...).
    n_stats = (quotes.get(NIFTY_KEY) or {}).get("entity_stats") or {}
    v_stats = (quotes.get(VIX_KEY) or {}).get("entity_stats") or {}
    live_vix = v_stats.get("live_price")
    if live_vix is not None and float(live_vix) > float(cfg.get("max_vix", 22)):
        return  # VIX panic regime: option premiums inflated and erratic
    mkt = market_context_view(analyzer.recent_items(now), now, n_stats.get("day_change_percentage"),
                              live_vix, v_stats.get("day_change_percentage"))
    trades_today = sum(t["date"] == today and team_of(t) == "news" for t in trades)
    for sym, idea in ideas:
        try:
            stats = (quotes.get(_stock_keys[sym]) or {}).get("entity_stats") or {}
            move = stats.get("day_change_percentage")
            if move is None:
                continue
            sign = 1 if idea["direction"] == "up" else -1
            if idea.get("source") == "preopen":
                # A pre-open gap says where a stock opens, not where it goes: ordinary-day gaps reverse
                # more often than not (1 year), and on 26 Oct all 8 sell-heavy IT gap-downs rallied
                # after the open. Trade only from `preopen_confirm_from`, while still moving the gap's
                # way since the open (the results-gap rule's check).
                o, live = stats.get("day_open"), stats.get("live_price")
                if now.time() < _t(c["preopen_confirm_from"]) or not o or not live \
                        or (float(live) - float(o)) * sign <= 0:
                    continue
            if c["confirm_pct"] <= sign * move <= idea.get("max_move", c["max_move_pct"]):
                early = False  # the price has confirmed the news
            elif c.get("early_entry") and idea.get("source") != "results-gap" and c["early_pct"] <= sign * move < c["confirm_pct"]:
                early = True   # moving the news's way, not yet the full confirmation: volume + order book decide
            else:
                continue  # price not moving the news's way yet, or already moved too far
            # Trend Checker (or the early-entry check): 2-3 INDmoney calls, so a stock that failed
            # is not re-checked for a few minutes
            failed_at = _daily.setdefault("trend_failed", {}).get(sym)
            if failed_at and (now - failed_at).total_seconds() < c["trend_recheck_min"] * 60:
                continue
            daily = await daily_candles(im, _stock_keys[sym], now.date())
            intraday = await im.candles(_stock_keys[sym], "5minute", "7d")
            # F&O Activity: derivatives traders building positions the news's way (agents/activity.py)
            act = (_daily.get("activity") or {}).get(sym)
            act_ok = c.get("activity_rule") and activity.confirms(act, idea["direction"], c["activity_min_oi_pct"])
            if early:
                book = await im.quotes([_stock_keys[sym]], segments=["depth"])
                sig = early_signals(intraday, (book.get(_stock_keys[sym]) or {}).get("market_depth"),
                                    idea["direction"], c["early_volume_x"], c["early_book_x"])
                if not sig["ok"] and not act_ok:
                    _daily["trend_failed"][sym] = now
                    log_skip(now, sym, idea, move, "early entry: " + "; ".join(sig["notes"])
                             + (f"; {activity.note(act)}" if act else ""))
                    continue
                trend = {"score": None, "signals": [(f"Early entry: price {move:+.2f}%", 0)] +
                         [(n, 0) for n in sig["notes"]] + ([(activity.note(act), 0)] if act_ok else [])}
            else:
                trend = read_trend(intraday, stock_profile(daily) if len(daily) >= 25 else {}, idea["direction"])
                if act_ok:
                    trend = {"score": min(100, trend["score"] + c["activity_points"]),
                             "signals": trend["signals"] + [(activity.note(act), c["activity_points"])]}
                if trend["score"] < c["min_trend_score"]:
                    _daily["trend_failed"][sym] = now
                    log_skip(now, sym, idea, move, f"Trend Checker {trend['score']} < {c['min_trend_score']}")
                    continue
            if headwind(mkt, idea["direction"], c["market_headwind_pct"]):
                log_skip(now, sym, idea, move, "market headwind: " + "; ".join(mkt.get("notes", [])[:1]))
                continue  # the whole market is moving hard the other way on news
            side = "loser" if idea["direction"] == "up" else "gainer"  # loser -> CALL, gainer -> PUT
            option = await im.pick_contract(_stock_keys[sym], side, cfg, now.date(), budget=float(cfg["capital"]))
            if option is None or option["ask"] < c["min_premium"]:
                log_skip(now, sym, idea, move, "no option" if option is None else f"premium Rs {option['ask']} under Rs {c['min_premium']}")
                continue

            # Analytical target forecasting based on news catalyst:
            spot_price = float(stats.get("live_price") or option.get("spot") or 100.0)
            exp_pct = idea.get("expected_move_pct")
            if exp_pct is None:
                if idea.get("source") == "results":
                    exp_pct = 3.0
                elif idea.get("source") == "results-gap":
                    exp_pct = min(max(abs(idea.get("gap_pct", 1.5)) * 1.2, 2.5), float(c.get("gap_max_move_pct", 8.0)))
                elif idea.get("source") == "preopen":
                    exp_pct = max(2.0, abs(idea.get("gap_pct", 2.0)) * 1.1)
                elif idea.get("source") == "spurt":
                    exp_pct = max(2.0, abs(idea.get("change_pct", 2.0)) * 0.8)
                else:
                    typ = reaction.typical_move(sym) or 2.0
                    exp_pct = max(float(c.get("min_forecast_move_pct", 1.5)), typ * (float(idea["confidence"]) / 70.0))
            exp_pct = round(float(exp_pct), 2)
            move_rupees = round(spot_price * (exp_pct / 100.0), 2)
            target_spot = round(spot_price * (1.0 + exp_pct / 100.0) if idea["direction"] == "up" else spot_price * (1.0 - exp_pct / 100.0), 2)

            news_forecast = {
                "level": target_spot,
                "move": move_rupees,
                "expected_move_pct": exp_pct,
                "basis": f"News forecast ({idea['source']}): target ₹{target_spot:.2f} ({exp_pct:+.1f}%)",
            }

            cfg_news = {
                **cfg,
                "target_mode": c.get("target_mode", "forecast"),
                "forecast_capture": c.get("forecast_capture", 0.6),
                "max_capital_per_trade": capital_share(option, cfg, {**c, "max_open_trades": max_open(cfg, "news")},
                                                       open_count(trades, "news")),
            }
            risk = plan(option, trades_today, now, cfg_news,
                        spread_pct=option["spread_pct"], forecast=news_forecast)
            if not risk["allowed"]:
                log_skip(now, sym, idea, move, "risk: " + "; ".join(risk["blocks"])[:150])
                continue
            sigma = intraday_sigma_per_min(intraday)
            hit_prob = round(hit_probability(risk["underlying_move"] or 0.0, sigma, risk["minutes_left"]) * 100) if sigma > 0 else ""
            row = {f: "" for f in FIELDS}
            row.update(date=today, opened=now.strftime("%H:%M"), symbol=sym, side=side,
                       contract=option["contract"], underlying_key=_stock_keys[sym],
                       derivative_id=option["derivative_id"], qty=risk["qty"], entry_ask=option["ask"],
                       target_bid=risk["target_premium"], spread_pct=round(option["spread_pct"], 2),
                       hit_probability=hit_prob,
                       chart_score=trend["score"], status="OPEN", notes="; ".join(filter(None, ["Early entry: " + ", ".join(t for t, _ in trend["signals"][1:]) if early else "",
                                                     rolled_note(option), idea["reason"]])), strategy=idea["source"],
                       valuation=valuation_view(sym).get("label", ""))
            trades.append(row)
            emit("SIGNAL", {"team": "news", "symbol": sym, "direction": idea["direction"],
                            "contract": option["contract"], "qty": risk["qty"], "entry_ask": option["ask"],
                            "target_bid": risk["target_premium"], "spread_pct": row["spread_pct"],
                            "spot": spot_price, "day_change_pct": move,
                            "expected_target_price": target_spot, "expected_move_pct": exp_pct,
                            "lot_size": option["lot_size"], "net_profit_at_target": round(risk["net_profit"]),
                            "square_off": cfg["square_off_time"], "source": idea["source"],
                            "confidence": idea["confidence"], "priced_in": idea["priced_in"],
                            "reason": idea["reason"], "valuation": row["valuation"], "rolled_from": option.get("rolled_from"),
                            "entry": "early" if early else "confirmed",
                            "trend_score": trend["score"], "trend_signals": [t for t, _ in trend["signals"]],
                            "forecast": {"target_spot": target_spot, "expected_move_pct": exp_pct,
                                         "basis": news_forecast["basis"],
                                         "option_price_there": risk["forecast_premium"] and round(risk["forecast_premium"], 2)},
                            "market": {"notes": mkt["notes"], "drivers": {t: {"tone": d["tone"], "headlines": d["headlines"]}
                                                                         for t, d in mkt["drivers"].items()}}})
            return  # one new trade per round: the next round (about a minute) can add another
        except (LoginRequired, RateLimited):
            raise
        except Exception as e:
            emit("ERROR", {"error": f"news team {sym}: {type(e).__name__}: {e}"})


def account(trades: list[dict], cfg: dict, team: str | None = None) -> tuple[float, float]:
    """(account value, money free for a new trade): starting capital plus realised P&L,
    minus the premium tied up in open trades. With `team`, that team's own book only."""
    if team:
        trades = [t for t in trades if team_of(t) == team]
        cfg = team_cfg(cfg, team)
    realised = sum(float(t["net_pnl"] or 0) for t in trades if t["status"] in ("TARGET", "SQUARED_OFF"))
    tied_up = sum(float(t["entry_ask"]) * int(t["qty"]) for t in trades if t["status"] == "OPEN")
    # top_up: paper money added later (e.g. to restore a team to its starting capital after
    # losses); it is not profit, so the scoreboard keeps the team's real record.
    value = cfg["capital"] + float(cfg.get("top_up", 0)) + realised
    return value, max(value - tied_up, 0.0)


def has_open(trades: list[dict], team: str | None = None) -> bool:
    return any(t["status"] == "OPEN" and (team is None or team_of(t) == team) for t in trades)


# Two teams trade side by side, each with its own paper capital, so their results can be compared:
#   movers  top gainers/losers reversal, read from price, charts and options (strategy "reversal")
#   news    NSE filings, results, concalls, news forecasts, pre-open imbalances, volume spurts, and results-gap rule
TEAMS = ("movers", "news")
NEWS_STRATEGIES = ("results", "intel", "news", "results-gap", "preopen", "spurt")


def team_of(trade: dict) -> str:
    return "news" if trade.get("strategy") in NEWS_STRATEGIES else "movers"


def team_cfg(cfg: dict, team: str) -> dict:
    return {"capital": cfg["capital"], **(cfg.get("teams") or {}).get(team, {})}


async def cycle(cfg: dict) -> None:
    """One round for both teams. Each team has its own capital and its own limit on open trades."""
    now = datetime.now(IST)
    trades = load_trades()
    baseline_keys = {_trade_key(t) for t in trades}
    try:
        async with IndMoney() as im:
            await manage_open_trades(im, trades, now, cfg)
            if _t(cfg["entry_start"]) <= now.time() <= _t(cfg["entry_end"]):
                # News first: results, filings, preopen and spurts move stocks within minutes, so the news team
                # acts before the movers' scan, and the scan stops for any idea that arrives meanwhile.
                news_free = team_cfg(cfg, "news").get("auto_trade", True) and not team_full(trades, cfg, "news")
                news_free = news_free and account(trades, cfg, "news")[1] > 0

                async def run_news():
                    news_pending.clear()
                    await news_team(im, trades, now, {**cfg, "capital": account(trades, cfg, "news")[1]})

                if news_free:
                    await run_news()
                else:
                    news_pending.clear()  # busy: ideas wait in the list, the movers need not stop
                if team_full(trades, cfg, "movers"):
                    # Busy: note setups we would have taken (every few minutes), but open nothing.
                    if clock.time() - _hold_scan.get("at", 0) >= cfg.get("hold_scan_min", 10) * 60:
                        _hold_scan["at"] = clock.time()
                        await scan(im, trades, now, cfg, hold=True, yield_to_news=news_free)
                else:
                    _, free = account(trades, cfg, "movers")
                    if free > 0:  # size new trades from the money that is actually free right now
                        await scan(im, trades, now, {**cfg, "capital": free}, yield_to_news=news_free)
                if news_free and news_pending.is_set() and not team_full(trades, cfg, "news"):
                    await run_news()  # an idea arrived during the scan
    finally:
        save_trades(trades, baseline_keys=baseline_keys)


_hold_scan: dict = {}


def leaf_errors(exc: BaseException) -> list[BaseException]:
    """The real errors inside an exception group (the MCP client wraps errors in groups)."""
    if isinstance(exc, BaseExceptionGroup):
        return [leaf for e in exc.exceptions for leaf in leaf_errors(e)]
    return [exc]


def market_open(now: datetime) -> bool:
    return holidays.is_trading_day(now.date()) and time(9, 15) <= now.time() <= time(15, 30)


async def exits_only(cfg: dict) -> bool:
    """Fast path between scans: only re-price open trades (one quote call).
    Returns True when a trade closed, so the next scan can run straight away."""
    trades = load_trades()
    if not has_open(trades):
        return False
    baseline_keys = {_trade_key(t) for t in trades}
    async with IndMoney() as im:
        await manage_open_trades(im, trades, datetime.now(IST), cfg)
    save_trades(trades, baseline_keys=baseline_keys)
    return not has_open(trades)


def main() -> None:
    cfg = load_config()
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true", help="run one cycle and exit")
    ap.add_argument("--interval", type=float, default=cfg.get("scan_interval_min", 1),
                    help="minutes between entry scans")
    args = ap.parse_args()
    exit_every = cfg.get("exit_check_seconds", 15)
    # Pace a little under the budget, so the budget guard below is a safety net, not a routine pause.
    set_hourly_budget(int(cfg.get("indmoney_hourly_budget", 450) * 0.95))

    closed = holidays.holiday_name(datetime.now(IST).date())
    if closed and not args.once:
        emit("STATUS", {"watching": False, "reason": f"NSE closed today: {closed}"})
        return
    emit("STATUS", {"watching": True, "scan_every_min": args.interval, "exit_check_every_sec": exit_every,
                    "time": datetime.now(IST)})
    if not args.once:  # NSE, news and analyzer: their own track, independent of the scan timing
        threading.Thread(target=information_track, args=(cfg,), daemon=True).start()
        threading.Thread(target=filings_track, args=(cfg,), daemon=True).start()
    last_scan = 0.0
    while True:
        now = datetime.now(IST)
        if args.once or market_open(now):
            try:
                used, budget = calls_last_hour(), cfg.get("indmoney_hourly_budget", 400)
                if used >= budget:  # leave the rest of INDmoney's 500/hour for Claude's own checks
                    emit("ERROR", {"error": "INDmoney call budget used up for this hour", "used": used,
                                   "budget": budget, "action": "waiting"})
                    clock.sleep(60)
                    continue
                trades = load_trades()
                busy = all(team_full(trades, cfg, t) for t in TEAMS)
                # While a trade is open, look for (and only record) setups every few minutes.
                every = cfg.get("hold_scan_min", 5) if busy else args.interval
                if args.once or clock.time() - last_scan >= every * 60:
                    last_scan = clock.time()
                    asyncio.run(cycle(cfg))
                elif asyncio.run(exits_only(cfg)):
                    last_scan = 0.0  # target hit: free again, scan on the next tick
            except Exception as exc:  # keep watching through temporary network/server errors
                errors = leaf_errors(exc)
                login = [e for e in errors if isinstance(e, LoginRequired)]
                limited = [e for e in errors if isinstance(e, RateLimited)]
                if login:
                    emit("ERROR", {"error": str(login[0]), "fix": "python -m agents.indmoney login"})
                    sys.exit(2)
                if limited:
                    wait = min(max(e.retry_after for e in limited), 3600)
                    emit("ERROR", {"error": "INDmoney hourly call limit reached", "pausing_min": round(wait / 60)})
                    clock.sleep(wait)
                else:
                    for e in errors:
                        emit("ERROR", {"error": f"{type(e).__name__}: {e}"})
        if args.once:
            return
        if now.time() > time(15, 30) or now.weekday() >= 5:
            emit("STATUS", {"watching": False, "reason": "market closed", "time": now})
            return
        # Calls are already paced evenly inside IndMoney.call, so a short tick is enough here.
        clock.sleep(exit_every if market_open(now) else 60)


if __name__ == "__main__":
    main()
