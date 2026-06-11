"""Direct LLM API calls — bypasses LangChain to avoid response_format issues."""

import json
import logging
import os
import time
from typing import Optional

import requests

log = logging.getLogger("tools.llm")

RETRYABLE_HTTP = (
    requests.ConnectionError,
    requests.Timeout,
    requests.exceptions.ReadTimeout,
    requests.exceptions.ConnectTimeout,
    ConnectionError,
    TimeoutError,
)

MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 1.5  # seconds, exponential: 1.5 → 2.25 → 3.375


class DirectLLM:
    """Drop-in replacement for ChatOpenAI that calls the API directly."""

    def __init__(self, model: str = "", temperature: float = 0.7, max_tokens: int = 16384):
        self.model = model or os.getenv("OPENAI_MODEL_NAME") or "deepseek-chat"
        self.temperature = temperature
        self.max_tokens = max_tokens

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

        last_error = ""
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                r = requests.post(
                    f"{base_url.rstrip('/')}/chat/completions",
                    json={
                        "model": self.model,
                        "messages": messages,
                        "temperature": self.temperature,
                        "max_tokens": self.max_tokens,
                    },
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    timeout=60,
                )

                if r.status_code == 200:
                    return r.json()["choices"][0]["message"]["content"]

                # 429 / 5xx → retry
                if r.status_code in (429, 502, 503, 504):
                    last_error = f"API error {r.status_code}: {r.text[:200]}"
                    if attempt < MAX_RETRIES:
                        wait = RETRY_BACKOFF_BASE ** attempt
                        log.warning("LLM retry %d/%d (status %d), waiting %.1fs",
                                    attempt, MAX_RETRIES, r.status_code, wait)
                        time.sleep(wait)
                        continue

                # 4xx (other than 429), no retry
                return json.dumps({"error": f"API error {r.status_code}: {r.text[:200]}"})

            except RETRYABLE_HTTP as e:
                last_error = f"network error: {e}"
                if attempt < MAX_RETRIES:
                    wait = RETRY_BACKOFF_BASE ** attempt
                    log.warning("LLM retry %d/%d after %s, waiting %.1fs",
                                attempt, MAX_RETRIES, type(e).__name__, wait)
                    time.sleep(wait)
                    continue
                return json.dumps({"error": last_error})

            except (KeyError, json.JSONDecodeError) as e:
                # Parse error → no point retrying
                return json.dumps({"error": f"unexpected response: {e}"})

        return json.dumps({"error": last_error})
