"""The brains the desk can use: Grok (xAI Responses API, as in the Browsing-agent) and Claude
(Anthropic Messages API), plus a spending meter that enforces a daily AI budget.

Three tiers of brain:
  watcher  cheap and fast: reads the news every 10 minutes (Claude Haiku by default)
  team     the Moderator, 12 specialists and the Strategist
  boss     Arjun
"""

import datetime as dt
import json
import os
import re
import sys
import threading
from pathlib import Path
from zoneinfo import ZoneInfo

XAI_BASE_URL = "https://api.x.ai/v1"
DEFAULT_MODELS = {"grok": "grok-4.3", "claude": "claude-opus-5-5"}
WATCHER_MODELS = {"claude": "claude-haiku-5-5"}  # Grok watcher uses the team's Grok model unless --watch-model
IST = ZoneInfo("Asia/Kolkata")

# USD per million tokens: (input, output, cache read). Cache writes cost 1.25x input.
PRICES = {
    "claude-opus-5-5": (4.00, 20.00, 0.20),
    "claude-sonnet-5-5": (2.00, 10.00, 0.20),
    "claude-haiku-5-5": (0.10, 0.50, 0.01),
    "claude-fable-5-1": (10.00, 50.00, 1.00),
}
# Grok rates: set GROK_PRICE_IN / GROK_PRICE_OUT (USD per million tokens) from xAI's pricing page.
# The defaults are a deliberately high placeholder so the budget errs on the safe side.
GROK_PRICES = (float(os.environ.get("GROK_PRICE_IN", 5)), float(os.environ.get("GROK_PRICE_OUT", 25)))
WEB_SEARCH_USD = 0.01  # Claude web search: $10 per 1,000 searches


class BudgetExceeded(Exception):
    pass


class Budget:
    """Daily AI spend, saved to state/ai_spend.json. Each kind of work has its own share of the daily
    budget, so the big morning meeting can't starve the news watcher:
    morning meeting 50%, intraday decisions 35%, news watching 15%.
    Trading itself never stops: armed setups, stops and targets run in code without any AI."""

    SHARE = {"morning": 0.50, "intraday": 0.35, "watch": 0.15}

    def __init__(self, limit_usd, path="state/ai_spend.json"):
        self.limit = limit_usd
        self.path = Path(path)
        self.lock = threading.Lock()
        self.data = json.loads(self.path.read_text()) if self.path.exists() else {}

    def _today(self):
        return self.data.setdefault(dt.datetime.now(IST).date().isoformat(), {"usd": 0.0, "calls": 0, "by_role": {}})

    def spent(self):
        with self.lock:
            return self._today()["usd"]

    def role_spent(self, role):
        with self.lock:
            return self._today()["by_role"].get(role, 0.0)

    def exhausted(self, role):
        return self.role_spent(role) >= self.limit * self.SHARE.get(role, 1.0) or self.spent() >= self.limit

    def check(self, role):
        if self.exhausted(role):
            cap = self.limit * self.SHARE.get(role, 1.0)
            raise BudgetExceeded(f"AI budget for '{role}' used up today (${self.role_spent(role):.2f} of ${cap:.2f})")

    def add(self, usd, role):
        with self.lock:
            day = self._today()
            day["usd"] = round(day["usd"] + usd, 4)
            day["calls"] += 1
            day["by_role"][role] = round(day["by_role"].get(role, 0) + usd, 4)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self.data, indent=2))

    def summary(self):
        with self.lock:
            d = self._today()
            return f"AI spend today ${d['usd']:.2f} of ${self.limit:.2f} in {d['calls']} calls {d['by_role']}"


def make_llm(provider, model=None, web_search=True, budget=None, tier="team"):
    provider = provider or default_provider()
    if provider == "claude":
        return ClaudeLLM(model or (WATCHER_MODELS["claude"] if tier == "watcher" else None), web_search, budget)
    if provider == "grok":
        return GrokLLM(model, web_search, budget)
    sys.exit(f"Unknown provider '{provider}'. Use grok or claude.")


def default_provider():
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "claude"
    if os.environ.get("XAI_API_KEY"):
        return "grok"
    sys.exit("Set ANTHROPIC_API_KEY (Claude) and/or XAI_API_KEY (Grok).")


class _Base:
    budget = None

    def _charge(self, usd, role):
        if self.budget:
            self.budget.add(usd, role)

    def ask_json(self, system, user, search=False, effort="medium", role="morning", cache_prefix=""):
        """Ask for a JSON object. Retries once if the reply can't be parsed."""
        text = self.ask(system, user, search, effort, role, cache_prefix)
        try:
            return extract_json(text)
        except ValueError:
            text = self.ask(system, user + "\n\nYour last reply was not valid JSON. Reply with ONLY the JSON object.",
                            False, effort, role, cache_prefix)
            return extract_json(text)


