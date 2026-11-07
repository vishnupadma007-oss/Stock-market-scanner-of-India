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
    monkeypatch.setattr(mover_forecast, "preopen_gaps", lambda now: {})
    rows = mover_forecast.forecast(datetime(2026, 10, 26, 9, 0))
    assert {r["symbol"] for r in rows} == {"JSWSTEEL", "AUBANK"}  # TCS reported before the last session
    assert all("gap" in r["direction"] for r in rows)


def test_preopen_and_spurt_parsing():
    from agents import preopen
    payload = {"data": [
        {"metadata": {"symbol": "DRREDDY", "lastPrice": 1260, "pChange": 2.48, "previousClose": 1229.5},
         "detail": {"preOpenMarket": {"totalBuyQuantity": 28041, "totalSellQuantity": 32807, "finalQuantity": 142491,
                                      "lastUpdateTime": "26-Oct-2026 09:09:18"}}},
        {"metadata": {"symbol": "NOTOURS", "lastPrice": 10, "pChange": 5, "previousClose": 9.5}, "detail": {}}]}
    p = preopen.parse_preopen(payload, {"DRREDDY"})
    assert list(p) == ["DRREDDY"] and p["DRREDDY"]["gap_pct"] == 2.48 and p["DRREDDY"]["buy_sell_ratio"] == 0.85
    spurts = preopen.parse_spurts({"data": [{"symbol": "PNB", "volume": 4000, "week1AvgVolume": 1000, "pChange": 3.1},
                                            {"symbol": "TCS", "volume": 1500, "week1AvgVolume": 1000, "pChange": 1}]}, {"PNB", "TCS"})
    assert spurts == [{"symbol": "PNB", "volume_x": 4.0, "change_pct": 3.1}]


def test_mover_forecast_adds_preopen_gap_fade_candidates(monkeypatch, tmp_path):
    from agents import mover_forecast
    ann = tmp_path / "ann.csv"
    ann.write_text("time,symbol,category,subject,text,pdf,seq_id\n2026-10-24 15:26:10,AUBANK,RESULTS,x,x,x,2\n")
    monkeypatch.setattr(mover_forecast, "ANNOUNCEMENTS", ann)
    monkeypatch.setattr(mover_forecast.analyzer, "recent_items", lambda now: [])
    monkeypatch.setattr(mover_forecast, "preopen_gaps", lambda now: {"AUBANK": {"gap_pct": -5.2}, "WIPRO": {"gap_pct": -2.3}})
    rows = {r["symbol"]: r for r in mover_forecast.forecast(datetime(2026, 10, 26, 9, 10))}
    assert rows["AUBANK"]["preopen_gap"] == -5.2 and "results" in rows["AUBANK"]["why"]
    assert "fade" in rows["WIPRO"]["direction"]


def test_preopen_idea_needs_the_move_to_continue_after_the_open(monkeypatch, tmp_path):
    import watcher
    from tests.test_teams import FakeIndMoney, CFG
    monkeypatch.setattr(watcher, "IDEAS", tmp_path / "ideas.csv")
    reached = []  # ideas that got past the pre-open gate (traded, or stopped by a later check)
    monkeypatch.setattr(watcher, "log_skip", lambda *a: reached.append("skip"))

    class Gapped(FakeIndMoney):
        def __init__(self, live):
            super().__init__(move=-1.5)
            self.live = live

        async def quotes(self, keys, segments=None):
            return {"INDS01469": {"entity_stats": {"live_price": self.live, "day_open": 1760.0,
                                                   "day_change_percentage": -1.5}}}

    cfg = {**CFG, "capital": 200000}
    for t, live, passes in ((datetime(2026, 10, 21, 9, 20, tzinfo=IST), 1750.0, False),   # before 09:30
                            (datetime(2026, 10, 21, 9, 40, tzinfo=IST), 1770.0, False),   # recovering above the open
                            (datetime(2026, 10, 21, 9, 40, tzinfo=IST), 1750.0, True)):   # still falling
        reached.clear()
        watcher._daily.clear()
        watcher.reset_daily(t.date().isoformat())
        watcher._daily["ideas"] = {"TECHM": {"direction": "down", "confidence": 80, "source": "preopen",
                                             "reason": "pre-open", "priced_in": "x", "at": t}}
        trades = []
        asyncio.run(watcher.news_team(Gapped(live), trades, t, cfg))
        assert bool(trades or reached) == passes
