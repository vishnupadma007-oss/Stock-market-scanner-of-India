import asyncio

from agents import activity
from agents.indmoney import IndMoney

PAYLOAD = {"data": [
    {"symbol": "BAJAJ-AUTO", "avgInOI": 10.4, "underlyingValue": 10320, "volume": 5000},
    {"symbol": "TCS", "avgInOI": -6.3, "underlyingValue": 2463, "volume": 9000},
    {"symbol": "PFC", "avgInOI": 8.5, "underlyingValue": 312.0, "volume": 3000},
    {"symbol": "SMALLCAP", "avgInOI": 40.0, "underlyingValue": 10, "volume": 1},
]}
PREV = {"BAJAJ-AUTO": 10000.0, "TCS": 2500.0, "PFC": 315.15}


def test_parse_reads_build_ups_for_our_stocks_only():
    rows = activity.parse(PAYLOAD, {"BAJAJ-AUTO", "TCS", "PFC"}, PREV)
    assert set(rows) == {"BAJAJ-AUTO", "TCS", "PFC"}
    assert rows["BAJAJ-AUTO"]["kind"] == "long build-up" and rows["BAJAJ-AUTO"]["price_pct"] == 3.2
    assert rows["TCS"]["kind"] == "long unwinding"
    assert rows["PFC"]["kind"] == "short build-up"


def test_confirms_needs_rising_oi_and_price_the_news_way():
    rows = activity.parse(PAYLOAD, {"BAJAJ-AUTO", "TCS", "PFC"}, PREV)
    assert activity.confirms(rows["BAJAJ-AUTO"], "up")
    assert not activity.confirms(rows["BAJAJ-AUTO"], "down")
    assert activity.confirms(rows["PFC"], "down")
    assert not activity.confirms(rows["TCS"], "down")  # OI falling: positions closing, not a build-up
    assert not activity.confirms(None, "up")


def test_quotes_are_sent_in_batches_of_ten():
    sizes = []

    class Fake(IndMoney):
        def __init__(self):
            pass

        async def call(self, tool, **args):
            sizes.append(len(args["ind_keys"]))
            return {k: {} for k in args["ind_keys"]}

    out = asyncio.run(Fake().quotes([f"K{i}" for i in range(12)]))
    assert sizes == [10, 2] and len(out) == 12


def _chain(spot=1767.0):
    rows = []
    for k, (ask, delta) in enumerate([(55.0, 0.57), (44.4, 0.5), (34.8, 0.43), (26.7, 0.36), (20.3, 0.3),
                                      (15.25, 0.24), (11.45, 0.19), (8.75, 0.15)]):
        strike = 1760 + 20 * k
        rows.append({"strike_price": strike, "call_data": {
            "derivative_id": f"D{strike}", "slug": f"adaniports-23-nov-{strike}-call", "sell_price": ask,
            "buy_price": round(ask * 0.99, 2), "delta": delta, "lot_size": 475, "iv": 24}})
    return {"option_chain_data": rows, "entity_details": {"live_price": spot},
            "selected_expiry": "20261123", "expiry_list": ["20261123"]}


def test_budget_steps_out_of_the_money_until_one_lot_fits():
    from datetime import date
    from agents.indmoney import affordable_option, lot_cost, pick_option
    cfg = {"strike_choice": "ATM", "budget_otm": {"enabled": True, "max_steps": 8, "min_delta": 0.15}}
    atm = pick_option(_chain(), "loser", "ATM", today=date(2026, 10, 28))
    assert atm["strike"] == 1760 and lot_cost(atm) > 7039
    opt = affordable_option(_chain(), "loser", cfg, date(2026, 10, 28), 7039)
    assert opt["strike"] == 1880 and lot_cost(opt) <= 7039 and opt["otm_for_budget"] == 6
    # Too little money even for the cheapest usable strike: nothing.
    assert affordable_option(_chain(), "loser", cfg, date(2026, 10, 28), 1000) is None
    # Delta floor: no strike weaker than 0.25 allowed -> nothing fits Rs 7,039.
    strict = {**cfg, "budget_otm": {**cfg["budget_otm"], "min_delta": 0.25}}
    assert affordable_option(_chain(), "loser", strict, date(2026, 10, 28), 7039) is None
