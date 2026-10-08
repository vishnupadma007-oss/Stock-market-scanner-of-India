"""Every rupee a trade costs in India: brokerage, STT, exchange charges, SEBI fee, GST, stamp
duty and DP charges. Profits and the daily target are always counted after these.

Rates change. Check your broker's charges page and edit RATES if they differ.
Defaults: Zerodha, NSE equity (as published in 2026).
"""

RATES = {
    "brokerage_delivery": 0.0,          # ₹ per order
    "brokerage_intraday_pct": 0.03,     # % of order value...
    "brokerage_intraday_cap": 20.0,     # ...or ₹20, whichever is lower
    "stt_delivery_pct": 0.1,            # buy and sell
    "stt_intraday_sell_pct": 0.025,     # sell side only
    "exchange_txn_pct": 0.00297,        # NSE, each side
    "sebi_fee_pct": 0.0001,             # ₹10 per crore, each side
    "gst_pct": 18.0,                    # on brokerage + exchange + SEBI fee
    "stamp_delivery_buy_pct": 0.015,    # buy side only
    "stamp_intraday_buy_pct": 0.003,
    "dp_charge_per_sell": 15.93,        # delivery sells: ₹13.5 + GST per stock per day
}


def round_trip(buy_value, sell_value, product="MIS", rates=RATES):
    """Charges for buying buy_value and selling sell_value of one stock (either order, so it
    works for shorts too). product: "MIS" (intraday) or "CNC" (delivery)."""
    r = rates
    turnover = buy_value + sell_value
    if product == "MIS":
        brokerage = sum(min(v * r["brokerage_intraday_pct"] / 100, r["brokerage_intraday_cap"])
                        for v in (buy_value, sell_value) if v > 0)
        stt = sell_value * r["stt_intraday_sell_pct"] / 100
        stamp = buy_value * r["stamp_intraday_buy_pct"] / 100
        dp = 0.0
    else:
        brokerage = 2 * r["brokerage_delivery"]
        stt = turnover * r["stt_delivery_pct"] / 100
        stamp = buy_value * r["stamp_delivery_buy_pct"] / 100
        dp = r["dp_charge_per_sell"] if sell_value > 0 else 0.0
    exchange = turnover * r["exchange_txn_pct"] / 100
    sebi = turnover * r["sebi_fee_pct"] / 100
    gst = (brokerage + exchange + sebi) * r["gst_pct"] / 100
    parts = {"brokerage": brokerage, "stt": stt, "exchange": exchange, "sebi": sebi,
             "gst": gst, "stamp": stamp, "dp": dp}
    parts = {k: round(v, 2) for k, v in parts.items()}
    parts["total"] = round(sum(parts.values()), 2)
    return parts


def trade_charges(side, qty, entry, exit_price, product):
    """Round-trip charges for a LONG or SHORT of qty shares from entry to exit_price."""
    if side == "LONG":
        return round_trip(qty * entry, qty * exit_price, product)
    return round_trip(qty * exit_price, qty * entry, product)


def breakeven_move_pct(price, qty, product):
    """How far the price must move (%) just to pay for the round trip."""
    if qty <= 0:
        return None
    return round(100 * round_trip(price * qty, price * qty, product)["total"] / (price * qty), 3)
