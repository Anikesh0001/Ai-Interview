"""Prompt for an adaptive follow-up question."""

from __future__ import annotations

from app.ai.prompts.base import SAFETY_RULES, wrap_untrusted
from app.ai.prompts.interviewer import interviewer_system_prompt

PROMPT_VERSION = "1.0"

INTENT = {
    "Strong": "Go one level deeper on the most interesting technical point they raised.",
    "Weak": "Ask a clarifying question that gives them a fair second chance on the core of the original question.",
    "Vague": "Ask for concrete details: a specific example, what exactly they did, numbers, tools.",
    "Incorrect": "Politely challenge the inaccurate part without giving the answer and invite them to reconsider.",
    "Suspicious": "Ask a verification question about how the claim was achieved or measured. Do not accuse.",
    "Incomplete": "Ask about the most important part of the question they did not address.",
}


def build(
    *, ctx: dict, question: str, answer: str, classification: str, missing: list[str], claim: str | None
) -> tuple[str, str]:
    system = interviewer_system_prompt(ctx["personality"], ctx["role"], ctx["level"], SAFETY_RULES)
    claim_block = f"\nRelated resume claim:\n{wrap_untrusted('resume_claim', claim, 400)}\n" if claim else ""
    user = f"""You just asked:
{question}

The candidate answered:
{wrap_untrusted("candidate_answer", answer, 3000)}
{claim_block}
Internal assessment (never reveal it): {classification}. Gaps: {", ".join(missing[:4]) or "n/a"}.
Goal: {INTENT.get(classification, INTENT["Strong"])}

Return JSON with:
- "acknowledgement": a brief natural reaction (max 1 sentence, no praise like "great answer")
- "question": ONE follow-up question (max 2 sentences) that references what they said
- "expected_concepts": 2-5 short concepts a good reply would include"""
    return system, user
