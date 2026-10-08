"""Daily price history for NSE stocks (Yahoo Finance) and the indicators the desk looks at."""

import pandas as pd


def fetch_history(symbol, period="1y"):
    import yfinance as yf  # imported here so the rest of the agent loads without it

    df = yf.Ticker(f"{symbol}.NS").history(period=period, interval="1d", auto_adjust=False)
    if df.empty:
        raise ValueError(f"No price data for {symbol} on NSE")
    return df[["Open", "High", "Low", "Close", "Volume"]]


def indicators(df):
    """Summary numbers for one stock from its daily OHLCV frame."""
    close, high, low = df["Close"], df["High"], df["Low"]
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
    rsi = 100 - 100 / (1 + gain / loss.replace(0, 1e-9))
    prev_close = close.shift()
    true_range = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    atr = true_range.rolling(14).mean()

    last = float(close.iloc[-1])

    def pct(n):
        return round(100 * (last / float(close.iloc[-n - 1]) - 1), 2) if len(close) > n else None

    return {
        "last_price": round(last, 2),
        "date": str(df.index[-1].date()),
        "change_1d_pct": pct(1),
        "change_1m_pct": pct(21),
        "change_6m_pct": pct(126),
        "sma20": round(float(close.rolling(20).mean().iloc[-1]), 2),
        "sma50": round(float(close.rolling(50).mean().iloc[-1]), 2),
        "sma200": round(float(close.rolling(200).mean().iloc[-1]), 2) if len(close) >= 200 else None,
        "rsi14": round(float(rsi.iloc[-1]), 1),
        "atr14": round(float(atr.iloc[-1]), 2),
        "high_52w": round(float(high.max()), 2),
        "low_52w": round(float(low.min()), 2),
        "avg_volume_20d": int(df["Volume"].tail(20).mean()),
        "volume_vs_avg": round(float(df["Volume"].iloc[-1] / max(df["Volume"].tail(20).mean(), 1)), 2),
    }


def fetch_intraday(symbol):
    import yfinance as yf

    df = yf.Ticker(f"{symbol}.NS").history(period="5d", interval="5m")
    if df.empty:
        raise ValueError(f"No intraday data for {symbol}")
    return df[["Open", "High", "Low", "Close", "Volume"]]


def intraday_indicators(df):
    """Today's session from 5-minute bars: gap, opening range, VWAP, high/low."""
    days = sorted(set(df.index.date))
    today = df[df.index.date == days[-1]]
    prev = df[df.index.date == days[-2]] if len(days) > 1 else None
    typical = (today["High"] + today["Low"] + today["Close"]) / 3
    vwap = float((typical * today["Volume"]).sum() / max(today["Volume"].sum(), 1))
    opening = today.head(3)  # first 15 minutes
    last = float(today["Close"].iloc[-1])
    out = {
        "session_date": str(days[-1]),
        "as_of": today.index[-1].strftime("%H:%M"),
        "last_price": round(last, 2),
        "day_open": round(float(today["Open"].iloc[0]), 2),
        "day_high": round(float(today["High"].max()), 2),
        "day_low": round(float(today["Low"].min()), 2),
        "vwap": round(vwap, 2),
        "pct_from_vwap": round(100 * (last / vwap - 1), 2),
        "opening_range_high": round(float(opening["High"].max()), 2),
        "opening_range_low": round(float(opening["Low"].min()), 2),
        "last_5_bars_close": [round(float(x), 2) for x in today["Close"].tail(5)],
    }
    if prev is not None and len(prev):
        prev_close = float(prev["Close"].iloc[-1])
        out["prev_close"] = round(prev_close, 2)
        out["gap_pct"] = round(100 * (out["day_open"] / prev_close - 1), 2)
        out["change_today_pct"] = round(100 * (last / prev_close - 1), 2)
    return out


def snapshot(symbols, intraday=False):
    """{symbol: indicators}; symbols that fail are reported and skipped. With intraday=True the
    daily picture is joined by today's 5-minute session, and last_price is the latest 5-minute close
    (Yahoo's NSE feed can lag; live trading uses the broker's price instead)."""
    out = {}
    for sym in symbols:
        try:
            out[sym] = indicators(fetch_history(sym))
            if intraday:
                out[sym]["today"] = intraday_indicators(fetch_intraday(sym))
                out[sym]["last_price"] = out[sym]["today"]["last_price"]
        except Exception as e:
            print(f"   ⚠️  {sym}: {e}")
    return out
