"""Robust JSON extraction for LLM output. LLM text is never trusted to be valid JSON."""

from __future__ import annotations

import json
import re
from typing import Any

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


def _balanced_object(text: str) -> str | None:
    start = text.find("{")
    while start != -1:
        depth = 0
        in_str = False
        esc = False
        for i in range(start, len(text)):
            ch = text[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return text[start : i + 1]
        start = text.find("{", start + 1)
    return None


def _repair(candidate: str) -> str:
    s = candidate
    s = s.replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")
    s = re.sub(r",\s*([}\]])", r"\1", s)  # trailing commas
    s = re.sub(r"\bTrue\b", "true", s)
    s = re.sub(r"\bFalse\b", "false", s)
    s = re.sub(r"\bNone\b", "null", s)
    s = re.sub(r"//[^\n\"]*\n", "\n", s)  # line comments outside strings (best effort)
    # unquoted keys:  { key: 1 } -> { "key": 1 }
    s = re.sub(r"([{,]\s*)([A-Za-z_][A-Za-z0-9_]*)\s*:", r'\1"\2":', s)
    return s


def extract_json(text: str) -> dict[str, Any] | None:
    """Best-effort extraction of the first JSON object in ``text``. Returns None on failure."""
    if not text:
        return None
    candidates: list[str] = []
    stripped = text.strip()
    candidates.append(stripped)
    for m in _FENCE_RE.finditer(text):
        candidates.append(m.group(1).strip())
    obj = _balanced_object(text)
    if obj:
        candidates.append(obj)
    for cand in candidates:
        for attempt in (cand, _repair(cand)):
            try:
                value = json.loads(attempt)
            except (json.JSONDecodeError, ValueError):
                continue
            if isinstance(value, dict):
                return value
    return None
