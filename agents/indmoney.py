"""INDmoney market data for the Python agents, through INDmoney's official MCP server.

The script talks to the same server Claude uses, so watching the market costs no Claude
credits. It needs a one-time login from you:

    python -m agents.indmoney login            # prints a link: open it, log in to INDmoney
    python -m agents.indmoney finish "<URL>"   # paste the address your browser ended on
    python -m agents.indmoney test             # checks the connection

After that the access token renews itself. The token file lives outside the repo and is
never committed. Access is read-only (market:read and portfolio:read; INDmoney requires both,
but this module only calls market-data tools).
"""
import asyncio
import contextlib
import base64
import hashlib
import json
import os
import re
import secrets
import sys
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

import httpx2
import pandas as pd
try:
    from mcp.client.session import ClientSession
    from mcp.client.streamable_http import streamable_http_client
except ImportError:
    ClientSession = None
    streamable_http_client = None

BASE = "https://mcp.indmoney.com"
MCP_URL = f"{BASE}/mcp"
REDIRECT_URI = "http://localhost:8765/callback"
# INDmoney's server refuses connections without portfolio:read, even for market tools.
# The watcher only calls market-data tools.
SCOPE = "market:read portfolio:read"
TOKEN_FILE = Path(os.environ.get("INDMONEY_TOKEN_FILE", Path.home() / ".config" / "indmoney" / "token.json"))


USAGE_FILE = TOKEN_FILE.parent / "usage.json"
CALL_COST = {"get_indian_stocks_movers": 2}  # INDmoney counts some tools double


