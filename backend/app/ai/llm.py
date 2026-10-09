"""LLM provider abstraction.

The app talks to a local Ollama server by default. All structured calls go through
``complete_structured``: prompt -> raw text -> JSON extraction -> Pydantic validation ->
one repair retry -> ``None``. Callers must always have a deterministic fallback for ``None``.
"""

from __future__ import annotations

import concurrent.futures
import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from app.ai.json_utils import extract_json
from app.config import get_settings

logger = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)


@dataclass
class LLMStatus:
    provider: str
    model: str
    available: bool
    server: str  # ok | unreachable | disabled
    model_available: bool
    detail: str
    installed_models: list[str]


class LLMProvider:
    name = "none"
    model = ""

    def status(self, refresh: bool = False) -> LLMStatus:
        raise NotImplementedError

    def is_available(self) -> bool:
        return self.status().available

    def chat(self, system: str, user: str, *, json_schema: dict | None = None, temperature: float | None = None) -> str:
        raise NotImplementedError

    def complete_structured(
        self,
        system: str,
        user: str,
        schema: type[T],
        *,
        temperature: float | None = None,
        validator: Callable[[T], str | None] | None = None,
    ) -> T | None:
        """Ask for JSON matching ``schema``; validate, retry once with the error, else return None.

        ``validator`` may return an error message to reject semantically bad output.
        """
        if not self.is_available():
            return None
        retries = max(0, get_settings().llm_max_retries)
        messages_user = user
        for attempt in range(retries + 1):
            try:
                raw = self.chat(system, messages_user, json_schema=schema.model_json_schema(), temperature=temperature)
            except Exception as exc:  # network errors, timeouts
                logger.warning("llm call failed: %s", type(exc).__name__)
                return None
            data = extract_json(raw)
            error: str | None
            if data is None:
                error = "The response was not a JSON object."
            else:
                try:
                    parsed = schema.model_validate(data)
                    error = validator(parsed) if validator else None
                    if error is None:
                        return parsed
                except ValidationError as exc:
                    error = "; ".join(f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()[:6])
            logger.info("llm output rejected (attempt %d): %s", attempt + 1, (error or "")[:200])
            messages_user = (
                f"{user}\n\nYour previous reply was invalid: {error}\n"
                "Reply again with ONLY a JSON object that matches the required schema."
            )
        return None


class NullProvider(LLMProvider):
    name = "none"

    def __init__(self, reason: str = "AI features are disabled."):
        self.reason = reason

    def status(self, refresh: bool = False) -> LLMStatus:
        return LLMStatus("none", "", False, "disabled", False, self.reason, [])

    def chat(self, system, user, *, json_schema=None, temperature=None) -> str:  # pragma: no cover
        raise RuntimeError("LLM disabled")


_PROBE_POOL = concurrent.futures.ThreadPoolExecutor(max_workers=2, thread_name_prefix="ollama-probe")


class OllamaProvider(LLMProvider):
    name = "ollama"
    STATUS_TTL = 15.0

    def __init__(self, base_url: str, model: str, timeout: float):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self._status: LLMStatus | None = None
        self._status_at = 0.0
        self._lock = threading.Lock()
        self._probe_future: concurrent.futures.Future[LLMStatus] | None = None

    PROBE_DEADLINE = 3.0

    def _unreachable(self, why: str = "") -> LLMStatus:
        return LLMStatus(
            "ollama",
            self.model,
            False,
            "unreachable",
            False,
            f"Ollama is not reachable at {self.base_url}{why}. Install it from https://ollama.com and run "
            f"'ollama serve', then 'ollama pull {self.model}'.",
            [],
        )

    def _probe(self) -> LLMStatus:
        try:
            resp = httpx.get(f"{self.base_url}/api/tags", timeout=2.5)
            resp.raise_for_status()
            models = [m.get("name", "") for m in resp.json().get("models", [])]
            wanted = self.model if ":" in self.model else f"{self.model}:latest"
            has_model = any(m == self.model or m == wanted for m in models)
            detail = (
                f"Ollama is running and '{self.model}' is installed."
                if has_model
                else f"Ollama is running but the model '{self.model}' is not installed. Run: ollama pull {self.model}"
            )
            return LLMStatus("ollama", self.model, has_model, "ok", has_model, detail, models)
        except Exception as exc:
            logger.info("ollama unreachable: %s", type(exc).__name__)
            return self._unreachable()

    def status(self, refresh: bool = False) -> LLMStatus:
        with self._lock:
            fresh = self._status and time.monotonic() - self._status_at < self.STATUS_TTL
            if self._status and (fresh and not refresh):
                return self._status
            # Never stack probes: while one is running, reuse it.
            if self._probe_future is None or self._probe_future.done():
                self._probe_future = _PROBE_POOL.submit(self._probe)
            future = self._probe_future
        # httpx timeouts don't cover DNS resolution (which can block for a minute when the host
        # doesn't resolve), so the probe runs on a worker thread with a hard deadline.
        try:
            st = future.result(timeout=self.PROBE_DEADLINE)
        except concurrent.futures.TimeoutError:
            logger.info("ollama probe timed out")
            st = self._unreachable(" (connection timed out)")
        with self._lock:
            self._status, self._status_at = st, time.monotonic()
        return st

    def chat(self, system: str, user: str, *, json_schema: dict | None = None, temperature: float | None = None) -> str:
        settings = get_settings()
        payload = {
            "model": self.model,
            "stream": False,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "options": {
                "temperature": settings.llm_temperature if temperature is None else temperature,
                "num_ctx": 8192,
            },
        }
        if json_schema is not None:
            payload["format"] = json_schema
        started = time.monotonic()
        resp = httpx.post(f"{self.base_url}/api/chat", json=payload, timeout=self.timeout)
        resp.raise_for_status()
        content = resp.json().get("message", {}).get("content", "")
        logger.info("ollama chat ok model=%s duration_ms=%d", self.model, int((time.monotonic() - started) * 1000))
        return content


# ---------------------------------------------------------------- provider registry

_override: LLMProvider | None = None
_cached: LLMProvider | None = None
_runtime: dict[str, str] = {}


def set_runtime_options(model: str | None = None, base_url: str | None = None) -> None:
    """Apply settings saved from the UI (model name / Ollama URL)."""
    global _cached
    if model:
        _runtime["model"] = model
    if base_url:
        _runtime["base_url"] = base_url
    _cached = None


def set_provider(provider: LLMProvider | None) -> None:
    """Install a provider explicitly (used by tests)."""
    global _override, _cached
    _override = provider
    _cached = None


def get_provider() -> LLMProvider:
    global _cached
    if _override is not None:
        return _override
    if _cached is not None:
        return _cached
    s = get_settings()
    if s.test_mode:
        _cached = NullProvider("Test mode is enabled: deterministic offline engine in use.")
    elif s.llm_provider.lower() != "ollama":
        _cached = NullProvider("LLM_PROVIDER is set to 'none'.")
    else:
        _cached = OllamaProvider(
            _runtime.get("base_url", s.ollama_base_url),
            _runtime.get("model", s.ollama_model),
            s.llm_timeout_seconds,
        )
    return _cached
