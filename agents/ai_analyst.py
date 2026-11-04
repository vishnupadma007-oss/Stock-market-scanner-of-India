"""AI Analyst agent (Claude): looks at the actual chart image, checks the news for the
reason behind the move, and gives a second opinion. Only the best few candidates are sent
here, so token use stays small (a few calls per run)."""
import base64
import json
import os

import anthropic

SYSTEM = """You are the senior analyst on an intraday options desk trading NSE stocks.
The strategy is mean reversion on the day's top movers: buy a PUT on a top gainer that is
showing exhaustion, or buy a CALL on a top loser that is showing a bounce. The goal is a
small, quick gain (about 1-2% on the option premium) and a full exit the same day.

You get the 5-minute chart image (candles, VWAP, EMA 9/21, volume), indicator facts, and
the other agents' findings. Do two things:
1. Read the chart yourself: trend structure, higher highs/lower lows, rejection candles,
   VWAP behaviour, volume. Say whether a reversal has actually started or not yet.
2. If web search is available, check today's news for the stock. A move driven by a real
   catalyst (results, big order, merger, regulatory action, fraud, upgrade/downgrade) is
   less likely to reverse intraday: lean to SKIP in that case.

Be strict: SKIP is the right answer when in doubt. Reply with ONLY a JSON object:
{"verdict": "TRADE" | "WATCH" | "SKIP", "confidence": 0-100,
 "chart_read": "<2 sentences>", "news": "<1-2 sentences, or 'not checked'>",
 "reason": "<1 sentence>"}"""


def available() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def _parse(text: str) -> dict:
    start, end = text.find("{"), text.rfind("}")
    data = json.loads(text[start:end + 1])
    data["verdict"] = str(data.get("verdict", "SKIP")).upper()
    data["confidence"] = int(data.get("confidence", 0))
    return data


def review(symbol: str, side: str, png: bytes, facts: dict, ai_cfg: dict) -> dict:
    client = anthropic.Anthropic()
    tools = [{"type": "web_search_20260209", "name": "web_search", "max_uses": 3}] \
        if ai_cfg.get("web_search") else []
    idea = "buy PUT (gainer fading)" if side == "gainer" else "buy CALL (loser bouncing)"
    messages = [{"role": "user", "content": [
        {"type": "image", "source": {"type": "base64", "media_type": "image/png",
                                     "data": base64.standard_b64encode(png).decode()}},
        {"type": "text", "text": f"Stock: {symbol} (NSE). Idea: {idea}.\n"
                                 f"Facts from the team:\n{json.dumps(facts, indent=1, default=str)}"},
    ]}]

    try:
        for _ in range(3):  # web search can pause a long turn; resume it
            response = client.beta.messages.create(
                model=ai_cfg["model"], max_tokens=16000, system=SYSTEM,
                messages=messages, tools=tools,
                output_config={"effort": ai_cfg.get("effort", "medium")},
                betas=["server-side-fallback-2026-07-01"], fallbacks="default",
            )
            if response.stop_reason != "pause_turn":
                break
            messages.append({"role": "assistant", "content": response.content})
    except anthropic.APIStatusError as e:
        return {"verdict": "ERROR", "confidence": 0, "reason": f"API error {e.status_code}: {e.message}"}
    except anthropic.APIConnectionError:
        return {"verdict": "ERROR", "confidence": 0, "reason": "Could not reach the Claude API."}

    if response.stop_reason == "refusal":
        return {"verdict": "ERROR", "confidence": 0, "reason": "The model declined this request."}
    text = "".join(b.text for b in response.content if b.type == "text")
    try:
        return _parse(text)
    except (ValueError, json.JSONDecodeError):
        return {"verdict": "ERROR", "confidence": 0, "reason": f"Unreadable reply: {text[:200]}"}
