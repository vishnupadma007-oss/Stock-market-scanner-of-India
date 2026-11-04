"""Forecast agent: how far is a reversal likely to go today?

Reversal trades usually travel back towards one of two levels: the day's VWAP (the average
price everyone paid today) or a 38.2% retracement of the day's move. The nearer of the two
that is still ahead of the price is the forecast. If that is closer than the move the option
needs to reach its target, the trade is not worth taking; if it is further, the target can be
set above the minimum 1%.
"""
import pandas as pd

from .indicators import vwap

RETRACE = 0.382


def reversal_target(intraday: pd.DataFrame, prev_close: float, side: str) -> dict:
    day = intraday[intraday.index.date == intraday.index[-1].date()]
    if day.empty:
        return {"level": None, "move": 0.0, "basis": "no candles today"}
    price = float(day["Close"].iloc[-1])
    v = float(vwap(intraday).iloc[-1])
    if side == "gainer":  # betting on a fall back from the high
        extreme = float(day["High"].max())
        retrace = extreme - RETRACE * (extreme - prev_close)
        levels = {"VWAP": v, "38% retracement": retrace}
        ahead = {k: lv for k, lv in levels.items() if lv < price}
        pick = max(ahead.items(), key=lambda kv: kv[1]) if ahead else None
    else:  # betting on a bounce off the low
        extreme = float(day["Low"].min())
        retrace = extreme + RETRACE * (prev_close - extreme)
        levels = {"VWAP": v, "38% retracement": retrace}
        ahead = {k: lv for k, lv in levels.items() if lv > price}
        pick = min(ahead.items(), key=lambda kv: kv[1]) if ahead else None
    if pick is None:
        return {"level": None, "move": 0.0, "price": price, "vwap": v, "retracement": retrace,
                "basis": "price is already past VWAP and the 38% retracement: the reversal has mostly happened"}
    return {"level": pick[1], "move": abs(price - pick[1]), "price": price, "vwap": v,
            "retracement": retrace, "basis": pick[0]}
