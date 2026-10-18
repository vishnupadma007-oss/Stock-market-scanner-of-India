"""INDmoney market data for the Python agents, through INDmoney's official MCP server.

The script talks to the same server Claude uses, so watching the market costs no Claude
credits. It needs a one-time login from you:

    python -m agents.indmoney login            # prints a link: open it, log in to INDmoney
    python -m agents.indmoney finish "<URL>"   # paste the address your browser ended on
    python -m agents.indmoney test             # checks the connection

After that the access token renews itself. The token file lives outside the repo and is
never committed. Access is read-only (market:read).
"""
import asyncio
import base64
import hashlib
import json
import os
import secrets
import sys
import time
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

import httpx2
import pandas as pd
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client

BASE = "https://mcp.indmoney.com"
MCP_URL = f"{BASE}/mcp"
REDIRECT_URI = "http://localhost:8765/callback"
SCOPE = "market:read"
TOKEN_FILE = Path(os.environ.get("INDMONEY_TOKEN_FILE", Path.home() / ".config" / "indmoney" / "token.json"))


class LoginRequired(RuntimeError):
    pass


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
    if not data.get("client_id"):
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
    return payload


class IndMoney:
    """One connection to the INDmoney MCP server: `async with IndMoney() as im: await im.movers(...)`."""

    async def __aenter__(self):
        self._http = httpx2.AsyncClient(headers={"Authorization": f"Bearer {access_token()}"},
                                        timeout=httpx2.Timeout(30.0, read=60.0))
        self._transport = streamable_http_client(MCP_URL, http_client=self._http)
        read, write = await self._transport.__aenter__()
        self._session = ClientSession(read, write)
        await self._session.__aenter__()
        await self._session.initialize()
        return self

    async def __aexit__(self, *exc):
        await self._session.__aexit__(*exc)
        await self._transport.__aexit__(*exc)
        await self._http.aclose()

    async def call(self, tool: str, **args) -> dict:
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

    async def option_chain(self, ind_key: str, strikes_around_atm: int = 4) -> dict:
        return await self.call("get_indian_stocks_option_chain", ind_key=ind_key,
                               use_expiry_date=False, strikes_around_atm=strikes_around_atm)

    async def quotes(self, ind_keys: list[str]) -> dict:
        return await self.call("get_indian_stocks_details", ind_keys=ind_keys)


def candles_frame(rows: list[dict]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])
    df = pd.DataFrame(rows)
    df.index = pd.to_datetime(df["datetime_ist"]).dt.tz_localize("Asia/Kolkata")
    df = df.rename(columns=str.capitalize)[["Open", "High", "Low", "Close", "Volume"]]
    return df.astype(float)


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
    leg = row["put_data" if side == "gainer" else "call_data"]
    bid = leg.get("buy_price", leg.get("bp"))
    ask = leg.get("sell_price", leg.get("sp"))
    if not bid or not ask:
        return None
    expiry = pd.to_datetime(chain["selected_expiry"]).date()
    return {
        "contract": f"{leg['slug'].upper()}", "derivative_id": leg["derivative_id"],
        "type": "PE" if side == "gainer" else "CE", "strike": strikes[i], "expiry": expiry,
        "bid": bid, "ask": ask, "ltp": leg.get("current_price"), "est_premium": ask,
        "spread_pct": (ask - bid) / ask * 100, "delta": leg.get("delta") or (-0.5 if side == "gainer" else 0.5),
        "lot_size": leg.get("lot_size"), "oi_tag": row.get("oi_trend_tag"), "spot": spot,
    }


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
