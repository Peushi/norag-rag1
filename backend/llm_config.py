"""Which LLM BakeFix talks to, read from the environment.

Any OpenAI-compatible chat-completions server works: Google Gemini, OpenAI,
a university gateway, or a local server such as Ollama or vLLM.

    LLM_URL      base URL of the OpenAI-compatible API (ends in /v1 for most servers)
    LLM_API_KEY  API key; may be left empty for local servers that need none
    LLM_MODEL    model name as the server knows it

Values are read from the real environment first, then `.env.local`, then
`.env` (earlier sources win). The older Gemini-only names (GOOGLE_API_KEY,
GEMINI_MODEL, GEMINI_TIMEOUT_SECONDS) still work as fallbacks so existing
local `.env` files keep working.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv
from openai import BadRequestError, OpenAI

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# override=False: values already set (real environment, then .env.local) win.
load_dotenv(PROJECT_ROOT / ".env.local", override=False)
load_dotenv(PROJECT_ROOT / ".env", override=False)

GOOGLE_OPENAI_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
DEFAULT_MODEL = "gemini-3.5-flash-lite"


@dataclass(frozen=True)
class LLMSettings:
    url: str
    api_key: str | None
    model: str
    timeout_seconds: float
    url_is_default: bool

    @property
    def provider_label(self) -> str:
        """A short, non-secret description for logs, traces, and the AI-BOM."""
        return "Google Gemini (default)" if self.url_is_default else self.url

    @property
    def is_configured(self) -> bool:
        # The default Google endpoint needs a key; a custom server (e.g. a local
        # Ollama) may not, so an explicit LLM_URL is enough on its own.
        return bool(self.api_key) or not self.url_is_default


def _first(*names: str) -> str | None:
    for name in names:
        value = os.getenv(name)
        if value is not None and value.strip():
            return value.strip()
    return None


def read_settings() -> LLMSettings:
    url = _first("LLM_URL")
    timeout = _first("LLM_TIMEOUT_SECONDS", "GEMINI_TIMEOUT_SECONDS")
    return LLMSettings(
        url=url or GOOGLE_OPENAI_URL,
        api_key=_first("LLM_API_KEY", "GOOGLE_API_KEY"),
        model=_first("LLM_MODEL", "GEMINI_MODEL") or DEFAULT_MODEL,
        # Local models on a laptop can take well over 30 s for a long answer.
        timeout_seconds=float(timeout) if timeout else 60.0,
        url_is_default=url is None,
    )


MISSING_CONFIG_MESSAGE = (
    "No LLM is configured. Set LLM_URL, LLM_API_KEY and LLM_MODEL in .env or "
    ".env.local (see .env.example), then restart the backend."
)


def make_client(settings: LLMSettings, max_retries: int = 1) -> OpenAI | None:
    if not settings.is_configured:
        return None
    return OpenAI(
        base_url=settings.url,
        # The client library requires some key; local servers ignore it.
        api_key=settings.api_key or "not-needed",
        timeout=settings.timeout_seconds,
        max_retries=max_retries,
    )


# Not every OpenAI-compatible server accepts response_format=json_object.
# After one refusal, ask for JSON through the prompt only (it already does).
_json_mode_supported = True


def chat_json(client: OpenAI, *, model: str, messages: list[dict], **kwargs):
    """A chat completion that should return a JSON object, on any compatible server."""
    global _json_mode_supported
    if _json_mode_supported:
        try:
            return client.chat.completions.create(
                model=model,
                messages=messages,
                response_format={"type": "json_object"},
                **kwargs,
            )
        except BadRequestError as exc:
            if "response_format" not in str(exc) and "json" not in str(exc).lower():
                raise
            _json_mode_supported = False
    return client.chat.completions.create(model=model, messages=messages, **kwargs)


_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


def parse_json_object(content: str) -> dict:
    """Parse a JSON object, tolerating Markdown fences or text around it.

    Some models (especially local ones) wrap JSON in ```json fences or add a
    sentence before it. Raises json.JSONDecodeError if no object is found.
    """
    text = _FENCE.sub("", content.strip())
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end <= start:
            raise
        value = json.loads(text[start : end + 1])
    if not isinstance(value, dict):
        raise json.JSONDecodeError("Expected a JSON object", text, 0)
    return value
