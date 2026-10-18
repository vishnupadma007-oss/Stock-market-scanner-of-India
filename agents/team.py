"""Runs the whole agent team once and returns a report the app can display."""
from datetime import datetime
from zoneinfo import ZoneInfo

from . import ai_analyst, data, journal, regime, scanner
from .chart_image import candle_png
from .chart_reader import read_chart
from .decision import decide
from .indicators import hist_vol
from .options import suggest_contract
from .risk import plan

IST = ZoneInfo("Asia/Kolkata")


def run(cfg: dict, use_ai: bool = True, progress=lambda msg, frac: None, now: datetime | None = None) -> dict:
    now = now or datetime.now(IST)
    today = now.date()

    progress("Market Regime agent: reading Nifty and India VIX", 0.05)
    idx = data.daily_bars([data.NIFTY, data.INDIA_VIX], period="6mo")
    if data.NIFTY not in idx:
        raise RuntimeError("Could not download Nifty data. Try again in a minute.")
    mkt = regime.assess(idx[data.NIFTY], idx.get(data.INDIA_VIX), cfg)

    progress(f"Scanner agent: scanning {len(cfg['universe'])} F&O stocks", 0.15)
    daily = data.daily_bars(cfg["universe"], period="6mo")
    gainers, losers = scanner.scan(daily, cfg)
    lots = {**data.nse_lot_sizes(), **(cfg.get("lot_sizes") or {})}

    work = [(row, "gainer") for _, row in gainers.iterrows()] + \
           [(row, "loser") for _, row in losers.iterrows()]
    candidates = []
    for i, (row, side) in enumerate(work):
        sym = row["symbol"]
        progress(f"Chart Reader agent: {sym}", 0.2 + 0.5 * i / max(len(work), 1))
        intra = data.intraday_bars(sym)
        profile = row.to_dict()
        chart = read_chart(intra, profile, side)
        option = suggest_contract(sym, profile["ltp"], side, hist_vol(daily[sym]["Close"]),
                                  lots.get(sym), cfg, today)
        candidates.append({"symbol": sym, "side": side, "profile": profile, "chart": chart,
                           "option": option, "intraday": intra, "ai": None})

    # Only the strongest few go to the AI analyst, to keep token use small.
    ai_on = use_ai and cfg["ai"]["enabled"] and ai_analyst.available()
    if ai_on:
        best = sorted((c for c in candidates if not c["intraday"].empty),
                      key=lambda c: c["chart"]["score"], reverse=True)[:cfg["ai"]["max_candidates"]]
        for i, c in enumerate(best):
            progress(f"AI Analyst agent: reviewing {c['symbol']} chart and news", 0.7 + 0.25 * i / len(best))
            png = candle_png(c["intraday"], f"{c['symbol']} 5-min")
            facts = {"day_change_pct": round(c["profile"]["chg_1d"], 2),
                     "week_change_pct": round(c["profile"]["chg_1w"], 2),
                     "month_change_pct": round(c["profile"]["chg_1m"], 2),
                     "daily_rsi": round(c["profile"]["rsi_daily"], 1),
                     "chart_reader_score": c["chart"]["score"],
                     "chart_reader_signals": [s for s, _ in c["chart"]["signals"]],
                     "market": mkt["notes"], "option": c["option"]["contract"]}
            c["ai"] = ai_analyst.review(c["symbol"], c["side"], png, facts, cfg["ai"])

    progress("Risk Manager and Decision agents", 0.97)
    trades_today = journal.trades_on(today.isoformat())
    for c in sorted(candidates, key=lambda c: c["chart"]["score"], reverse=True):
        c["risk"] = plan(c["option"], trades_today, now, cfg)
        c["decision"] = decide(c["side"], mkt, c["chart"], c["risk"], c["ai"], cfg)
        if c["decision"]["verdict"] == "TRADE":
            trades_today += 1

    journal.log([{
        "date": today.isoformat(), "time": now.strftime("%H:%M"), "symbol": c["symbol"],
        "side": c["side"], "contract": c["option"]["contract"], "verdict": c["decision"]["verdict"],
        "score": c["decision"]["score"], "spot": round(c["profile"]["ltp"], 2),
        "est_premium": c["risk"]["entry_premium"], "target_premium": c["risk"]["target_premium"],
        "qty": c["risk"]["qty"], "result": "",
    } for c in candidates if c["decision"]["verdict"] in ("TRADE", "WATCH")])

    progress("Done", 1.0)
    return {"time": now, "regime": mkt, "candidates": candidates, "ai_used": ai_on,
            "scanned": len(daily)}
