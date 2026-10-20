"""Market watcher: runs the rule-based agents on live INDmoney data all day and stays quiet
until something happens. It prints one line per event, so Claude (or you) only needs to
look when there is a signal:

    SIGNAL {...}   new paper trade opened (rule-based agents said TRADE)
    EXIT {...}     paper trade closed (target reached, or square-off time)
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
import time as clock
from datetime import datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

from agents import daymode, macro, news, psychology
from agents.chart_reader import read_chart
from agents.config import load_config
from agents.costs import round_trip_charges
from agents.decision import decide
from agents.forecast import reversal_target
from agents.indicators import intraday_sigma_per_min
from agents.indmoney import IndMoney, LoginRequired, RateLimited, calls_last_hour, pick_option
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
          "status", "closed", "exit_bid", "charges", "net_pnl", "claude_verdict", "notes"]

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


async def market_context(im: IndMoney, now: datetime) -> dict:
    """Sector, crude and rupee moves for the Macro agent; results calendar for the News agent."""
    today = now.date().isoformat()
    if _daily.get("date") != today:
        _daily.clear()
        _daily.update(date=today, results=news.results_calendar(), crude_key=await im.crude_key())
    keys = [k for k, _ in SECTORS.values()] + ([_daily["crude_key"]] if _daily["crude_key"] else [])
    changes = await im.day_changes(keys)
    return {"results": _daily["results"], "usdinr": usdinr_change(),
            "crude": changes.get(_daily["crude_key"]),
            "sectors": {name: changes.get(k) for name, (k, _) in SECTORS.items()}}


def emit(kind: str, payload: dict) -> None:
    if kind == "ERROR":
        key = payload.get("error", "")[:120]
        if clock.time() - _errors_seen.get(key, 0) < 3600:
            return
        _errors_seen[key] = clock.time()
    print(f"{kind} {json.dumps(payload, default=str)}", flush=True)


def load_trades() -> list[dict]:
    if not TRADES.exists():
        return []
    with open(TRADES, newline="") as f:
        return list(csv.DictReader(f))


def save_trades(rows: list[dict]) -> None:
    TRADES.parent.mkdir(exist_ok=True)
    with open(TRADES, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)


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
    mkt = assess(nifty, vix, cfg)
    if mkt["no_trade"]:
        return

    ctx = await market_context(im, now)
    universe = set(cfg["universe"]) - set(day["avoid"])
    today = now.date().isoformat()
    taken = {t["contract"] for t in trades if t["date"] == today}
    trades_today = sum(t["date"] == today for t in trades)

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
                extras = [news.assess(m["symbol"], side, m["change_pct"], now.date(), await im.news(m["ind_key"]),
                                      ctx["results"], intraday, cfg)]
                if cfg.get("use_macro", True):
                    extras.append(macro.assess(m["symbol"], side, m["change_pct"],
                                               ctx["sectors"].get(sector_of(m["symbol"])), ctx["crude"],
                                               ctx["usdinr"], cfg))
                crowd = psychology.assess(side, m["price"], m["change_pct"],
                                          await im.futures_oi_change(m["symbol"], option["expiry"]),
                                          m.get("52_week_high"), m.get("52_week_low"),
                                          m.get("circuit_upper_limit"), m.get("circuit_lower_limit"), cfg)
                extras.append(crowd)
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
                           oi_type=crowd["oi_type"],
                           status="OPEN")
                trades.append(row)
                taken.add(option["contract"])
                trades_today += 1
                emit("SIGNAL", {
                    **{k: row[k] for k in ("symbol", "side", "contract", "qty", "entry_ask", "target_bid",
                                           "spread_pct", "hit_probability", "chart_score")},
                    "spot": m["price"], "day_change_pct": m["change_pct"], "lot_size": option["lot_size"],
                    "net_profit_at_target": round(risk["net_profit"]), "square_off": cfg["square_off_time"],
                    "chart_signals": [s for s, _ in chart["signals"]], "market": mkt["notes"],
                    "news_and_macro": [n for e in extras for n in e["notes"]],
                    "news_driven": extras[0]["news_driven"], "decision_score": decision["score"],
                    "forecast": {"level": forecast.get("level") and round(forecast["level"], 2),
                                 "basis": forecast["basis"],
                                 "option_price_there": risk["forecast_premium"] and round(risk["forecast_premium"], 2)},
                    "day_mode": day["mode"],
                    "crowd": {"oi_type": crowd["oi_type"], "would_score": crowd["would_score"],
                              "would_block": crowd["would_block"]},
                })
            except (LoginRequired, RateLimited):
                raise
            except Exception as e:  # one bad reply must not stop the other stocks
                emit("ERROR", {"error": f"{m['symbol']}: {type(e).__name__}: {e}"})


def account(trades: list[dict], cfg: dict) -> tuple[float, float]:
    """(account value, money free for a new trade): starting capital plus realised P&L,
    minus the premium tied up in open trades."""
    realised = sum(float(t["net_pnl"] or 0) for t in trades if t["status"] in ("TARGET", "SQUARED_OFF"))
    tied_up = sum(float(t["entry_ask"]) * int(t["qty"]) for t in trades if t["status"] == "OPEN")
    value = cfg["capital"] + realised
    return value, max(value - tied_up, 0.0)


def has_open(trades: list[dict]) -> bool:
    return any(t["status"] == "OPEN" for t in trades)


async def cycle(cfg: dict) -> None:
    now = datetime.now(IST)
    trades = load_trades()
    async with IndMoney() as im:
        await manage_open_trades(im, trades, now, cfg)
        if _t(cfg["entry_start"]) <= now.time() <= _t(cfg["entry_end"]):
            if has_open(trades) and cfg.get("one_trade_at_a_time", True):
                # Busy: note setups we would have taken, but open nothing and wake no one.
                await scan(im, trades, now, cfg, hold=True)
            else:
                _, free = account(trades, cfg)
                if free > 0:  # size new trades from the money that is actually free right now
                    await scan(im, trades, now, {**cfg, "capital": free})
    save_trades(trades)


def leaf_errors(exc: BaseException) -> list[BaseException]:
    """The real errors inside an exception group (the MCP client wraps errors in groups)."""
    if isinstance(exc, BaseExceptionGroup):
        return [leaf for e in exc.exceptions for leaf in leaf_errors(e)]
    return [exc]


def market_open(now: datetime) -> bool:
    return now.weekday() < 5 and time(9, 15) <= now.time() <= time(15, 30)


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

    emit("STATUS", {"watching": True, "scan_every_min": args.interval, "exit_check_every_sec": exit_every,
                    "time": datetime.now(IST)})
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
                busy = has_open(load_trades()) and cfg.get("one_trade_at_a_time", True)
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
        clock.sleep(exit_every if market_open(now) else 60)


if __name__ == "__main__":
    main()
