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
