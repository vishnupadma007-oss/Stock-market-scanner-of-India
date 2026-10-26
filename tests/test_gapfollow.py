import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

import watcher
from agents import gapfollow
from agents.config import load_config

IST = ZoneInfo("Asia/Kolkata")
NIFTY = {"day_open": 22500.0, "prev_close": 22500.0, "live_price": 22510.0}


def test_gap_read():
    au = {"day_open": 884.0, "prev_close": 932.9, "live_price": 861.1}  # AU Bank, 26 Oct
    g = gapfollow.assess(au, NIFTY)
    assert g["direction"] == "down" and g["gap_pct"] < -5 and g["confirmed"]
    bounce = {**au, "live_price": 890.0}  # gapped down but recovering: not confirmed yet
    assert not gapfollow.assess(bounce, NIFTY)["confirmed"]
    assert gapfollow.assess({"day_open": 100.5, "prev_close": 100.0, "live_price": 101}, NIFTY) is None  # 0.5% gap


class Quotes:
    async def quotes(self, keys, segments=None):
        return {"K_AU": {"entity_stats": {"day_open": 884.0, "prev_close": 932.9, "live_price": 861.1}},
                watcher.NIFTY_KEY: {"entity_stats": NIFTY}}


def test_results_gap_becomes_an_idea_that_news_cannot_overwrite(monkeypatch, tmp_path):
    monkeypatch.setattr(watcher, "IDEAS", tmp_path / "ideas.csv")
    now = datetime(2026, 10, 26, 9, 31, tzinfo=IST)
    watcher._daily.clear()
    watcher.reset_daily(now.date().isoformat())
    watcher._daily["filings"] = {"AUBANK": [{"category": "RESULTS", "time": "2026-10-24 15:26:10"}]}
    watcher._stock_keys["AUBANK"] = "K_AU"
    c = {**watcher.NEWS_DEFAULTS, **load_config()["teams"]["news"]}
    asyncio.run(watcher.results_gap_ideas(Quotes(), now, c, set()))
    idea = watcher._daily["ideas"]["AUBANK"]
    assert idea["direction"] == "down" and idea["source"] == "results-gap" and idea["max_move"] == 8.0
    watcher.add_idea("AUBANK", "up", 90, "intel", "headline", {"label": "x"}, now)
    assert watcher._daily["ideas"]["AUBANK"]["direction"] == "down"  # the market's reaction wins


def test_mover_forecast_lists_results_stocks_first(monkeypatch, tmp_path):
    from agents import mover_forecast
    ann = tmp_path / "ann.csv"
    ann.write_text("time,symbol,category,subject,text,pdf,seq_id\n"
                   "2026-10-23 14:53:31,JSWSTEEL,RESULTS,x,x,x,1\n2026-10-24 15:26:10,AUBANK,RESULTS,x,x,x,2\n"
                   "2026-10-22 10:00:00,TCS,RESULTS,x,x,x,3\n")
    monkeypatch.setattr(mover_forecast, "ANNOUNCEMENTS", ann)
    monkeypatch.setattr(mover_forecast.analyzer, "recent_items", lambda now: [])
    rows = mover_forecast.forecast(datetime(2026, 10, 26, 9, 0))
    assert {r["symbol"] for r in rows} == {"JSWSTEEL", "AUBANK"}  # TCS reported before the last session
    assert all("open" in r["direction"] for r in rows)