class GrokLLM(_Base):
    name = "grok"

    def __init__(self, model=None, web_search=True, budget=None):
        import openai
        api_key = os.environ.get("XAI_API_KEY")
        if not api_key:
            sys.exit("XAI_API_KEY is not set. Create a key at https://console.x.ai and export it.")
        self._openai = openai
        self.client = openai.OpenAI(api_key=api_key, base_url=XAI_BASE_URL, timeout=600)
        self.model = model or os.environ.get("GROK_MODEL", DEFAULT_MODELS["grok"])
        self.web_search = web_search
        self.budget = budget

    def ask(self, system, user, search=False, effort="medium", role="morning", cache_prefix=""):
        if self.budget:
            self.budget.check(role)
        # xAI caches repeated prompt prefixes on its own; keeping the stable part first helps it.
        kwargs = {"model": self.model, "input": [{"role": "system", "content": system},
                                                 {"role": "user", "content": cache_prefix + user}]}
        response = None
        if search and self.web_search:
            try:
                response = self.client.responses.create(tools=[{"type": "web_search"}], **kwargs)
            except self._openai.BadRequestError:
                self.web_search = False  # Model or key without search: fall back to plain calls.
                print("   ⚠️  Grok web search unavailable; agents will reason without live news.")
        response = response or self.client.responses.create(**kwargs)
        u = response.usage
        if u:
            self._charge((u.input_tokens * GROK_PRICES[0] + u.output_tokens * GROK_PRICES[1]) / 1e6, role)
        return response.output_text


class ClaudeLLM(_Base):
    name = "claude"

    def __init__(self, model=None, web_search=True, budget=None):
        import anthropic
        if not os.environ.get("ANTHROPIC_API_KEY") and not os.environ.get("ANTHROPIC_AUTH_TOKEN"):
            sys.exit("ANTHROPIC_API_KEY is not set. Create a key at https://platform.claude.com and export it.")
        self.client = anthropic.Anthropic()
        self.model = model or os.environ.get("CLAUDE_MODEL", DEFAULT_MODELS["claude"])
        self.web_search = web_search
        self.budget = budget

    def _cost(self, usage):
        p_in, p_out, p_cache = PRICES.get(self.model, PRICES["claude-opus-5-5"])
        searches = getattr(getattr(usage, "server_tool_use", None), "web_search_requests", 0) or 0
        return ((usage.input_tokens * p_in + usage.output_tokens * p_out
                 + (usage.cache_creation_input_tokens or 0) * p_in * 1.25
                 + (usage.cache_read_input_tokens or 0) * p_cache) / 1e6 + searches * WEB_SEARCH_USD)

    def ask(self, system, user, search=False, effort="medium", role="morning", cache_prefix=""):
        if self.budget:
            self.budget.check(role)
        haiku = "haiku" in self.model
        content = [{"type": "text", "text": user}]
        if cache_prefix:  # Stable context repeated across calls (minutes, plan): read from cache at ~5% of the price.
            content.insert(0, {"type": "text", "text": cache_prefix, "cache_control": {"type": "ephemeral"}})
        messages = [{"role": "user", "content": content}]
        tools = []
        if search and self.web_search:
            # The dynamic-filtering search tool needs Opus/Sonnet; Haiku uses the basic one.
            tools = [{"type": "web_search_20250305" if haiku else "web_search_20260209", "name": "web_search",
                      "max_uses": 3 if haiku else 5}]
        extra = {} if haiku else {"betas": ["server-side-fallback-2026-07-01"], "fallbacks": "default"}
        for _ in range(5):  # Web search can pause a long turn; resume it.
            response = self.client.beta.messages.create(
                model=self.model, max_tokens=16000, messages=messages, tools=tools,
                system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
                output_config={"effort": effort}, **extra)
            self._charge(self._cost(response.usage), role)
            if response.stop_reason == "refusal":
                category = response.stop_details.category if response.stop_details else None
                raise RuntimeError(f"Claude declined this request (category: {category})")
            if response.stop_reason != "pause_turn":
                break
            messages.append({"role": "assistant", "content": response.content})
        return "".join(b.text for b in response.content if b.type == "text")


def extract_json(text):
    """Pull the first JSON object out of a reply that may be wrapped in prose or ``` fences."""
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    candidate = fenced.group(1) if fenced else text[text.find("{"): text.rfind("}") + 1]
    try:
        return json.loads(candidate)
    except json.JSONDecodeError as e:
        raise ValueError(f"No JSON object in reply: {text[:200]}") from e
