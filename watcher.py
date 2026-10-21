"""Market watcher: runs the rule-based agents on live INDmoney data all day and stays quiet
until something happens. It prints one line per event, so Claude (or you) only needs to
look when there is a signal:

    SIGNAL {...}   new paper trade opened; "team" says which team opened it:
                   movers = top gainers/losers reversal, news = filings/results/news forecasts
    EXIT {...}     paper trade closed (target reached, or square-off time)
    RESULT {...}   a company in our list filed results on NSE (figures read, priced-in check done)
    NEWS {...}     a major NSE filing (regulatory action, etc.); other filings only feed the analyzer
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
from datetime import datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from agents import (analyzer, announcements, commodities, concalls, daymode, expectations, holidays, intel, macro,
                    news, newsfeed, psychology, reaction, valuation)
from agents.chart_reader import read_chart
from agents.config import load_config
from agents.costs import round_trip_charges
from agents.decision import decide
from agents.forecast import reversal_target
from agents.indicators import intraday_sigma_per_min
from agents.indmoney import (IndMoney, LoginRequired, RateLimited, calls_last_hour, pick_option,
                             set_hourly_budget)
from agents.regime import assess
from agents.risk import plan
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
_daily: dict = {}  # once-a-day lookups: results calendar, crude contract
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
    if _daily.get("date") != today:
        _daily.clear()
        _daily.update(date=today, filings={}, seen_filings=set(), shocks_sent=set(), forecasts={},
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
        _daily["changes"] = await im.day_changes([k for k, _ in SECTORS.values()] + list(ckeys.values()))
        _daily["changes_at"] = clock.time()
    changes = _daily["changes"]
    moves = {name: changes.get(key) for name, key in ckeys.items()}
    for shock in commodities.shocks(moves, cfg or {}):
        if shock["commodity"] not in _daily["shocks_sent"]:
            _daily["shocks_sent"].add(shock["commodity"])
            emit("COMMODITY", shock)
    return {"results": _daily["results"], "usdinr": usdinr_change(), "commodities": moves,
            "sectors": {name: changes.get(k) for name, (k, _) in SECTORS.items()}}


def log_filing(item: dict) -> None:
    new = not FILINGS_LOG.exists()
    FILINGS_LOG.parent.mkdir(exist_ok=True)
    with open(FILINGS_LOG, "a", newline="") as f:
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
    _daily["expectations"][symbol] = result
    return result


def add_idea(symbol: str, direction: str, confidence: int, source: str, reason: str,
             expect: dict, now: datetime) -> None:
    """A trade idea for the news team. Confidence is cut when the move is already priced in."""
    if direction not in ("up", "down"):
        return
    adjusted = expectations.adjust_forecast({"direction": direction, "confidence": confidence}, expect)
    prev = (_daily.get("ideas") or {}).get(symbol)
    if "ideas_logged" not in _daily:  # what is already in today's log (a restart must not log it again)
        rows = csv.reader(open(IDEAS)) if IDEAS.exists() else []
        _daily["ideas_logged"] = {(r[0], r[2], r[3]) for r in rows if len(r) > 3}
    key = (now.date().isoformat(), symbol, direction)
    if (prev is None or prev["direction"] != direction) and key not in _daily["ideas_logged"]:
        _daily["ideas_logged"].add(key)  # the review counts these as the news team's chances
        new = not IDEAS.exists()
        IDEAS.parent.mkdir(exist_ok=True)
        with open(IDEAS, "a", newline="") as f:
            w = csv.writer(f)
            if new:
                w.writerow(["date", "time", "symbol", "direction", "confidence", "source", "priced_in"])
            w.writerow([now.date().isoformat(), now.strftime("%H:%M"), symbol, direction,
                        adjusted["confidence"], source, expect.get("label", "")])
    _daily.setdefault("ideas", {})[symbol] = {
        "direction": direction, "confidence": adjusted["confidence"], "source": source, "reason": reason[:300],
        "priced_in": expect.get("label"), "at": now}


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
    universe = set(cfg["universe"])
    meets = [r for r in rows if f"concall-{r.get('seq_id')}" not in _daily["intel_seen"]]
    intel.append(concalls.items_from_rows(meets, universe), _daily["intel_seen"])
    for item in announcements.material(rows, universe, since=_daily["filings_since"]):
        if item["seq_id"] in _daily["seen_filings"]:
            continue
        _daily["seen_filings"].add(item["seq_id"])
        _daily["filings"].setdefault(item["symbol"], []).append(item)
        log_filing(item)
        if item["category"] == "RESULTS" and item["pdf"].endswith(".pdf"):
            try:
                summary = announcements.results_summary(item["pdf"])
                item = {**item, **summary, "read": announcements.score_results(summary["figures"])}
            except Exception as e:
                item = {**item, "read": {"view": "unread", "notes": [f"PDF not read: {type(e).__name__}"]}}
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
                         f"Results {view}; " + "; ".join(rf["notes"]), item["expectations"], now)
            elif "direction_reliable" in rf:
                pass  # 3 years of history: figures alone do not tell the direction, so no trade idea from them
            elif view in ("strong", "good", "weak"):
                confidence = {"strong": 80, "good": 65, "weak": 70}[view]
                add_idea(item["symbol"], "up" if view != "weak" else "down", confidence, "results",
                         f"Results {view}: " + "; ".join(item["read"]["notes"]), item["expectations"], now)
            emit("RESULT", item)
        intel_item = announcements.to_intel(item)
        intel.append([intel_item], _daily["intel_seen"])
        if item["category"] != "RESULTS" and intel_item["impact"] >= 3:
            emit("NEWS", item)


def poll_news(cfg: dict, now: datetime) -> None:
    """News agent: Indian business and global/domestic macro headlines into the intelligence log."""
    reset_daily(now.date().isoformat())
    items, failed = newsfeed.fetch_all()
    intel.append(items, _daily["intel_seen"])
    if len(failed) == len(newsfeed.FEEDS):
        emit("ERROR", {"error": "all news feeds unreachable"})


def run_analyzer(cfg: dict, now: datetime) -> None:
    """Data Analyzer: re-forecast every stock; report strong forecasts that are new or changed."""
    items = analyzer.recent_items(now)
    for symbol in cfg["universe"]:
        view = analyzer.stock_view(symbol, items, now, cfg)
        prev = _daily["forecasts"].get(symbol)
        if view["strong"] and (prev is None or prev["direction"] != view["direction"]
                               or view["confidence"] >= prev["confidence"] + 20):
            _daily["forecasts"][symbol] = view
            expect = check_expectations(symbol, now)
            add_idea(symbol, view["direction"], view["confidence"], "intel",
                     "Analyzer: " + "; ".join(str(r) for r in view.get("reasons", [])[:3]), expect, now)
            move = reaction.typical_move(symbol)
            if move:  # news forecasts are not calibrated yet: give the usual size of a day's move
                view = {**view, "usual_day_move_pct": move}
            emit("FORECAST", {**expectations.adjust_forecast(view, expect),
                              "priced_in": {k: expect.get(k) for k in ("priced_in", "label", "bar", "notes", "error")
                                            if expect.get(k) is not None},
                              "market": analyzer.market_mood(items, now)["mood"]})


_print_lock = threading.Lock()  # the information track and the scanner both print events


def emit(kind: str, payload: dict) -> None:
    with _print_lock:
        if kind == "ERROR":
            key = payload.get("error", "")[:120]
            if clock.time() - _errors_seen.get(key, 0) < 3600:
                return
            _errors_seen[key] = clock.time()
        print(f"{kind} {json.dumps(payload, default=str)}", flush=True)


def information_track(cfg: dict) -> None:
    """Runs beside the scanner: NSE filings + concalls, news and the Data Analyzer every
    `info_poll_seconds`, so a long market scan never delays them."""
    every = cfg.get("info_poll_seconds", 30)
    while True:
        started = clock.time()
        now = datetime.now(IST)
        if holidays.is_trading_day(now.date()):
            for step in (valuations, poll_filings, poll_news, run_analyzer):
                try:
                    step(cfg, now)
                except Exception as e:  # one failing source must not stop the others
                    emit("ERROR", {"error": f"{step.__name__}: {type(e).__name__}: {e}"})
        clock.sleep(max(1.0, every - (clock.time() - started)))


def load_trades() -> list[dict]:
    if not TRADES.exists():
        return []
    with open(TRADES, newline="") as f:
        return list(csv.DictReader(f))


def save_trades(rows: list[dict]) -> None:
    TRADES.parent.mkdir(exist_ok=True)
    temp_path = TRADES.with_suffix(".tmp")
    with open(temp_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    temp_path.replace(TRADES)


def _t(hhmm: str) -> time:
    h, m = hhmm.split(":")
    return time(int(h), int(m))


async def manage_open_trades(im: IndMoney, trades: list[dict], now: datetime, cfg: dict) -> None:
    square_off = now.time() >= _t(cfg["square_off_time"])
    open_trades = [t for t in trades if t["status"] == "OPEN"]
    bids = {}
    for i in range(0, len(open_trades), 10):  # one quick quote call per 10 open options
        quotes = await im.quotes([t["derivative_id"] for t in open_trades[i:i + 10]])
        bids.update({k: v.get("entity_stats", {}).get("bid_price") for k, v in quotes.items() if isinstance(v, dict)})
    for t in open_trades:
        bid = bids.get(t["derivative_id"])
        if not bid:
            continue
        if bid >= float(t["target_bid"]) or square_off:
            qty, entry = int(t["qty"]), float(t["entry_ask"])
            charges = round_trip_charges(entry, bid, qty, cfg["charges"])["total"]
            t.update(status="TARGET" if bid >= float(t["target_bid"]) else "SQUARED_OFF",
                     closed=now.strftime("%H:%M"), exit_bid=bid, charges=round(charges, 2),
                     net_pnl=round((bid - entry) * qty - charges, 2))
            emit("EXIT", {k: t[k] for k in ("symbol", "contract", "status", "entry_ask", "exit_bid", "qty", "net_pnl")})


def record_held(now: datetime, symbol: str, contract: str, score: int, ask: float) -> None:
    """A setup that passed every agent while a trade was already open (not traded)."""
    seen = set()
    if HELD.exists():
        with open(HELD, newline="") as f:
            seen = {(r["date"], r["contract"]) for r in csv.DictReader(f)}
    if (now.date().isoformat(), contract) in seen:
        return
    new = not HELD.exists()
    HELD.parent.mkdir(exist_ok=True)
    with open(HELD, "a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["date", "time", "symbol", "contract", "score", "ask"])
        w.writerow([now.date().isoformat(), now.strftime("%H:%M"), symbol, contract, score, ask])


async def scan(im: IndMoney, trades: list[dict], now: datetime, cfg: dict, hold: bool = False) -> None:
    """hold=True: a trade is already open, so only record qualifying setups, do not open them."""
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
    trades_today = sum(t["date"] == today and team_of(t) == "movers" for t in trades)
    # The movers team reads price only; news, filings and forecasts are the news team's job.
    news_votes = team_cfg(cfg, "movers").get("news_votes", False)

    for side, category, ok in (("gainer", "top-gainers", mkt["gainers_ok"]),
                               ("loser", "top-losers", mkt["losers_ok"])):
        if not ok:
            continue
        movers = [m for m in await im.movers(category, 50)
                  if m["symbol"] in universe and abs(m["change_pct"]) >= cfg["min_move_pct"]][:cfg["top_n"]]
        for m in movers:
            try:
                daily = await daily_candles(im, m["ind_key"], now.date())
                intraday = await im.candles(m["ind_key"], "5minute", "7d")
                if len(daily) < 25 or intraday.empty:
                    continue
                profile = {**stock_profile(daily), "ltp": m["price"], "chg_1d": m["change_pct"]}
                chart = read_chart(intraday, profile, side)
                if chart["score"] < cfg["min_chart_score"] + mkt["threshold_adj"]:
                    continue  # skip the option-chain call for weak charts

                option = pick_option(await im.option_chain(m["ind_key"]), side, cfg["strike_choice"])
                if option is None or option["contract"] in taken:
                    continue
                prev_close = m.get("previous_close") or m["price"] / (1 + m["change_pct"] / 100)
                forecast = reversal_target(intraday, float(prev_close), side)
                risk = plan(option, trades_today, now, cfg, sigma_per_min=intraday_sigma_per_min(intraday),
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
                           status="OPEN")
                trades.append(row)
                taken.add(option["contract"])
                trades_today += 1
                if cfg.get("one_trade_at_a_time", True):
                    hold = True  # the rest of this scan only records setups (one trade at a time)
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
                    "day_mode": day["mode"],
                    "valuation": {"label": value["label"], "would_score": value["would_score"]},
                    "crowd": {"oi_type": crowd["oi_type"], "would_score": crowd["would_score"],
                              "would_block": crowd["would_block"]},
                })
            except (LoginRequired, RateLimited):
                raise
            except Exception as e:  # one bad reply must not stop the other stocks
                emit("ERROR", {"error": f"{m['symbol']}: {type(e).__name__}: {e}"})


NEWS_DEFAULTS = {
    "auto_trade": True,
    "min_confidence": 60,   # after the priced-in cut
    "confirm_pct": 0.5,     # the stock must already be moving the forecast's way by this much today
    "max_move_pct": 4.0,    # ...but not so far that the move is used up
    "max_age_min": 120,     # ideas older than this are dropped
}


async def news_team(im: IndMoney, trades: list[dict], now: datetime, cfg: dict) -> None:
    """News team: trade the strongest results/forecast idea once the price confirms its direction.
    Buys a CALL for "up" and a PUT for "down"; same 1% net target, no stop-loss, same exits."""
    c = {**NEWS_DEFAULTS, **team_cfg(cfg, "news")}
    today = now.date().isoformat()
    done = {t["symbol"] for t in trades if t["date"] == today and team_of(t) == "news"}
    # An idea whose priced-in check failed is not traded: unchecked is not "not priced in".
    ideas = sorted(((sym, i) for sym, i in (_daily.get("ideas") or {}).items()
                    if sym not in done and i["confidence"] >= c["min_confidence"] and i.get("priced_in")
                    and (now - i["at"]).total_seconds() <= c["max_age_min"] * 60),
                   key=lambda x: -x[1]["confidence"])[:10]
    if not ideas:
        return
    for sym, _ in ideas:
        if sym not in _stock_keys:
            _stock_keys[sym] = await expectations.stock_key(im, sym)
    quotes = await im.quotes([_stock_keys[sym] for sym, _ in ideas])
    trades_today = sum(t["date"] == today and team_of(t) == "news" for t in trades)
    for sym, idea in ideas:
        try:
            stats = (quotes.get(_stock_keys[sym]) or {}).get("entity_stats") or {}
            move = stats.get("day_change_percentage")
            if move is None:
                continue
            sign = 1 if idea["direction"] == "up" else -1
            if not c["confirm_pct"] <= sign * move <= c["max_move_pct"]:
                continue  # price not confirming yet, or already moved too far
            side = "loser" if idea["direction"] == "up" else "gainer"  # loser -> CALL, gainer -> PUT
            option = pick_option(await im.option_chain(_stock_keys[sym]), side, cfg["strike_choice"])
            if option is None:
                continue
            risk = plan(option, trades_today, now, cfg, spread_pct=option["spread_pct"])
            if not risk["allowed"]:
                continue
            row = {f: "" for f in FIELDS}
            row.update(date=today, opened=now.strftime("%H:%M"), symbol=sym, side=side,
                       contract=option["contract"], underlying_key=_stock_keys[sym],
                       derivative_id=option["derivative_id"], qty=risk["qty"], entry_ask=option["ask"],
                       target_bid=risk["target_premium"], spread_pct=round(option["spread_pct"], 2),
                       status="OPEN", notes=idea["reason"], strategy=idea["source"],
                       valuation=valuation_view(sym).get("label", ""))
            trades.append(row)
            emit("SIGNAL", {"team": "news", "symbol": sym, "direction": idea["direction"],
                            "contract": option["contract"], "qty": risk["qty"], "entry_ask": option["ask"],
                            "target_bid": risk["target_premium"], "spread_pct": row["spread_pct"],
                            "spot": stats.get("live_price"), "day_change_pct": move,
                            "lot_size": option["lot_size"], "net_profit_at_target": round(risk["net_profit"]),
                            "square_off": cfg["square_off_time"], "source": idea["source"],
                            "confidence": idea["confidence"], "priced_in": idea["priced_in"],
                            "reason": idea["reason"], "valuation": row["valuation"]})
            return  # one trade at a time
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
    value = cfg["capital"] + realised
    return value, max(value - tied_up, 0.0)


def has_open(trades: list[dict], team: str | None = None) -> bool:
    return any(t["status"] == "OPEN" and (team is None or team_of(t) == team) for t in trades)


# Two teams trade side by side, each with its own paper capital, so their results can be compared:
#   movers  top gainers/losers reversal, read from price, charts and options (strategy "reversal")
#   news    NSE filings, results, concalls and news forecasts (strategies "results", "intel")
TEAMS = ("movers", "news")
NEWS_STRATEGIES = ("results", "intel", "news")


def team_of(trade: dict) -> str:
    return "news" if trade.get("strategy") in NEWS_STRATEGIES else "movers"


def team_cfg(cfg: dict, team: str) -> dict:
    return {"capital": cfg["capital"], **(cfg.get("teams") or {}).get(team, {})}


async def cycle(cfg: dict) -> None:
    """One round for both teams. Each team has its own capital and its own one-trade-at-a-time rule."""
    now = datetime.now(IST)
    trades = load_trades()
    one_at_a_time = cfg.get("one_trade_at_a_time", True)
    try:
        async with IndMoney() as im:
            await manage_open_trades(im, trades, now, cfg)
            if _t(cfg["entry_start"]) <= now.time() <= _t(cfg["entry_end"]):
                if has_open(trades, "movers") and one_at_a_time:
                    # Busy: note setups we would have taken (every few minutes), but open nothing.
                    if clock.time() - _hold_scan.get("at", 0) >= cfg.get("hold_scan_min", 10) * 60:
                        _hold_scan["at"] = clock.time()
                        await scan(im, trades, now, cfg, hold=True)
                else:
                    _, free = account(trades, cfg, "movers")
                    if free > 0:  # size new trades from the money that is actually free right now
                        await scan(im, trades, now, {**cfg, "capital": free})
                if team_cfg(cfg, "news").get("auto_trade", True) and not (has_open(trades, "news") and one_at_a_time):
                    _, free = account(trades, cfg, "news")
                    if free > 0:
                        await news_team(im, trades, now, {**cfg, "capital": free})
    finally:
        save_trades(trades)


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
    async with IndMoney() as im:
        await manage_open_trades(im, trades, datetime.now(IST), cfg)
    save_trades(trades)
    return not has_open(trades)


def main() -> None:
    cfg = load_config()
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true", help="run one cycle and exit")
    ap.add_argument("--interval", type=float, default=cfg.get("scan_interval_min", 1),
                    help="minutes between entry scans")
    args = ap.parse_args()
    exit_every = cfg.get("exit_check_seconds", 15)
    set_hourly_budget(cfg.get("indmoney_hourly_budget", 450))

    closed = holidays.holiday_name(datetime.now(IST).date())
    if closed and not args.once:
        emit("STATUS", {"watching": False, "reason": f"NSE closed today: {closed}"})
        return
    emit("STATUS", {"watching": True, "scan_every_min": args.interval, "exit_check_every_sec": exit_every,
                    "time": datetime.now(IST)})
    if not args.once:  # NSE, news and analyzer: their own track, independent of the scan timing
        threading.Thread(target=information_track, args=(cfg,), daemon=True).start()
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
                busy = all(has_open(trades, t) for t in TEAMS) and cfg.get("one_trade_at_a_time", True)
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
