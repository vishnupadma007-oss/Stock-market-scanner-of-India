"""Fast prices for the reflex engine: one cheap call for every symbol, many times a minute."""

import datetime as dt
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")


class YahooFeed:
    """1-minute bars from Yahoo Finance (about a minute behind the market). Used for paper trading."""

    name = "Yahoo 1-minute bars"
    default_tick = 30  # seconds; a new bar only arrives once a minute

    def prices(self, symbols):
        """({symbol: last price}, time of the latest bar)."""
        import yfinance as yf

        df = yf.download(" ".join(f"{s}.NS" for s in symbols), period="1d", interval="1m",
                         progress=False, group_by="ticker", auto_adjust=False)
        out, latest = {}, None
        for s in symbols:
            try:
                close = df[f"{s}.NS"]["Close"].dropna()  # group_by="ticker" nests columns even for one symbol
            except KeyError:
                continue
            if len(close):
                out[s] = round(float(close.iloc[-1]), 2)
                t = close.index[-1].tz_convert(IST)
                latest = max(latest, t) if latest else t
        return out, latest


class BrokerFeed:
    """Live last-traded prices from the broker (Zerodha Kite: one request covers every symbol)."""

    name = "broker live prices"
    default_tick = 3

    def __init__(self, broker):
        self.broker = broker

    def prices(self, symbols):
        return self.broker.ltp(symbols), dt.datetime.now(IST)
