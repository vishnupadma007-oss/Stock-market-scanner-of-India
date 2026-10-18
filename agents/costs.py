"""Charges calculator for buying and selling an NSE option intraday."""


def round_trip_charges(buy_premium: float, sell_premium: float, qty: int, rates: dict) -> dict:
    buy_val, sell_val = buy_premium * qty, sell_premium * qty
    turnover = buy_val + sell_val
    brokerage = 2 * rates["brokerage_per_order"]
    stt = sell_val * rates["stt_sell_pct"] / 100
    exchange = turnover * rates["exchange_txn_pct"] / 100
    sebi = turnover * rates["sebi_per_crore"] / 1e7
    stamp = buy_val * rates["stamp_buy_pct"] / 100
    gst = (brokerage + exchange + sebi) * rates["gst_pct"] / 100
    total = brokerage + stt + exchange + sebi + stamp + gst
    return {"brokerage": brokerage, "stt": stt, "exchange": exchange, "sebi": sebi,
            "stamp": stamp, "gst": gst, "total": total}


def exit_for_net_target(buy_premium: float, qty: int, net_target_pct: float, rates: dict) -> dict:
    """Sell price at which profit after all charges equals net_target_pct of capital paid."""
    want = buy_premium * qty * net_target_pct / 100
    lo, hi = buy_premium, buy_premium * 3
    for _ in range(60):
        mid = (lo + hi) / 2
        net = (mid - buy_premium) * qty - round_trip_charges(buy_premium, mid, qty, rates)["total"]
        lo, hi = (mid, hi) if net < want else (lo, mid)
    sell = round(hi + 0.025, 1)  # round up to a tradable 0.05-ish tick
    charges = round_trip_charges(buy_premium, sell, qty, rates)
    return {"exit_premium": sell, "gross_move_pct": (sell / buy_premium - 1) * 100,
            "charges": charges, "net_profit": (sell - buy_premium) * qty - charges["total"]}
