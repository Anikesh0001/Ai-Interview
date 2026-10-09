"""Prompt for optional LLM enrichment of the deterministically parsed resume."""

from __future__ import annotations

from app.ai.prompts.base import SAFETY_RULES, wrap_untrusted

PROMPT_VERSION = "1.0"

SYSTEM = f"""You extract structured facts from resumes. Only report facts that literally appear in the resume.
Do not guess or embellish.

{SAFETY_RULES}"""


def build(resume_text: str) -> tuple[str, str]:
    user = f"""Resume:
{wrap_untrusted("resume", resume_text, 9000)}

Return JSON with:
- "name": candidate full name or ""
- "location": city/region or ""
- "summary": 1-2 sentence neutral summary of the candidate's background (for the interviewer's context)
- "skills": up to 25 technical skills, tools or methods explicitly mentioned
- "project_highlights": up to 4 objects {{"name": ..., "problem": ..., "role": ...}} for projects in the resume"""
    return SYSTEM, user