def _usage() -> list[list[float]]:
    try:
        rows = json.loads(USAGE_FILE.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return []
    return [r for r in rows if r[0] > time.time() - 3600]


_usage_lock = threading.Lock()  # the scanner and the information thread both record calls


def record_call(tool: str, cost: int | None = None) -> None:
    """Keep a rolling one-hour log of this script's INDmoney calls (survives restarts)."""
    with _usage_lock:
        rows = _usage() + [[time.time(), CALL_COST.get(tool, 1) if cost is None else cost, tool]]
        USAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
        USAGE_FILE.write_text(json.dumps(rows))


def calls_last_hour() -> int:
    return int(sum(row[1] for row in _usage()))  # rows: [time, cost] or [time, cost, tool]


# Even pacing: calls are spread evenly through the hour instead of in bursts. With a budget of
# 450 calls/hour each call waits until 8 seconds after the previous one (16 for a double-cost call).
_pace = {"gap": 3600 / 450, "next": 0.0}


def set_hourly_budget(calls_per_hour: int) -> None:
    _pace["gap"] = 3600 / calls_per_hour


async def _wait_turn(cost: int) -> None:
    now = time.monotonic()
    start = max(now, _pace["next"])
    _pace["next"] = start + cost * _pace["gap"]
    if start > now:
        await asyncio.sleep(start - now)


class LoginRequired(RuntimeError):
    pass


class RateLimited(RuntimeError):
    """INDmoney allows a fixed number of calls per hour across the whole account."""

    def __init__(self, message: str, retry_after: int):
        super().__init__(message)
        self.retry_after = retry_after


# ---------------------------------------------------------------- token handling

def _load() -> dict:
    data = json.loads(TOKEN_FILE.read_text()) if TOKEN_FILE.exists() else {}
    # Allow bootstrapping from environment secrets (e.g. a cloud environment's settings).
    for key in ("client_id", "client_secret", "refresh_token"):
        env = os.environ.get(f"INDMONEY_{key.upper()}")
        if env and not data.get(key):
            data[key] = env
    return data


def _save(data: dict) -> None:
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_FILE.write_text(json.dumps(data, indent=1))
    TOKEN_FILE.chmod(0o600)


def _store_tokens(data: dict, resp: dict) -> None:
    data["access_token"] = resp["access_token"]
    data["expires_at"] = time.time() + int(resp.get("expires_in", 3600))
    if resp.get("refresh_token"):  # servers may rotate refresh tokens
        data["refresh_token"] = resp["refresh_token"]
    _save(data)


def _client_auth(data: dict) -> dict:
    return {"client_id": data["client_id"], "client_secret": data.get("client_secret", "")}


def refresh(data: dict) -> dict:
    if not data.get("refresh_token"):
        raise LoginRequired("Not logged in to INDmoney. Run: python -m agents.indmoney login")
    resp = httpx2.post(f"{BASE}/token", data={"grant_type": "refresh_token",
                                              "refresh_token": data["refresh_token"], **_client_auth(data)},
                       timeout=20)
    if resp.status_code >= 400:
        raise LoginRequired(f"INDmoney login expired ({resp.status_code}). Run the login steps again.")
    _store_tokens(data, resp.json())
    return data


def access_token() -> str:
    data = _load()
    if not data.get("access_token") or data.get("expires_at", 0) < time.time() + 60:
        data = refresh(data)
    return data["access_token"]


def start_login() -> str:
    data = _load()
    if not data.get("client_id") or data.get("client_scope") != SCOPE:
        resp = httpx2.post(f"{BASE}/register", json={
            "client_name": "Stock Market Scanner of India (watcher)",
            "redirect_uris": [REDIRECT_URI],
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"],
            "token_endpoint_auth_method": "client_secret_post",
            "scope": SCOPE,
        }, timeout=20)
        resp.raise_for_status()
        reg = resp.json()
        data["client_id"], data["client_secret"] = reg["client_id"], reg.get("client_secret", "")
        data["client_scope"] = SCOPE
        data.pop("refresh_token", None)
        data.pop("access_token", None)
    verifier = secrets.token_urlsafe(48)
    data["pkce_verifier"], data["state"] = verifier, secrets.token_urlsafe(16)
    _save(data)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    return f"{BASE}/authorize?" + urlencode({
        "response_type": "code", "client_id": data["client_id"], "redirect_uri": REDIRECT_URI,
        "scope": SCOPE, "state": data["state"], "code_challenge": challenge,
        "code_challenge_method": "S256", "resource": MCP_URL,
    })


def finish_login(redirected: str) -> None:
    data = _load()
    query = parse_qs(urlparse(redirected).query)
    code = query.get("code", [redirected.strip()])[0]
    if "state" in query and query["state"][0] != data.get("state"):
        raise RuntimeError("Login link does not match. Run 'login' again and use the newest link.")
    resp = httpx2.post(f"{BASE}/token", data={
        "grant_type": "authorization_code", "code": code, "redirect_uri": REDIRECT_URI,
        "code_verifier": data["pkce_verifier"], "resource": MCP_URL, **_client_auth(data),
    }, timeout=20)
    resp.raise_for_status()
    data.pop("pkce_verifier", None)
    data.pop("state", None)
    _store_tokens(data, resp.json())


# ---------------------------------------------------------------- MCP calls

def _parse(result) -> dict:
    if result.is_error:
        raise RuntimeError(" ".join(getattr(c, "text", "") for c in result.content)[:300])
    payload = result.structured_content
    if payload is None:
        payload = json.loads("".join(getattr(c, "text", "") for c in result.content))
    # The server wraps its JSON in {"result": "<json string>"}.
    if isinstance(payload, dict) and isinstance(payload.get("result"), str):
        payload = json.loads(payload["result"])
    if isinstance(payload, dict) and payload.get("error") == "rate_limit_exceeded":
        raise RateLimited(payload.get("message", "rate limit"), int(payload.get("retry_after_seconds", 600)))
    return payload


class IndMoney:
    """One connection to the INDmoney MCP server: `async with IndMoney() as im: await im.movers(...)`."""

    async def __aenter__(self):
        if ClientSession is None or streamable_http_client is None:
            raise RuntimeError("The 'mcp' package is required to connect to INDmoney. Install via 'pip install mcp>=2.2'.")
        # An exit stack unwinds every layer even when one of them fails, so a failed call
        # surfaces as its real error instead of a "cancel scope" error during cleanup.
        self._stack = contextlib.AsyncExitStack()
        try:
            http = await self._stack.enter_async_context(httpx2.AsyncClient(
                headers={"Authorization": f"Bearer {access_token()}"}, timeout=httpx2.Timeout(30.0, read=60.0)))
            read, write = await self._stack.enter_async_context(streamable_http_client(MCP_URL, http_client=http))
            self._session = await self._stack.enter_async_context(ClientSession(read, write))
            await self._session.initialize()
        except BaseException:
            await self._stack.aclose()
            raise
        return self

    async def __aexit__(self, *exc):
        return await self._stack.__aexit__(*exc)

    async def call(self, tool: str, **args) -> dict:
        # INDmoney charges a details call per instrument asked for (seen 21 Oct: our per-request
        # count read 253 when INDmoney said 500), so count it the same way.
        cost = max(1, len(args.get("ind_keys", []))) if tool == "get_indian_stocks_details" else CALL_COST.get(tool, 1)
        await _wait_turn(cost)
        record_call(tool, cost)
        return _parse(await self._session.call_tool(tool, args))

    async def movers(self, category: str, limit: int = 50) -> list[dict]:
        return (await self.call("get_indian_stocks_movers", category=category, limit=limit))["stocks"]

    async def lookup(self, names: list[str]) -> dict[str, str]:
        rows = await self.call("lookup_ind_keys", names=names)
        return {r["name"]: r["ind_key"] for r in rows if r.get("ind_key")}

    async def candles(self, ind_key: str, interval: str, lookback: str) -> pd.DataFrame:
        rows = (await self.call("get_indian_stocks_ohlc", ind_key=ind_key,
                                interval=interval, lookback=lookback)).get("candles", [])
        return candles_frame(rows)

    async def option_chain(self, ind_key: str, strikes_around_atm: int = 4, expiry: str | None = None) -> dict:
        """Nearest expiry, or `expiry` (one of the chain's expiry_list values, e.g. "20261123")."""
        if expiry:
            return await self.call("get_indian_stocks_option_chain", ind_key=ind_key, use_expiry_date=True,
                                   expiry_date=expiry, strikes_around_atm=strikes_around_atm)
        return await self.call("get_indian_stocks_option_chain", ind_key=ind_key,
                               use_expiry_date=False, strikes_around_atm=strikes_around_atm)

    async def pick_contract(self, ind_key: str, side: str, cfg: dict, today) -> dict | None:
        """This month's contract; in expiry week, next month's when this month's fails the checks
        (too cheap or too wide a bid-ask gap). One extra chain call, only in that case."""
        chain = await self.option_chain(ind_key)
        option = pick_option(chain, side, cfg["strike_choice"])
        fb = cfg.get("expiry_fallback") or {}
        if not needs_next_month(option, chain, today, fb):
            return option
        later = sorted(e for e in chain.get("expiry_list") or [] if e > str(chain.get("selected_expiry")))
        if not later:
            return option
        nxt = pick_option(await self.option_chain(ind_key, expiry=later[0]), side, cfg["strike_choice"])
        # Both months unusable: keep the narrower bid-ask gap (the team's own checks decide after that).
        if nxt is None or (option is not None and _fails(nxt, fb)
                           and (not _fails(option, fb) or option["spread_pct"] <= nxt["spread_pct"])):
            return option
        nxt["rolled_from"] = option["contract"] if option else str(chain.get("selected_expiry"))
        return nxt

    async def quotes(self, ind_keys: list[str], segments: list[str] | None = None) -> dict:
        args = {"ind_keys": ind_keys} | ({"segments": segments} if segments else {})
        return await self.call("get_indian_stocks_details", **args)

    async def day_changes(self, ind_keys: list[str]) -> dict[str, float]:
        """Today's % change for each instrument (the server takes 10 keys per call)."""
        out = {}
        for i in range(0, len(ind_keys), 10):
            data = await self.quotes(ind_keys[i:i + 10])
            out.update({k: v["entity_stats"]["day_change_percentage"] for k, v in data.items()
                        if isinstance(v, dict) and "entity_stats" in v})
        return out

    async def news(self, ind_key: str) -> list[dict]:
        return (await self.quotes([ind_key], ["news"])).get(ind_key, {}).get("news", [])

    async def futures_oi_change(self, symbol: str, expiry) -> float | None:
        """Today's % change in open interest of the stock's futures for this expiry."""
        name = f"{symbol} {expiry:%d %b} Fut"
        rows = await self.call("lookup_ind_keys", names=[name], filter_type="IN_STOCKS_FNO")
        key = next((r["ind_key"] for r in rows if r.get("name", "").upper() == name.upper()), None)
        if not key:
            return None
        stats = (await self.quotes([key])).get(key, {}).get("entity_stats", {})
        return stats.get("open_interest_change")

    async def commodity_keys(self, names: list[str]) -> dict[str, str]:
        """Current MCX futures contract for each commodity name (e.g. "crude oil" -> CRUDEOIL Fut)."""
        rows = await self.call("lookup_ind_keys", names=names, filter_type="IN_COMMODITY")
        today = datetime.now().date()
        keys = {}
        for name in names:
            code = name.replace(" ", "").upper()
            match = next((r for r in rows if r.get("ind_key") and r.get("name", "").upper().endswith(" FUT")
                          and r["name"].upper().startswith(code + " ")), None)
            if match and contract_expiry(match["name"], today) < today:
                # Lookup returned an expired contract (e.g. on the day after expiry): ask for the next one.
                nxt = (today.replace(day=1) + timedelta(days=32)).strftime("%b")
                # Search only offers next month's options then; an option's parent is the future.
                more = await self.call("lookup_ind_keys", names=[f"{code} {nxt}"], filter_type="IN_COMMODITY")
                opt = next((r["ind_key"] for r in more if r.get("ind_key")
                            and r.get("name", "").upper().startswith(code + " ")), None)
                if opt:
                    parent = (await self.quotes([opt])).get(opt, {}).get("entity_basic", {}).get(
                        "underlying_parent_ind_key")
                    if parent:
                        match = {"ind_key": parent, "name": f"{code} {nxt} Fut"}
            if match:
                keys[name] = match["ind_key"]
        return keys

    async def crude_key(self) -> str | None:
        rows = await self.call("lookup_ind_keys", names=["crude oil"], filter_type="IN_COMMODITY")
        return next((r["ind_key"] for r in rows if r.get("ind_key")), None)


def candles_frame(rows: list[dict]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])
    df = pd.DataFrame(rows)
    dt = pd.to_datetime(df["datetime_ist"])
    df.index = dt.dt.tz_localize("Asia/Kolkata") if dt.dt.tz is None else dt.dt.tz_convert("Asia/Kolkata")
    df = df.rename(columns=str.capitalize)[["Open", "High", "Low", "Close", "Volume"]]
    return df.astype(float)


