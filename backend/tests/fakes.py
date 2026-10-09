"""A scripted LLM provider for exercising the LLM code paths without a model."""

from __future__ import annotations

from collections import deque
from collections.abc import Callable, Iterable

from app.ai.llm import LLMProvider, LLMStatus


class FakeProvider(LLMProvider):
    """Reports itself as available and returns scripted replies in order.

    Each reply is either a string or a callable ``(system, user) -> str``. When the queue is
    empty, ``default`` is returned (or, if it is None, a non-JSON string so callers fall back).
    Every call is recorded in ``calls`` as ``(system, user)``.
    """

    name = "fake"
    model = "fake-model"

    def __init__(self, replies: Iterable[str | Callable[[str, str], str]] = (), default: str | None = None):
        self.replies: deque = deque(replies)
        self.default = default
        self.calls: list[tuple[str, str]] = []

    def status(self, refresh: bool = False) -> LLMStatus:
        return LLMStatus("fake", self.model, True, "ok", True, "Fake provider for tests.", [self.model])

    def chat(self, system: str, user: str, *, json_schema: dict | None = None, temperature: float | None = None) -> str:
        self.calls.append((system, user))
        if self.replies:
            reply = self.replies.popleft()
            return reply(system, user) if callable(reply) else reply
        return self.default if self.default is not None else "I'm sorry, I can't produce JSON right now."
