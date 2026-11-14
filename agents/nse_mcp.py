"""NSE's own MCP servers, called straight from Python (no login, no Claude credits).

- Bhavcopy server (`BHAVCOPY_URL`): official NSE daily prices for ~5,000 stocks, 5 years, plus index
  history, market mood/breadth, corporate actions. Prices are NOT adjusted for splits/bonuses: check
  `corporate_actions` before using a long history.
- Live server (`LIVE_URL`): live gainers/losers
  (every 5 min) and index values (every minute) - a backup for the NSE website reads.

Usage: python -m agents.nse_mcp tools | history SYMBOL [MONTHS] | mood | live | call TOOL '{"arg": 1}'
"""
import asyncio
import json
import logging
import sys

import pandas as pd

try:
    from mcp.client.session import ClientSession
    from mcp.client.streamable_http import streamable_http_client
except ImportError:  # pragma: no cover
    ClientSession = streamable_http_client = None

BHAVCOPY_URL = "https://mcp.nseindia.in/bhavcopy/cm/mcp"
LIVE_URL = "https://mcp.nseindia.in/cmmkt/mcp"
logging.getLogger("mcp.client.streamable_http").setLevel(logging.ERROR)  # NSE answers "termination 501": harmless


def _parse(result):
    sc = getattr(result, "structured_content", None) or getattr(result, "structuredContent", None)
    if sc:
        return sc
    text = "".join(getattr(c, "text", "") for c in result.content)
    try:
        return json.loads(text)
    except ValueError:
        return text


async def acall(tool: str, args: dict | None = None, url: str = BHAVCOPY_URL, timeout: float = 30):
    """One tool call on an NSE MCP server; returns the parsed JSON."""
    async def go():
        async with streamable_http_client(url) as (read, write):
            async with ClientSession(read, write) as s:
                await s.initialize()
                res = await s.call_tool(tool, args or {})
                if getattr(res, "is_error", None) or getattr(res, "isError", None):
                    raise RuntimeError(f"NSE MCP {tool}: {_parse(res)}")
                return _parse(res)
    return await asyncio.wait_for(go(), timeout)


def call(tool: str, args: dict | None = None, url: str = BHAVCOPY_URL, timeout: float = 30):
    return asyncio.run(acall(tool, args, url, timeout))


def list_tools(url: str = BHAVCOPY_URL) -> list[str]:
    async def go():
        async with streamable_http_client(url) as (read, write):
            async with ClientSession(read, write) as s:
                await s.initialize()
                return [t.name for t in (await s.list_tools()).tools]
    return asyncio.run(go())


def history_frame(rows: list[dict]) -> pd.DataFrame:
    """Bhavcopy rows -> OHLCV frame indexed by date (oldest first), Yahoo-style column names."""
    if not rows:
        return pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    df = df.rename(columns={"open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume"})
    return df.set_index("date").sort_index()[["Open", "High", "Low", "Close", "Volume"]]


def daily_history(symbol: str, months: int = 12) -> pd.DataFrame:
    """Daily OHLCV for `months` (unadjusted), chaining the server's 3-month chunks."""
    rows, end, left = [], "today", months

    async def go():
        nonlocal end, left
        while left > 0:
            chunk = min(3, left)
            data = await acall("get_stock_history", {"symbol": symbol.upper(), "months": chunk, "endDate": end})
            rows.extend(data.get("data", []))
            end, left = data.get("next_end_date"), left - chunk
            if not end:
                break
    asyncio.run(go())
    return history_frame(rows).loc[lambda d: ~d.index.duplicated()]


def live_movers(limit: int = 20) -> dict:
    """Live top gainers/losers across all NSE stocks (refreshed every 5 min; empty outside market hours)."""
    return call("nse_get_market_movers", {"indexName": "", "limit": limit}, LIVE_URL)


def live_quote(symbol: str) -> dict:
    """Live NSE cash quote (LTP, open/high/low, volume), refreshed every minute."""
    return call("cm_get_stock_quote", {"symbol": symbol.upper()}, LIVE_URL)


def _f(d: dict, *keys):
    for k in keys:
        v = d.get(k)
        if v not in (None, "", "-"):
            try:
                return float(str(v).replace(",", ""))
            except ValueError:
                continue
    return None


def parse_quote(q) -> dict | None:
    """A live quote in the spurt engine's shape {price, prev_close, move_pct, volume, vwap}; None if unusable.
    Field names are read defensively (the server's exact names were not published)."""
    if not isinstance(q, dict) or q.get("error"):
        return None
    d = q.get("data") if isinstance(q.get("data"), dict) else q
    price = _f(d, "ltp", "lastPrice", "last_price", "LTP", "last")
    prev = _f(d, "prevClose", "previousClose", "prev_price", "previous_close")
    move = _f(d, "pChange", "perChange", "percChange", "pchange", "changePct", "percentChange")
    if price is None:
        return None
    if move is None and prev:
        move = (price / prev - 1) * 100
    return {"price": price, "prev_close": prev, "move_pct": round(move or 0.0, 2),
            "volume": _f(d, "volume", "totalTradedVolume", "trade_quantity", "tradedVolume") or 0.0,
            "vwap": _f(d, "vwap", "averagePrice", "avgPrice")}


def live_rows(symbols, concurrency: int = 8, timeout: float = 45) -> dict[str, dict]:
    """Live quotes for many stocks over ONE session (backup for NSE's stocks-traded page and INDmoney)."""
    async def go():
        out = {}
        async with streamable_http_client(LIVE_URL) as (read, write):
            async with ClientSession(read, write) as s:
                await s.initialize()
                sem = asyncio.Semaphore(concurrency)

                async def one(sym):
                    async with sem:
                        try:
                            r = parse_quote(_parse(await s.call_tool("cm_get_stock_quote", {"symbol": sym})))
                            if r:
                                out[sym] = r
                        except Exception:
                            pass
                await asyncio.gather(*(one(x) for x in symbols))
        return out
    return asyncio.run(asyncio.wait_for(go(), timeout))


def nifty_move() -> float | None:
    """Nifty 50's % change today from NSE's live index feed (None when unavailable)."""
    try:
        q = live_index("NIFTY 50")
    except Exception:
        return None
    return _f(q if isinstance(q, dict) else {}, "percChange", "pChange", "changePct", "perChange")


def live_index(name: str = "NIFTY 50") -> dict:
    return call("cm_get_index_quote", {"indexName": name}, LIVE_URL)


def market_mood(date: str = "today") -> dict:
    return call("get_market_mood", {"date": date})


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "tools"
    if cmd == "tools":
        print(list_tools())
    elif cmd == "history":
        print(daily_history(sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 3).tail(10))
    elif cmd == "live":
        print(json.dumps(live_movers(5), indent=1)[:3000])
    elif cmd == "mood":
        print(json.dumps(market_mood(), indent=1)[:3000])
    elif cmd == "call":
        print(json.dumps(call(sys.argv[2], json.loads(sys.argv[3]) if len(sys.argv) > 3 else {}), indent=1)[:5000])
