"""Candlestick Patterns agent: names the classic Japanese candle patterns on the last 1-3 candles.

Single candles: hammer, hanging man, inverted hammer, shooting star, bullish/bearish marubozu, doji.
Two candles:    bullish/bearish engulfing, piercing line, dark cloud cover, bullish/bearish harami,
                tweezer bottom/top.
Three candles:  morning star, evening star, three white soldiers, three black crows.

Reversal patterns only count after a move into them (a hammer needs a fall before it), using the
6 candles before the pattern. Each pattern is +1 (bullish) or -1 (bearish); doji is 0 (indecision).

Studies of candle patterns on liquid stocks find little edge after costs (e.g. Duvinage et al.,
83 rules on Dow stocks, 5-minute bars). So this agent starts in observe mode: its patterns are
shown on signals and logged, and `candles.points` in config.yaml stays 0 until our own data
(`python -m agents.candles test`) shows they help.

    python -m agents.candles test     # do the patterns predict the next 30 min on our 60-day data?
"""
import pandas as pd

LOOKBACK = 6  # candles before the pattern that set the trend it reverses


def _parts(c: pd.Series) -> dict:
    o, h, l, cl = float(c["Open"]), float(c["High"]), float(c["Low"]), float(c["Close"])
    rng = max(h - l, 1e-9)
    return {"o": o, "h": h, "l": l, "c": cl, "rng": rng, "body": abs(cl - o), "up": cl > o, "down": cl < o,
            "upper": h - max(o, cl), "lower": min(o, cl) - l, "mid": (o + cl) / 2}


def detect(df: pd.DataFrame) -> list[tuple[str, int]]:
    """Patterns completed on the last candle of `df` (5-minute OHLC): [(name, +1/-1/0), ...]."""
    if len(df) < LOOKBACK + 3:
        return []
    a, b, c = (_parts(df.iloc[i]) for i in (-3, -2, -1))
    before = df["Close"].iloc[-(LOOKBACK + 1):-1]
    trend = (float(before.iloc[-1]) - float(before.iloc[0])) / float(before.iloc[0]) * 100
    fell, rose = trend <= -0.3, trend >= 0.3
    avg_body = float((df["Close"] - df["Open"]).abs().iloc[-(LOOKBACK + 1):-1].mean()) or 1e-9
    big = lambda p: p["body"] >= 1.2 * avg_body  # noqa: E731
    small = lambda p: p["body"] <= 0.3 * p["rng"]  # noqa: E731
    out = []

    def add(cond, name, d):
        if cond:
            out.append((name, d))

    # Single candle
    long_lower = c["lower"] >= 2 * c["body"] and c["upper"] <= 0.3 * c["rng"] and c["body"] > 0
    long_upper = c["upper"] >= 2 * c["body"] and c["lower"] <= 0.3 * c["rng"] and c["body"] > 0
    add(long_lower and fell, "Hammer", 1)
    add(long_lower and rose, "Hanging man", -1)
    add(long_upper and fell, "Inverted hammer", 1)
    add(long_upper and rose, "Shooting star", -1)
    add(c["body"] >= 0.9 * c["rng"] and big(c) and c["up"], "Bullish marubozu", 1)
    add(c["body"] >= 0.9 * c["rng"] and big(c) and c["down"], "Bearish marubozu", -1)
    add(c["body"] <= 0.1 * c["rng"] and (fell or rose), "Doji", 0)

    # Two candles
    add(fell and b["down"] and c["up"] and c["o"] <= b["c"] and c["c"] >= b["o"] and c["body"] > b["body"],
        "Bullish engulfing", 1)
    add(rose and b["up"] and c["down"] and c["o"] >= b["c"] and c["c"] <= b["o"] and c["body"] > b["body"],
        "Bearish engulfing", -1)
    add(fell and b["down"] and big(b) and c["up"] and c["o"] < b["c"] and b["mid"] < c["c"] < b["o"],
        "Piercing line", 1)
    add(rose and b["up"] and big(b) and c["down"] and c["o"] > b["c"] and b["o"] < c["c"] < b["mid"],
        "Dark cloud cover", -1)
    add(fell and b["down"] and big(b) and c["up"] and max(c["o"], c["c"]) <= b["o"] and min(c["o"], c["c"]) >= b["c"]
        and c["body"] < 0.6 * b["body"], "Bullish harami", 1)
    add(rose and b["up"] and big(b) and c["down"] and max(c["o"], c["c"]) <= b["c"] and min(c["o"], c["c"]) >= b["o"]
        and c["body"] < 0.6 * b["body"], "Bearish harami", -1)
    add(fell and b["down"] and c["up"] and abs(b["l"] - c["l"]) <= 0.001 * c["c"], "Tweezer bottom", 1)
    add(rose and b["up"] and c["down"] and abs(b["h"] - c["h"]) <= 0.001 * c["c"], "Tweezer top", -1)

    # Three candles
    add(fell and a["down"] and big(a) and small(b) and c["up"] and c["c"] > a["mid"], "Morning star", 1)
    add(rose and a["up"] and big(a) and small(b) and c["down"] and c["c"] < a["mid"], "Evening star", -1)
    add(all(p["up"] and p["body"] >= 0.5 * p["rng"] for p in (a, b, c)) and a["c"] < b["c"] < c["c"]
        and b["o"] > a["o"] and c["o"] > b["o"], "Three white soldiers", 1)
    add(all(p["down"] and p["body"] >= 0.5 * p["rng"] for p in (a, b, c)) and a["c"] > b["c"] > c["c"]
        and b["o"] < a["o"] and c["o"] < b["o"], "Three black crows", -1)
    return out