def contract_expiry(name: str, today) -> "date":
    """Expiry from a contract name like 'CRUDEOIL 19 Oct Fut' (year inferred; Dec->Jan rolls over)."""
    m = re.search(r"(\d{1,2}) ([A-Za-z]{3})", name)
    if not m:
        return today
    d = datetime.strptime(f"{m.group(1)} {m.group(2)} {today.year}", "%d %b %Y").date()
    return d.replace(year=d.year + 1) if (today - d).days > 180 else d


def pick_option(chain: dict, side: str, strike_choice: str) -> dict | None:
    """Real contract from the live chain: PE for a gainer, CE for a loser, ATM or one strike ITM."""
    rows = chain.get("option_chain_data") or []
    spot = chain.get("entity_details", {}).get("live_price")
    if not rows or not spot:
        return None
    strikes = sorted(r["strike_price"] for r in rows)
    atm_i = min(range(len(strikes)), key=lambda i: abs(strikes[i] - spot))
    shift = 1 if strike_choice == "ITM1" else 0
    # ITM for a put is above spot, for a call below spot.
    i = min(atm_i + shift, len(strikes) - 1) if side == "gainer" else max(atm_i - shift, 0)
    row = next(r for r in rows if r["strike_price"] == strikes[i])
    leg = row.get("put_data" if side == "gainer" else "call_data") or {}
    bid = float(leg.get("buy_price", leg.get("bp")) or 0)
    ask = float(leg.get("sell_price", leg.get("sp")) or 0)
    if bid <= 0 or ask <= 0 or not leg.get("derivative_id") or not leg.get("slug") \
            or not chain.get("selected_expiry"):
        return None  # strike not quoted on this side, or an incomplete reply
    expiry = pd.to_datetime(chain["selected_expiry"]).date()
    return {
        "contract": f"{leg['slug'].upper()}", "derivative_id": leg["derivative_id"],
        "type": "PE" if side == "gainer" else "CE", "strike": strikes[i], "expiry": expiry,
        "bid": bid, "ask": ask, "ltp": leg.get("current_price"), "est_premium": ask,
        "spread_pct": (ask - bid) / ask * 100, "delta": leg.get("delta") or (-0.5 if side == "gainer" else 0.5),
        "lot_size": leg.get("lot_size"), "oi_tag": row.get("oi_trend_tag"), "spot": spot,
    }


