"""Prompt for the narrative parts of the final report. Scores are computed by the backend."""

from __future__ import annotations

from app.ai.prompts.base import SAFETY_RULES

PROMPT_VERSION = "1.0"

SYSTEM = f"""You write concise, specific interview debriefs for a candidate. You are given computed scores and
per-question findings. Do not change or invent scores. Do not predict hiring probability or say whether they
would be hired. Be direct, constructive and specific to the evidence.

{SAFETY_RULES}"""


def build(
    *, role: str, level: str, scores: dict, strengths: list[str], weaknesses: list[str], findings: list[str]
) -> tuple[str, str]:
    user = f"""Role: {level} {role}
Computed scores (0-100): {scores}
Strongest areas: {", ".join(strengths) or "n/a"}
Weakest areas: {", ".join(weaknesses) or "n/a"}
Per-question findings (system generated):
{chr(10).join("- " + f for f in findings[:15])}

Return JSON with:
- "executive_summary": 2-3 sentences, e.g. "You demonstrated strong knowledge of X but struggled to explain Y."
- "verdict": 1-2 sentences on readiness for this level/role and what to improve first (no hiring probability)
- "communication_feedback": 1-2 sentences on clarity and structure of answers"""
    return SYSTEM, user
