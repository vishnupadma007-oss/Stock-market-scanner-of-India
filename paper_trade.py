"""Open a paper trade from Claude's own analysis (results, news, preopen, spurt), outside the scanner.

    python paper_trade.py open --symbol TECHM --direction up --strategy results --reason "Q2 beat"
    python paper_trade.py status

direction "up" buys a CALL, "down" buys a PUT. These trades belong to the news team and use its
own paper capital. The same rules as the scanner apply: trading day, entry window, one news-team
trade at a time, lot must fit the team's free money, target dynamically forecasted from the news
catalyst (not capped at 1%), no stop-loss. The running watcher re-prices the trade and closes it
at the forecast target or at square-off.
"""
import argparse
import asyncio
import json
from datetime import datetime

from agents import daymode, holidays
from agents.config import load_config
from agents.indmoney import IndMoney
from agents.risk import plan
from watcher import (FIELDS, IST, NEWS_DEFAULTS, TEAMS, _t, _trade_key, account, capital_share,
                     has_open, load_trades, max_open, open_count, team_full, rolled_note, save_trades, team_cfg, team_of,
                     valuation_view)


async def find_key(im: IndMoney, symbol: str) -> str | None:
    rows = await im.call("lookup_ind_keys", names=[symbol])
    return next((r["ind_key"] for r in rows if r.get("ind_key", "").startswith("INDS")), None)


def check_rules(trades: list[dict], now: datetime, cfg: dict, symbol: str | None = None) -> str | None:
    """Why a new trade is not allowed right now, or None."""
    closed = holidays.holiday_name(now.date())
    if closed:
        return f"NSE closed today ({closed})"
    day = daymode.load(now.date())
    if day.get("mode") == "no_trade":
        return "day mode is set to no_trade today"
    if symbol and symbol in (day.get("avoid") or []):
        return f"{symbol} is on today's avoid list"
    if not _t(cfg["entry_start"]) <= now.time() <= _t(cfg["entry_end"]):
        return f"outside the entry window {cfg['entry_start']}-{cfg['entry_end']}"
    if team_full(trades, cfg, "news"):
        return f"{max_open(cfg, 'news')} news-team trade(s) already open: the team's limit"
    if symbol and any(t["status"] == "OPEN" and t.get("symbol") == symbol and team_of(t) == "news" for t in trades):
        return f"a news-team trade on {symbol} is already open"
    return None


async def open_trade(symbol: str, direction: str, strategy: str, reason: str, expected_move_pct: float | None = None) -> dict:
    cfg = load_config()
    now = datetime.now(IST)
    trades = load_trades()
    baseline_keys = {_trade_key(t) for t in trades}
    problem = check_rules(trades, now, cfg, symbol=symbol)
    if problem:
        return {"opened": False, "reason": problem}

    _, free = account(trades, cfg, "news")
    if free <= 0:
        return {"opened": False, "reason": "No free capital available for news team"}

    side = "loser" if direction == "up" else "gainer"  # loser -> CALL, gainer -> PUT
    async with IndMoney() as im:
        key = await find_key(im, symbol)
        if not key:
            return {"opened": False, "reason": f"{symbol} not found on INDmoney"}
        option = await im.pick_contract(key, side, cfg, now.date(), budget=free)

    if option is None:
        return {"opened": False, "reason": "no quoted option contract"}
    news_cfg = {**NEWS_DEFAULTS, **team_cfg(cfg, "news")}
    if option["ask"] < news_cfg["min_premium"]:
        return {"opened": False, "reason": f"option premium ₹{option['ask']} is under the ₹{news_cfg['min_premium']} minimum"}

    today_str = now.date().isoformat()
    trades_today = sum(t.get("date") == today_str and team_of(t) == "news" for t in trades)

    # Dynamic target price forecasting from news catalyst (no 1% cap)
    spot = float(option.get("spot") or 100.0)
    if expected_move_pct is None:
        exp_pct = 3.0 if strategy == "results" else 2.5 if strategy in ("results-gap", "preopen", "spurt") else 2.0
    else:
        exp_pct = float(expected_move_pct)
    move_rupees = round(spot * (exp_pct / 100.0), 2)
    target_spot = round(spot * (1.0 + exp_pct / 100.0) if direction == "up" else spot * (1.0 - exp_pct / 100.0), 2)
    news_forecast = {
        "level": target_spot,
        "move": move_rupees,
        "expected_move_pct": exp_pct,
        "basis": f"News forecast ({strategy}): target ₹{target_spot:.2f} ({exp_pct:+.1f}%)",
    }

    cfg_news = {
        **cfg,
        "capital": free,
        "target_mode": news_cfg.get("target_mode", "forecast"),
        "forecast_capture": news_cfg.get("forecast_capture", 0.6),
        "max_capital_per_trade": capital_share(option, {**cfg, "capital": free},
                                               {**news_cfg, "max_open_trades": max_open(cfg, "news")},
                                               open_count(trades, "news")),
    }

    risk = plan(option, trades_today, now, cfg_news,
                spread_pct=option["spread_pct"], forecast=news_forecast)
    if not risk["allowed"]:
        return {"opened": False, "reason": "; ".join(risk["blocks"])}

    row = {f: "" for f in FIELDS}
    row.update(date=today_str, opened=now.strftime("%H:%M"), symbol=symbol,
               side=side, contract=option["contract"], underlying_key=key,
               derivative_id=option["derivative_id"], qty=risk["qty"], entry_ask=option["ask"],
               target_bid=risk["target_premium"], spread_pct=round(option["spread_pct"], 2),
               status="OPEN", claude_verdict="TRADE",
               notes="; ".join(filter(None, [rolled_note(option), reason, f"Target: ₹{target_spot:.1f} ({exp_pct:+.1f}%)"])), strategy=strategy,
               valuation=valuation_view(symbol).get("label", ""))
    trades.append(row)
    save_trades(trades, baseline_keys=baseline_keys)

    return {"opened": True, "contract": option["contract"], "qty": risk["qty"], "lot_size": option["lot_size"],
            "entry_ask": option["ask"], "target_bid": risk["target_premium"],
            "expected_target_price": target_spot, "expected_move_pct": exp_pct,
            "net_profit_at_target": round(risk["net_profit"]), "capital_used": round(risk["capital_used"]),
            "square_off": cfg["square_off_time"], "strategy": strategy}


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    o = sub.add_parser("open")
    o.add_argument("--symbol", required=True)
    o.add_argument("--direction", choices=["up", "down"], required=True)
    o.add_argument("--strategy", default="results")
    o.add_argument("--reason", default="")
    o.add_argument("--move-pct", type=float, default=None, help="expected underlying move %")
    sub.add_parser("status")
    args = ap.parse_args()
    if args.cmd == "open":
        print(json.dumps(asyncio.run(open_trade(args.symbol.upper(), args.direction, args.strategy, args.reason, args.move_pct))))
    else:
        cfg = load_config()
        trades = load_trades()
        teams = {}
        for team in TEAMS:
            value, free = account(trades, cfg, team)
            teams[team] = {"account_value": round(value), "free": round(free)}
        print(json.dumps({"teams": teams, "open": [t for t in trades if t["status"] == "OPEN"]}, default=str))


if __name__ == "__main__":
    main()
