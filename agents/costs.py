"""Charges calculator for buying and selling an NSE option intraday.

Implements exact statutory fee models according to Indian exchange and SEBI rules:
- Brokerage: 2 * flat fee per executed order
- STT (Securities Transaction Tax): on sell turnover (premium * qty)
- Exchange transaction charges: on round-trip turnover (buy turnover + sell turnover)
- SEBI turnover fee: on round-trip turnover
- Stamp duty: on buy turnover
- GST: 18% on (Brokerage + Exchange transaction charges + SEBI charges)

Also includes analytical closed-form target solver with strict upward ceiling to
NSE 0.05 option tick size, mathematically guaranteeing that the net profit
after all taxes and charges is always >= net_target_pct of premium invested.
"""
import math


def round_trip_charges(buy_premium: float, sell_premium: float, qty: int, rates: dict) -> dict:
    """Calculates full itemized round-trip charges for buying and selling an option."""
    buy_val = buy_premium * qty
    sell_val = sell_premium * qty
    turnover = buy_val + sell_val

    brokerage = 2.0 * rates["brokerage_per_order"]
    stt = sell_val * rates["stt_sell_pct"] / 100.0
    exchange = turnover * rates["exchange_txn_pct"] / 100.0
    sebi = turnover * rates["sebi_per_crore"] / 1e7
    stamp = buy_val * rates["stamp_buy_pct"] / 100.0
    gst = (brokerage + exchange + sebi) * rates["gst_pct"] / 100.0
    total = brokerage + stt + exchange + sebi + stamp + gst

    return {
        "brokerage": round(brokerage, 2),
        "stt": round(stt, 2),
        "exchange": round(exchange, 2),
        "sebi": round(sebi, 2),
        "stamp": round(stamp, 2),
        "gst": round(gst, 2),
        "total": round(total, 2),
        "turnover": round(turnover, 2),
    }


def exit_for_net_target(buy_premium: float, qty: int, net_target_pct: float, rates: dict,
                        tick_size: float = 0.05) -> dict:
    """Calculates the exact sell premium needed to achieve at least net_target_pct net profit.

    Uses an exact analytical closed-form derivation:
    Profit = (S - B)*Q - Charges = Target
    Charges = BuyFixed + S*Q*SellRate
    Solving for S:
    S = (Target + B*Q + BuyFixed) / (Q * (1 - SellRate))

    The result is rounded UP to the next valid exchange tick size (0.05 on NSE),
    guaranteeing that real fills at the target limit bid never fall short of the 1% target.
    """
    if qty <= 0 or buy_premium <= 0:
        return {
            "exit_premium": 0.0,
            "gross_move_pct": 0.0,
            "charges": round_trip_charges(0.0, 0.0, 0, rates),
            "net_profit": 0.0,
            "break_even_premium": 0.0,
        }

    want = buy_premium * qty * net_target_pct / 100.0
    gst_mult = 1.0 + rates["gst_pct"] / 100.0
    brokerage_total = 2.0 * rates["brokerage_per_order"]
    txn_rate = rates["exchange_txn_pct"] / 100.0 + rates["sebi_per_crore"] / 1e7

    # Variable rate on sell value
    sell_var_rate = (rates["stt_sell_pct"] / 100.0) + (txn_rate * gst_mult)

    # Fixed charges attributable to buy leg
    buy_fixed = (brokerage_total * gst_mult) + (
        buy_premium * qty * (rates["stamp_buy_pct"] / 100.0 + txn_rate * gst_mult)
    )

    denom = qty * (1.0 - sell_var_rate)
    if denom <= 0:
        raise ValueError("Statutory fee rate exceeds 100% of sell price; cannot compute valid exit.")

    # Target sell price (analytical)
    s_exact = (want + buy_premium * qty + buy_fixed) / denom

    # Break-even sell price (0% profit)
    s_breakeven = (buy_premium * qty + buy_fixed) / denom

    # Round UP to nearest exchange tick (default 0.05 on NSE)
    sell = math.ceil(round(s_exact, 6) / tick_size) * tick_size
    sell = round(sell, 4)

    charges = round_trip_charges(buy_premium, sell, qty, rates)
    net_profit = (sell - buy_premium) * qty - charges["total"]

    # In rare floating-point edge cases where rounding is 0.0001 short, bump by 1 tick
    if net_profit < want - 1e-4:
        sell = round(sell + tick_size, 4)
        charges = round_trip_charges(buy_premium, sell, qty, rates)
        net_profit = (sell - buy_premium) * qty - charges["total"]

    gross_move_pct = (sell / buy_premium - 1.0) * 100.0
    be_tick = math.ceil(round(s_breakeven, 6) / tick_size) * tick_size

    return {
        "exit_premium": round(sell, 2),
        "gross_move_pct": round(gross_move_pct, 2),
        "charges": charges,
        "net_profit": round(net_profit, 2),
        "break_even_premium": round(be_tick, 2),
        "target_profit_required": round(want, 2),
    }
