"""Prompt for evaluating one answer. The backend computes the final score from the dimensions."""

from __future__ import annotations

from app.ai.prompts.base import SAFETY_RULES, bullet_list, wrap_untrusted

PROMPT_VERSION = "1.0"

SYSTEM = f"""You are a strict, fair interview evaluator. You score one candidate answer against the question,
the expected concepts and the rubric. You do not converse with the candidate.

Scoring (integers 0-10 for every dimension):
- technical_correctness: factual/technical accuracy (for behavioral questions: plausibility and soundness of judgment)
- relevance: does it answer the question that was asked
- depth: specifics, reasoning, trade-offs, internals
- completeness: coverage of the expected concepts / all parts of the question (STAR for behavioral)
- problem_solving: structured reasoning, consideration of alternatives, edge cases, measurement
- communication: clarity and structure of the explanation
- confidence_indicators: ONLY observable text signals: hedging, excessive self-correction, unclear structure,
  very short answers vs. a clear well-structured explanation. Never infer personality or mental state.

Calibration: 9-10 exceptional and precise; 7-8 solid; 5-6 acceptable but shallow; 3-4 weak; 0-2 missing or wrong.
Set is_incorrect=true only for clear factual errors. Set is_off_topic=true if the answer does not address the
question. Set is_vague=true if the answer is generic and lacks concrete details.
Answers may come from speech-to-text: ignore transcription artifacts, filler words and grammar slips.

{SAFETY_RULES}"""


def build(
    *,
    question: str,
    category: str,
    expected: list[str],
    rubric: list[str],
    answer: str,
    claim: str | None,
    role: str,
    level: str,
) -> tuple[str, str]:
    claim_block = f"\nResume claim being verified:\n{wrap_untrusted('resume_claim', claim, 400)}\n" if claim else ""
    user = f"""Role: {level} {role}
Question category: {category}
Question asked by the interviewer:
{question}
{claim_block}
Expected concepts:
{bullet_list(expected)}

Rubric:
{bullet_list(rubric)}

Candidate answer:
{wrap_untrusted("candidate_answer", answer, 5000)}

Return JSON with the seven integer dimensions, is_incorrect, is_off_topic, is_vague, covered_concepts (subset of the
expected concepts that were covered), strengths, weaknesses, missing_points, feedback (2-3 sentences addressed to
the candidate, for the post-interview report), improvement (concrete advice) and follow_up_required."""
    return SYSTEM, user
