from datetime import date, datetime

from agents import carry

NOW = datetime(2026, 11, 4, 15, 20)
NEXT = date(2026, 11, 5)
ON = {"enabled": True}
T = {"date": "2026-11-04", "opened": "10:00", "symbol": "SBIN", "side": "loser", "contract": "SBIN-23-NOV-980-CALL",
     "status": "OPEN", "notes": ""}


def filing(t, cat, sym="SBIN"):
    return {"time": t, "symbols": [sym], "kind": "filing", "category": cat, "headline": f"{sym} {cat}",
            "sentiment": 0, "impact": 3, "scope": "stock", "sectors": [], "source": "NSE"}


def test_expiry_from_contract_name():
    assert carry.expiry_of("SBIN-23-NOV-980-CALL", date(2026, 11, 4)) == date(2026, 11, 23)
    assert carry.expiry_of("X-30-DEC-10-PUT", date(2026, 12, 31)) == date(2026, 12, 30)
    assert carry.expiry_of("garbage", date(2026, 11, 4)) is None


def test_plain_trade_is_carried():
    assert carry.should_carry(T, NOW, "news", [], [], NEXT, ON) == (True, "")


def test_not_carried_near_expiry_results_or_own_filing_or_second_night():
    assert not carry.should_carry({**T, "contract": "SBIN-05-NOV-980-CALL"}, NOW, "news", [], [], NEXT, ON)[0]
    assert not carry.should_carry(T, NOW, "news", [], ["2026-11-05"], NEXT, ON)[0]
    assert not carry.should_carry(T, NOW, "news", [filing("2026-11-04 12:00:00", "REGULATORY")], [], NEXT, ON)[0]
    assert carry.should_carry(T, NOW, "news", [filing("2026-11-04 12:00:00", "REGULATORY", "PNB")], [], NEXT, ON)[0]
    assert not carry.should_carry({**T, "date": "2026-11-03"}, NOW, "news", [], [], NEXT, ON)[0]
    assert not carry.should_carry(T, NOW, "movers", [], [], NEXT, {**ON, "teams": ["news"]})[0]


def test_morning_exit_on_overnight_filing_only():
    morning = datetime(2026, 11, 5, 9, 16)
    assert carry.overnight_exit(T, [filing("2026-11-04 18:00:00", "RESULTS")], morning)
    assert carry.overnight_exit(T, [filing("2026-11-04 11:00:00", "RESULTS")], morning) is None
    assert carry.overnight_exit(T, [], morning) is None


def test_carried_and_market_open():
    assert carry.is_carried(T, date(2026, 11, 5)) and not carry.is_carried(T, date(2026, 11, 4))
    assert not carry.market_open(datetime(2026, 11, 5, 9, 10)) and carry.market_open(datetime(2026, 11, 5, 9, 20))
