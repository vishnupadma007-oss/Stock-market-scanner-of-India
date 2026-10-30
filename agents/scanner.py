"""Scanner agent: finds today's top gainers and losers among liquid F&O stocks."""
import pandas as pd

from .indicators import atr, rsi


def _pct(close: pd.Series, days: int) -> float:
    if len(close) <= days:
        return 0.0
    val_prev = float(close.iloc[-1 - days])
    if val_prev <= 0:
        return 0.0
    return float(close.iloc[-1] / val_prev - 1.0) * 100.0


def stock_profile(df: pd.DataFrame) -> dict:
    if df.empty:
        return {
            "ltp": 0.0, "chg_1d": 0.0, "chg_1w": 0.0, "chg_1m": 0.0,
            "rsi_daily": 50.0, "atr_pct": 0.0, "dist_sma20_atr": 0.0, "turnover_cr": 0.0,
        }

    close = df["Close"]
    a = float(atr(df).iloc[-1]) if len(df) >= 2 else 0.0
    ltp = float(close.iloc[-1])
    roll_len = min(len(close), 20)
    sma20 = float(close.tail(roll_len).mean()) if roll_len > 0 else ltp

    vol = df["Volume"].fillna(0.0) if "Volume" in df else pd.Series(0.0, index=df.index)
    turnover = (close * vol).tail(roll_len).mean() / 1e7 if roll_len > 0 else 0.0

    return {
        "ltp": ltp,
        "chg_1d": _pct(close, 1),
        "chg_1w": _pct(close, 5),
        "chg_1m": _pct(close, 21),
        "rsi_daily": float(rsi(close).iloc[-1]) if len(close) >= 2 else 50.0,
        "atr_pct": (a / ltp * 100.0) if ltp > 0 else 0.0,
        "dist_sma20_atr": ((ltp - sma20) / a) if a > 0 else 0.0,
        "turnover_cr": float(turnover),
    }


def scan(daily: dict[str, pd.DataFrame], cfg: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows = [{"symbol": s, **stock_profile(df)} for s, df in daily.items() if not df.empty]
    table = pd.DataFrame(rows)
    if table.empty:
        return table, table
    table = table[table["turnover_cr"] >= cfg["min_turnover_cr"]]
    gainers = table[table["chg_1d"] >= cfg["min_move_pct"]].nlargest(cfg["top_n"], "chg_1d")
    losers = table[table["chg_1d"] <= -cfg["min_move_pct"]].nsmallest(cfg["top_n"], "chg_1d")
    return gainers.reset_index(drop=True), losers.reset_index(drop=True)
