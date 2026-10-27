"""Options agent: picks the contract (CE for losers, PE for gainers) and calculates Greeks.

Premiums are calculated using an exact Black-Scholes model with Greeks (Delta, Gamma,
Theta per day, Vega) from historical or implied volatility, plus a fast hybrid
Newton-Raphson / bisection Implied Volatility (IV) solver for live option chain quotes.

NSE Stock options specifications:
- Expiry: Last Tuesday of the contract month (moved to previous trading day if holiday).
- ITM1 strike shift for high delta and lower time decay.
- Real option chain bid/ask pricing preferred when live data exists.
"""
import calendar
import math
from datetime import date, timedelta

from .holidays import previous_trading_day


class BSResult(tuple):
    """Tuple subclass returning (price, delta) for backward compatibility, plus Greeks attributes."""
    def __new__(cls, price: float, delta: float, gamma: float = 0.0, theta: float = 0.0, vega: float = 0.0):
        instance = super().__new__(cls, (price, delta))
        instance.price = price
        instance.delta = delta
        instance.gamma = gamma
        instance.theta = theta  # Theta per calendar day
        instance.vega = vega    # Vega per 1% change in IV
        return instance


def strike_step(price: float) -> float:
    """Returns the NSE strike interval step for a given stock price."""
    for limit, step in ((100, 1), (250, 2.5), (500, 5), (1000, 10), (2500, 20), (5000, 50)):
        if price < limit:
            return float(step)
    return 100.0


def last_tuesday(year: int, month: int) -> date:
    """Finds the last Tuesday of the given year and month."""
    d = date(year, month, calendar.monthrange(year, month)[1])
    return d - timedelta(days=(d.weekday() - 1) % 7)


def monthly_expiry(today: date, min_days: int) -> date:
    """NSE stock options expire on the last Tuesday of the month (moved a day earlier on holidays)."""
    exp = previous_trading_day(last_tuesday(today.year, today.month))
    if (exp - today).days < min_days:
        y, m = (today.year + 1, 1) if today.month == 12 else (today.year, today.month + 1)
        exp = previous_trading_day(last_tuesday(y, m))
    return exp


def _ncdf(x: float) -> float:
    """Standard Normal Cumulative Distribution Function."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _npdf(x: float) -> float:
    """Standard Normal Probability Density Function."""
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def black_scholes(spot: float, strike: float, years: float, rate: float, vol: float, is_call: bool) -> BSResult:
    """Black-Scholes pricing with full Greeks: Delta, Gamma, Theta (per day), Vega (per 1%)."""
    years = max(years, 1.0 / 365.0)
    vol = max(vol, 0.01)
    spot = max(spot, 0.01)
    strike = max(strike, 0.01)

    sqrt_t = math.sqrt(years)
    d1 = (math.log(spot / strike) + (rate + 0.5 * vol * vol) * years) / (vol * sqrt_t)
    d2 = d1 - vol * sqrt_t

    df = math.exp(-rate * years)
    pdf_d1 = _npdf(d1)

    gamma = pdf_d1 / (spot * vol * sqrt_t)
    vega = (spot * sqrt_t * pdf_d1) / 100.0  # per 1% change in vol

    if is_call:
        price = spot * _ncdf(d1) - strike * df * _ncdf(d2)
        delta = _ncdf(d1)
        theta_annual = -(spot * pdf_d1 * vol) / (2.0 * sqrt_t) - rate * strike * df * _ncdf(d2)
    else:
        price = strike * df * _ncdf(-d2) - spot * _ncdf(-d1)
        delta = _ncdf(d1) - 1.0
        theta_annual = -(spot * pdf_d1 * vol) / (2.0 * sqrt_t) + rate * strike * df * _ncdf(-d2)

    theta_day = theta_annual / 365.0
    return BSResult(max(price, 0.0), delta, gamma=gamma, theta=theta_day, vega=vega)


def implied_volatility(market_price: float, spot: float, strike: float, years: float,
                       rate: float = 0.065, is_call: bool = True) -> float:
    """Inverts Black-Scholes to find Implied Volatility (IV) from a live option market price.
    Uses bounded Newton-Raphson with bisection fallback for guaranteed convergence.
    """
    if market_price <= 0 or spot <= 0 or strike <= 0:
        return 0.30
    years = max(years, 1.0 / 365.0)
    df = math.exp(-rate * years)
    intrinsic = max(0.0, (spot - strike * df) if is_call else (strike * df - spot))
    if market_price <= intrinsic + 1e-4:
        return 0.05

    lo, hi = 0.01, 3.00
    # Brenner-Subrahmanyam initial guess
    vol = min(max(math.sqrt(2.0 * math.pi / years) * (market_price / spot), 0.10), 1.50)

    for _ in range(25):
        bs = black_scholes(spot, strike, years, rate, vol, is_call)
        diff = bs.price - market_price
        if abs(diff) < 1e-4:
            return round(vol, 4)
        if diff > 0:
            hi = vol
        else:
            lo = vol
        vega_raw = bs.vega * 100.0  # dPrice / dVol
        if vega_raw > 1e-5:
            nxt = vol - diff / vega_raw
            vol = nxt if lo < nxt < hi else 0.5 * (lo + hi)
        else:
            vol = 0.5 * (lo + hi)
    return round(vol, 4)


def suggest_contract(symbol: str, spot: float, side: str, hist_vol: float, lot: int | None,
                     cfg: dict, today: date) -> dict:
    """Selects the option contract and calculates theoretical premium, Greeks, and expiry."""
    is_call = side == "loser"
    step = strike_step(spot)
    atm = round(spot / step) * step
    itm_shift = step if cfg["strike_choice"] == "ITM1" else 0.0
    strike = atm - itm_shift if is_call else atm + itm_shift

    expiry = monthly_expiry(today, cfg["min_days_to_expiry"])
    days_to_expiry = max((expiry - today).days, 1)
    vol = max(hist_vol * 1.15, 0.20)  # Implied volatility typically trades at premium over historical

    bs = black_scholes(spot, strike, days_to_expiry / 365.0, cfg["risk_free_rate"], vol, is_call)
    premium = max(round(bs.price * 20.0) / 20.0, 0.05)  # round to nearest NSE 0.05 tick

    opt_type = "CE" if is_call else "PE"
    contract_name = f"{symbol} {expiry:%d%b%y}".upper() + f" {strike:g} {opt_type}"

    return {
        "contract": contract_name,
        "type": opt_type,
        "strike": strike,
        "expiry": expiry,
        "days_to_expiry": days_to_expiry,
        "est_premium": premium,
        "delta": round(bs.delta, 4),
        "gamma": round(bs.gamma, 6),
        "theta_day": round(bs.theta, 3),
        "vega": round(bs.vega, 3),
        "iv_used": round(vol, 4),
        "lot_size": lot,
    }
