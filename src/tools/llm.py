"""Direct LLM API calls — bypasses LangChain to avoid response_format issues."""

import json
import os
from typing import Optional

import requests


class DirectLLM:
    """Drop-in replacement for ChatOpenAI that calls the API directly."""

    def __init__(self, model: str = "", temperature: float = 0.7):
        self.model = model or os.getenv("OPENAI_MODEL_NAME") or "deepseek-chat"
        self.temperature = temperature

    def invoke(self, messages: list) -> str:
        """Call the API. Accepts LangChain message objects or plain dicts."""
        ROLE_MAP = {"human": "user", "ai": "assistant", "system": "system"}
        raw = []
        for m in messages:
            if hasattr(m, "content"):
                role = ROLE_MAP.get(m.type, m.type)
                raw.append({"role": role, "content": m.content})
            elif isinstance(m, dict):
                raw.append(m)
            else:
                raw.append({"role": "user", "content": str(m)})
        return self._call(raw)

    def _call(self, messages: list[dict]) -> str:
        api_key = os.getenv("OPENAI_API_KEY")
        base_url = os.getenv("OPENAI_API_BASE") or os.getenv("OPENAI_BASE_URL") or "https://api.deepseek.com"

        try:
            r = requests.post(
                f"{base_url.rstrip('/')}/chat/completions",
                json={
                    "model": self.model,
                    "messages": messages,
                    "temperature": self.temperature,
                    "max_tokens": 2048,
                },
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                timeout=60,
            )
            if r.status_code != 200:
                return json.dumps({"error": f"API error: {r.text[:200]}"})
            return r.json()["choices"][0]["message"]["content"]
        except (requests.RequestException, KeyError, json.JSONDecodeError):
            return json.dumps({"error": "request failed"})
