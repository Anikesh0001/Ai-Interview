"""Prompt for generating the next main interview question."""

from __future__ import annotations

from app.ai.prompts.base import SAFETY_RULES, bullet_list, wrap_untrusted
from app.ai.prompts.interviewer import interviewer_system_prompt

PROMPT_VERSION = "1.0"

CATEGORY_GUIDANCE = {
    "intro": "A warm-up question inviting the candidate to walk through their background.",
    "resume": "A question about a specific role, responsibility or claim from the resume.",
    "claim_verification": "A question that checks how the candidate substantiates the specific resume claim given as the focus (how it was measured, built or achieved). Do not accuse.",
    "project": "A deep-dive question about the focus project: problem, architecture, technology choices, personal contribution, trade-offs, failure handling or scaling.",
    "technical": "A conceptual or practical technical question about the focus skill, pitched at the requested difficulty and grounded in how the candidate used it.",
    "skills": "A practical question about how the candidate applied the focus skill.",
    "coding": "A verbal coding/algorithm question the candidate can answer by explaining an approach and its complexity (no IDE needed).",
    "system_design": "A system design question scoped so it can be discussed verbally in a few minutes.",
    "situational": "A realistic scenario (e.g. production incident, ambiguous requirement) asking how they would handle it.",
    "behavioral": "A STAR-style behavioral question (situation, task, action, result).",
    "hr": "An HR/motivation question about goals, values, teamwork or role fit.",
    "jd_specific": "A question about a requirement from the job description, especially one the resume does not clearly show.",
    "role_specific": "A question about core responsibilities of the target role.",
}


def build(*, ctx: dict, slot: dict, asked: list[str], difficulty: str) -> tuple[str, str]:
    system = interviewer_system_prompt(ctx["personality"], ctx["role"], ctx["level"], SAFETY_RULES)
    category = slot["category"]
    user = f"""Generate the next interview question.

Phase: {slot["phase"]}
Question category: {category} — {CATEGORY_GUIDANCE.get(category, "")}
Focus: {slot.get("focus") or "choose the most relevant topic"}
Target difficulty: {difficulty}

Candidate summary (derived from parsed resume):
- Skills: {", ".join(ctx["skills"][:20]) or "unknown"}
- Projects: {", ".join(ctx["projects"][:6]) or "none listed"}
- Experience: {", ".join(ctx["experience"][:4]) or "none listed"}
- Education: {ctx["education"] or "unknown"}

Relevant resume excerpt:
{wrap_untrusted("resume_excerpt", slot.get("context_text") or ctx["resume_excerpt"], 2500)}

Job description requirements (may be empty):
{wrap_untrusted("job_description", ctx["jd_summary"], 1500)}

Previous answers summary (most recent last):
{wrap_untrusted("answer_history", ctx["answer_history"], 2000)}

Questions already asked (do NOT repeat or paraphrase these):
{bullet_list(asked, 25)}

Return JSON with:
- "question": the exact words you will say (1-3 sentences, may include a brief natural transition)
- "expected_concepts": 3-6 short key concepts a strong answer would cover
- "evaluation_rubric": 2-5 short criteria for judging the answer
- "ideal_answer": 2-4 sentences outlining the structure of an ideal answer (for the post-interview report only)"""
    return system, user