def _fails(option: dict, fb: dict) -> bool:
    return option["ask"] < fb.get("min_premium", 5.0) or option["spread_pct"] > fb.get("max_spread_pct", 2.0)


def needs_next_month(option: dict | None, chain: dict, today, fb: dict) -> bool:
    """Expiry week (within `days` of this month's expiry) and this month's option is unusable:
    not quoted, cheaper than `min_premium`, or a bid-ask gap wider than `max_spread_pct`."""
    if not fb.get("enabled", True) or not chain.get("selected_expiry"):
        return False
    days_left = (pd.to_datetime(str(chain["selected_expiry"])).date() - today).days
    return days_left <= fb.get("days", 7) and (option is None or _fails(option, fb))


def main(argv: list[str]) -> None:
    cmd = argv[1] if len(argv) > 1 else "help"
    if cmd == "login":
        print("Open this link, log in to INDmoney and allow access. Your browser will then try to open\n"
              "a 'localhost' page that does not load - that is expected. Copy that page's full address\n"
              "and run:  python -m agents.indmoney finish \"<address>\"\n")
        print(start_login())
    elif cmd == "finish":
        finish_login(argv[2])
        print(f"Logged in. Token saved to {TOKEN_FILE}")
    elif cmd == "test":
        async def check():
            async with IndMoney() as im:
                top = await im.movers("top-gainers", 3)
                print("Connected. Top gainers:", ", ".join(f"{s['symbol']} {s['change_pct']:+.2f}%" for s in top))
        asyncio.run(check())
    else:
        print(__doc__)


if __name__ == "__main__":
    main(sys.argv)
