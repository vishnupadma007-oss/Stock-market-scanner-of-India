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


def snapshot(symbols):
    """{symbol: indicators}; symbols that fail are reported and skipped."""
    out = {}
    for sym in symbols:
        try:
            out[sym] = indicators(fetch_history(sym))
        except Exception as e:
            print(f"   ⚠️  {sym}: {e}")
    return out
