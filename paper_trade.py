"""Open a paper trade from Claude's own analysis (results or news), outside the scanner.

    python paper_trade.py open --symbol TECHM --direction up --strategy results --reason "Q2 beat"
    python paper_trade.py status

direction "up" buys a CALL, "down" buys a PUT. These trades belong to the news team and use its
own paper capital. The same rules as the scanner apply: trading day, entry window, one news-team
trade at a time, lot must fit the team's free money, target = net target after all
charges and the bid-ask gap, no stop-loss. The running watcher re-prices the trade and closes it
at the target or at square-off.
"""
import argparse
import asyncio
import json
from datetime import datetime

from agents import holidays
from agents.config import load_config
from agents.indmoney import IndMoney, pick_option
from agents.risk import plan
from watcher import FIELDS, IST, NEWS_DEFAULTS, TEAMS, _t, account, has_open, load_trades, save_trades, team_cfg


async def find_key(im: IndMoney, symbol: str) -> str | None:
    rows = await im.call("lookup_ind_keys", names=[symbol])
    return next((r["ind_key"] for r in rows if r.get("ind_key", "").startswith("INDS")), None)


def check_rules(trades: list[dict], now: datetime, cfg: dict) -> str | None:
    """Why a new trade is not allowed right now, or None."""
    closed = holidays.holiday_name(now.date())
    if closed:
        return f"NSE closed today ({closed})"
    if not _t(cfg["entry_start"]) <= now.time() <= _t(cfg["entry_end"]):
        return f"outside the entry window {cfg['entry_start']}-{cfg['entry_end']}"
    if has_open(trades, "news") and cfg.get("one_trade_at_a_time", True):
        return "a news-team trade is already open (one at a time)"
    return None


async def open_trade(symbol: str, direction: str, strategy: str, reason: str) -> dict:
    cfg = load_config()
    now = datetime.now(IST)
    trades = load_trades()
    problem = check_rules(trades, now, cfg)
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
        option = pick_option(await im.option_chain(key), side, cfg["strike_choice"])

    if option is None:
        return {"opened": False, "reason": "no quoted option contract"}
    news_cfg = {**NEWS_DEFAULTS, **team_cfg(cfg, "news")}
    if option["ask"] < news_cfg["min_premium"]:
        return {"opened": False, "reason": f"option premium ₹{option['ask']} is under the ₹{news_cfg['min_premium']} minimum"}

    risk = plan(option, 0, now, {**cfg, "capital": free, "max_capital_per_trade": news_cfg["max_capital_per_trade"]},
                spread_pct=option["spread_pct"])
    if not risk["allowed"]:
        return {"opened": False, "reason": "; ".join(risk["blocks"])}

    row = {f: "" for f in FIELDS}
    row.update(date=now.date().isoformat(), opened=now.strftime("%H:%M"), symbol=symbol,
               side=side, contract=option["contract"], underlying_key=key,
               derivative_id=option["derivative_id"], qty=risk["qty"], entry_ask=option["ask"],
               target_bid=risk["target_premium"], spread_pct=round(option["spread_pct"], 2),
               status="OPEN", claude_verdict="TRADE", notes=reason, strategy=strategy)
    trades.append(row)
    save_trades(trades)

    return {"opened": True, "contract": option["contract"], "qty": risk["qty"], "lot_size": option["lot_size"],
            "entry_ask": option["ask"], "target_bid": risk["target_premium"],
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
    sub.add_parser("status")
    args = ap.parse_args()
    if args.cmd == "open":
        print(json.dumps(asyncio.run(open_trade(args.symbol.upper(), args.direction, args.strategy, args.reason))))
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
