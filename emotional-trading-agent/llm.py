"""The two brains the desk can use: Grok (xAI Responses API, as in the Browsing-agent) and Claude
(Anthropic Messages API). The boss and the team can run on different ones."""

import json
import os
import re
import sys

XAI_BASE_URL = "https://api.x.ai/v1"
DEFAULT_MODELS = {"grok": "grok-4.3", "claude": "claude-opus-5-5"}


def make_llm(provider, model=None, web_search=True):
    provider = provider or default_provider()
    if provider == "claude":
        return ClaudeLLM(model, web_search)
    if provider == "grok":
        return GrokLLM(model, web_search)
    sys.exit(f"Unknown provider '{provider}'. Use grok or claude.")


def default_provider():
    if os.environ.get("XAI_API_KEY"):
        return "grok"
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "claude"
    sys.exit("Set XAI_API_KEY (Grok) and/or ANTHROPIC_API_KEY (Claude).")


class _Base:
    def ask_json(self, system, user, search=False, effort="medium"):
        """Ask for a JSON object. Retries once if the reply can't be parsed."""
        text = self.ask(system, user, search, effort)
        try:
            return extract_json(text)
        except ValueError:
            text = self.ask(system, user + "\n\nYour last reply was not valid JSON. Reply with ONLY the JSON object.",
                            False, effort)
            return extract_json(text)


class GrokLLM(_Base):
    name = "grok"

    def __init__(self, model=None, web_search=True):
        import openai
        api_key = os.environ.get("XAI_API_KEY")
        if not api_key:
            sys.exit("XAI_API_KEY is not set. Create a key at https://console.x.ai and export it.")
        self._openai = openai
        self.client = openai.OpenAI(api_key=api_key, base_url=XAI_BASE_URL, timeout=600)
        self.model = model or os.environ.get("GROK_MODEL", DEFAULT_MODELS["grok"])
        self.web_search = web_search

    def ask(self, system, user, search=False, effort="medium"):
        kwargs = {"model": self.model, "input": [{"role": "system", "content": system},
                                                 {"role": "user", "content": user}]}
        if search and self.web_search:
            try:
                return self.client.responses.create(tools=[{"type": "web_search"}], **kwargs).output_text
            except self._openai.BadRequestError:
                self.web_search = False  # Model or key without search: fall back to plain calls.
                print("   ⚠️  Grok web search unavailable; agents will reason without live news.")
        return self.client.responses.create(**kwargs).output_text


class ClaudeLLM(_Base):
    name = "claude"

    def __init__(self, model=None, web_search=True):
        import anthropic
        if not os.environ.get("ANTHROPIC_API_KEY") and not os.environ.get("ANTHROPIC_AUTH_TOKEN"):
            sys.exit("ANTHROPIC_API_KEY is not set. Create a key at https://platform.claude.com and export it.")
        self.client = anthropic.Anthropic()
        self.model = model or os.environ.get("CLAUDE_MODEL", DEFAULT_MODELS["claude"])
        self.web_search = web_search

    def ask(self, system, user, search=False, effort="medium"):
        messages = [{"role": "user", "content": user}]
        tools = [{"type": "web_search_20260209", "name": "web_search", "max_uses": 5}] if search and self.web_search else []
        for _ in range(5):  # Web search can pause a long turn; resume it.
            response = self.client.beta.messages.create(
                model=self.model, max_tokens=16000, system=system, messages=messages,
                output_config={"effort": effort}, tools=tools,
                # If a safety classifier declines, the API retries on a suitable fallback model.
                betas=["server-side-fallback-2026-07-01"], fallbacks="default",
            )
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
