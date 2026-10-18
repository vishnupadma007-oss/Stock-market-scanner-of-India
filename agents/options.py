"""Options agent: picks the contract (CE for losers, PE for gainers) and estimates its premium.

Premiums here are Black-Scholes ESTIMATES from historical volatility, because free live
option chains are not reliable. Always check the real premium in your broker app.
"""
import calendar
import math
from datetime import date, timedelta


def strike_step(price: float) -> float:
    for limit, step in ((100, 1), (250, 2.5), (500, 5), (1000, 10), (2500, 20), (5000, 50)):
        if price < limit:
            return step
    return 100


def last_tuesday(year: int, month: int) -> date:
    d = date(year, month, calendar.monthrange(year, month)[1])
    return d - timedelta(days=(d.weekday() - 1) % 7)


def monthly_expiry(today: date, min_days: int) -> date:
    """NSE stock options expire on the last Tuesday of the month (moved a day earlier on holidays)."""
    exp = last_tuesday(today.year, today.month)
    if (exp - today).days < min_days:
        y, m = (today.year + 1, 1) if today.month == 12 else (today.year, today.month + 1)
        exp = last_tuesday(y, m)
    return exp


def _ncdf(x: float) -> float:
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def black_scholes(spot, strike, years, rate, vol, is_call) -> tuple[float, float]:
    years = max(years, 1 / 365)
    d1 = (math.log(spot / strike) + (rate + vol ** 2 / 2) * years) / (vol * math.sqrt(years))
    d2 = d1 - vol * math.sqrt(years)
    if is_call:
        return spot * _ncdf(d1) - strike * math.exp(-rate * years) * _ncdf(d2), _ncdf(d1)
    return strike * math.exp(-rate * years) * _ncdf(-d2) - spot * _ncdf(-d1), _ncdf(d1) - 1


def suggest_contract(symbol: str, spot: float, side: str, hist_vol: float, lot: int | None,
                     cfg: dict, today: date) -> dict:
    is_call = side == "loser"
    step = strike_step(spot)
    atm = round(spot / step) * step
    itm_shift = step if cfg["strike_choice"] == "ITM1" else 0
    strike = atm - itm_shift if is_call else atm + itm_shift
    expiry = monthly_expiry(today, cfg["min_days_to_expiry"])
    vol = max(hist_vol * 1.15, 0.20)  # implied vol usually trades above historical
    premium, delta = black_scholes(spot, strike, (expiry - today).days / 365,
                                   cfg["risk_free_rate"], vol, is_call)
    premium = max(round(premium * 20) / 20, 0.05)
    return {
        "contract": f"{symbol} {expiry:%d%b%y}".upper() + f" {strike:g} {'CE' if is_call else 'PE'}",
        "type": "CE" if is_call else "PE", "strike": strike, "expiry": expiry,
        "days_to_expiry": (expiry - today).days, "est_premium": premium,
        "delta": delta, "iv_used": vol, "lot_size": lot,
    }
