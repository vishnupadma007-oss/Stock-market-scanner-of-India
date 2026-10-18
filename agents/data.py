"""Market data. Uses Yahoo Finance (free, NSE symbols with .NS suffix)."""
import io

import pandas as pd
import requests
import yfinance as yf

NIFTY = "^NSEI"
SENSEX = "^BSESN"
INDIA_VIX = "^INDIAVIX"


def yahoo_symbol(symbol: str) -> str:
    return symbol if symbol.startswith("^") else f"{symbol}.NS"


def daily_bars(symbols: list[str], period: str = "6mo") -> dict[str, pd.DataFrame]:
    tickers = [yahoo_symbol(s) for s in symbols]
    raw = yf.download(tickers, period=period, interval="1d", group_by="ticker",
                      auto_adjust=False, progress=False, threads=True)
    out = {}
    for sym, tk in zip(symbols, tickers):
        try:
            df = raw[tk].dropna(subset=["Close"])
        except KeyError:
            continue
        if len(df) >= 25:
            out[sym] = df
    return out


def intraday_bars(symbol: str, interval: str = "5m", period: str = "5d") -> pd.DataFrame:
    df = yf.Ticker(yahoo_symbol(symbol)).history(period=period, interval=interval)
    if df.empty:
        return df
    df.index = df.index.tz_convert("Asia/Kolkata")
    return df[["Open", "High", "Low", "Close", "Volume"]]


def nse_lot_sizes() -> dict[str, int]:
    """Current F&O lot sizes from NSE's public file. Returns {} if NSE is unreachable."""
    url = "https://nsearchives.nseindia.com/content/fo/fo_mktlots.csv"
    try:
        resp = requests.get(url, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        df = pd.read_csv(io.StringIO(resp.text))
    except Exception:
        return {}
    df.columns = [c.strip().upper() for c in df.columns]
    lots = {}
    month_cols = [c for c in df.columns if c not in ("UNDERLYING", "SYMBOL")]
    for _, row in df.iterrows():
        sym = str(row.get("SYMBOL", "")).strip()
        for col in month_cols:
            try:
                lots[sym] = int(str(row[col]).strip())
                break
            except ValueError:
                continue
    return lots
