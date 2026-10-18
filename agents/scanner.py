"""Scanner agent: finds today's top gainers and losers among liquid F&O stocks."""
import pandas as pd

from .indicators import atr, rsi


def _pct(close: pd.Series, days: int) -> float:
    return float(close.iloc[-1] / close.iloc[-1 - days] - 1) * 100 if len(close) > days else 0.0


def stock_profile(df: pd.DataFrame) -> dict:
    close = df["Close"]
    a = float(atr(df).iloc[-1])
    sma20 = float(close.rolling(20).mean().iloc[-1])
    turnover = (df["Close"] * df["Volume"]).tail(20).mean() / 1e7
    return {
        "ltp": float(close.iloc[-1]),
        "chg_1d": _pct(close, 1), "chg_1w": _pct(close, 5), "chg_1m": _pct(close, 21),
        "rsi_daily": float(rsi(close).iloc[-1]),
        "atr_pct": a / float(close.iloc[-1]) * 100,
        "dist_sma20_atr": (float(close.iloc[-1]) - sma20) / a if a else 0.0,
        "turnover_cr": float(turnover),
    }


def scan(daily: dict[str, pd.DataFrame], cfg: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows = [{"symbol": s, **stock_profile(df)} for s, df in daily.items()]
    table = pd.DataFrame(rows)
    if table.empty:
        return table, table
    table = table[table["turnover_cr"] >= cfg["min_turnover_cr"]]
    gainers = table[table["chg_1d"] >= cfg["min_move_pct"]].nlargest(cfg["top_n"], "chg_1d")
    losers = table[table["chg_1d"] <= -cfg["min_move_pct"]].nsmallest(cfg["top_n"], "chg_1d")
    return gainers.reset_index(drop=True), losers.reset_index(drop=True)
