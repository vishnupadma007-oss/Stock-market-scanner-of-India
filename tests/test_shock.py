from datetime import datetime

from agents import intel, shock

NOW = datetime(2026, 10, 22, 11, 0)
CALM = {"IT": 0.2, "Bank": -0.1, "Auto": 0.3, "Pharma": 0.1, "Metal": -0.2}
UP = {k: 1.8 for k in CALM}
DOWN = {k: -1.9 for k in CALM}


def news(headlines):
    return [intel.make_item(id=f"s{k}", time="2026-10-22 10:00:00", source="Reuters", kind="news", headline=h)
            for k, h in enumerate(headlines)]


def test_ceasefire_rally_blocks_fading_gainers():
    items = news(["US and Iran agree ceasefire, oil prices plunge", "Global stocks surge as war ends with ceasefire",
                  "Sensex soars 1,500 points as US-Iran ceasefire boosts markets"])
    v = shock.assess(1.8, -14.0, UP, items, NOW)
    assert v["state"] == "rally" and v["gainers_ok"] is False and v["losers_ok"] is True


def test_war_crash_blocks_bounce_trades():
    v = shock.assess(-1.9, 15.0, DOWN, [], NOW)
    assert v["state"] == "crash" and v["losers_ok"] is False and v["gainers_ok"] is True


def test_extreme_day_stands_aside_and_normal_days_pass():
    assert shock.assess(-2.8, 30.0, DOWN, [], NOW)["state"] == "extreme"
    assert shock.assess(1.1, 2.0, UP, [], NOW)["state"] == "normal"      # an ordinary good day
    assert shock.assess(1.7, 1.0, CALM, [], NOW)["state"] == "normal"    # a move with no confirmation
