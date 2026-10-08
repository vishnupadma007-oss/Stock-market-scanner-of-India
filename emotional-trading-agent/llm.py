"""Thin wrapper around the xAI Grok Responses API (same setup as the Browsing-agent)."""

import json
import os
import re
import sys

import openai

XAI_BASE_URL = "https://api.x.ai/v1"
DEFAULT_MODEL = "grok-4.3"


class LLM:
    def __init__(self, model=None, web_search=True):
        api_key = os.environ.get("XAI_API_KEY")
        if not api_key:
            sys.exit("XAI_API_KEY is not set. Create a key at https://console.x.ai and export it.")
        self.client = openai.OpenAI(api_key=api_key, base_url=XAI_BASE_URL, timeout=600)
        self.model = model or os.environ.get("GROK_MODEL", DEFAULT_MODEL)
        self.web_search = web_search

    def ask(self, system, user, search=False):
        """One call. With search=True Grok may use its server-side web search for live news."""
        kwargs = {"model": self.model, "input": [{"role": "system", "content": system},
                                                 {"role": "user", "content": user}]}
        if search and self.web_search:
            try:
                return self.client.responses.create(tools=[{"type": "web_search"}], **kwargs).output_text
            except openai.BadRequestError:
                self.web_search = False  # Model or key without search: fall back to plain calls.
                print("   ⚠️  Web search unavailable for this model; analysts will reason without live news.")
        return self.client.responses.create(**kwargs).output_text

    def ask_json(self, system, user, search=False):
        """Ask for a JSON object. Retries once if the reply can't be parsed."""
        text = self.ask(system, user, search)
        try:
            return extract_json(text)
        except ValueError:
            text = self.ask(system, user + "\n\nYour last reply was not valid JSON. Reply with ONLY the JSON object.")
            return extract_json(text)


def extract_json(text):
    """Pull the first JSON object out of a reply that may be wrapped in prose or ``` fences."""
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    candidate = fenced.group(1) if fenced else text[text.find("{"): text.rfind("}") + 1]
    try:
        return json.loads(candidate)
    except json.JSONDecodeError as e:
        raise ValueError(f"No JSON object in reply: {text[:200]}") from e