def recent(df: pd.DataFrame, candles: int = 3) -> list[tuple[str, int]]:
    """Patterns completed on any of the last `candles` candles (newest first, no repeats)."""
    seen, out = set(), []
    for k in range(candles):
        for name, d in detect(df.iloc[:len(df) - k] if k else df):
            if name not in seen:
                seen.add(name)
                out.append((name, d))
    return out


def as_extra(df: pd.DataFrame, side: str, cfg: dict) -> dict:
    """Decision extra. A PUT on a gainer wants bearish patterns, a CALL on a loser bullish ones.
    Points come from `candles.points` in config (0 = observe mode: notes only)."""
    pts = int((cfg.get("candles") or {}).get("points", 0))
    want = -1 if side == "gainer" else 1
    found = recent(df)
    agree = [n for n, d in found if d == want]
    against = [n for n, d in found if d == -want]
    notes = []
    if agree:
        notes.append(f"Candles: {', '.join(agree)} (supports the reversal)")
    if against:
        notes.append(f"Candles: {', '.join(against)} (against the reversal)")
    return {"points": pts * (len(agree) > 0) - pts * (len(against) > 0), "notes": notes,
            "patterns": [n for n, _ in found]}


def test(intra: pd.DataFrame, horizon: int = 6) -> pd.DataFrame:
    """For every 5-minute candle of every stock: which patterns completed, and the move over the
    next `horizon` candles. Returns per pattern: count, share that went the pattern's way, average
    move in the pattern's direction (%), against the same numbers for all candles."""
    rows = []
    for tk in intra.columns.get_level_values(0).unique():
        df = intra[tk].dropna(subset=["Close"])
        for day, g in df.groupby(df.index.date):
            if len(g) < LOOKBACK + 3 + horizon:
                continue
            closes = g["Close"].values
            for i in range(LOOKBACK + 3, len(g) - horizon):
                fwd = (closes[i - 1 + horizon] / closes[i - 1] - 1) * 100
                for name, d in detect(g.iloc[:i]):
                    if d:
                        rows.append({"pattern": name, "dir": d, "fwd": fwd})
                rows.append({"pattern": "(any candle, up)", "dir": 1, "fwd": fwd})
    t = pd.DataFrame(rows)
    t["right"] = t["fwd"] * t["dir"] > 0
    t["move"] = t["fwd"] * t["dir"]
    return t.groupby("pattern").agg(count=("move", "size"), right=("right", "mean"), avg_move=("move", "mean")) \
        .sort_values("count", ascending=False).round(3)


def main() -> None:
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        import yfinance as yf
        from .config import load_config
        tickers = [s + ".NS" for s in load_config()["universe"]]
        if len(sys.argv) > 2:
            intra = pd.read_pickle(sys.argv[2])
        else:
            intra = yf.download(tickers, period="60d", interval="5m", group_by="ticker", progress=False,
                                auto_adjust=False)
        intra = intra[[c for c in intra.columns if c[0] in tickers]]
        print(test(intra).to_string())


if __name__ == "__main__":
    main()
