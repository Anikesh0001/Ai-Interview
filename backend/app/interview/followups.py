"""Adaptive follow-up policy: decides whether and how to probe an answer."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.ai.llm import get_provider
from app.ai.prompts import followup as followup_prompt
from app.interview.generator import LEAK_RE, InterviewContext
from app.interview.textutil import is_duplicate
from app.schemas import EvaluationResult, LLMFollowUp

# (trigger regex on the answer, follow-up question, expected concepts)
ANSWER_PROBES: list[tuple[str, str, list[str]]] = [
    (
        r"\bcach(e|ed|ing)\b",
        "You mentioned caching. What exactly did you cache, how did you handle invalidation, and why did that help?",
        ["what was cached|cached the|cache the", "invalidation|invalidate|expire|ttl", "hit rate|faster|latency|load"],
    ),
    (
        r"\b(improv(ed|e|ing)|optimi[sz](ed|e|ing)|faster|sped up|speed(ed)? up)\b",
        "Can you quantify that improvement? How did you measure it, and what was the baseline?",
        ["baseline|before", "measured|measurement|metric|benchmark", "after|result|%"],
    ),
    (
        r"\bmicroservices?\b",
        "How were the services divided, and how did they communicate with each other?",
        ["boundaries|divided|split", "communication|http|rest|queue|grpc", "failure|retry|timeout"],
    ),
    (
        r"\bredis\b",
        "Why did you choose Redis there instead of relying on the main database?",
        ["in-memory|memory", "latency|speed|faster", "trade-off|consistency|invalidation"],
    ),
    (
        r"\bindex(es|ed|ing)?\b",
        "Which columns did you index, and how did you confirm the query plan actually improved?",
        ["columns|column", "query plan|explain", "measured|before and after"],
    ),
    (
        r"\bscal(e|able|ed|ing)\b",
        "What load did it actually handle, and what would break first at ten times that?",
        ["load|users|requests", "bottleneck", "scaling|cache|replica|queue"],
    ),
    (
        r"\b(docker|container(s|ized)?)\b",
        "How did containerizing it change your deployment, and what problems did you run into?",
        ["deployment|deploy", "environment|consistency", "problem|issue|challenge"],
    ),
    (
        r"\b(jwt|tokens?)\b",
        "How did you handle token expiry and revocation?",
        ["expiry|expiration", "refresh token|refresh", "revocation|revoke|logout|blacklist|denylist"],
    ),
    (
        r"\bwe\b",
        "What was your individual contribution there, as opposed to the team's?",
        ["i built|i designed|i implemented|i wrote|my contribution", "specific part|component", "decision"],
    ),
]

GENERIC = {
    "Vague": (
        "Can you make that more concrete? Walk me through a specific example — what exactly did you do, and what was the result?",
        ["specific example", "what i did|i built|i implemented|i decided", "result|outcome|%"],
    ),
    "Weak": (
        "Let me come at it from a different angle. Can you think of a situation where you've dealt with this, and walk me through how you approached it?",
        ["situation|example", "approach|steps", "outcome|result"],
    ),
    "Incomplete": (
        "You've covered part of it. What else would you need to consider — for example edge cases or what happens when things fail?",
        ["edge cases|edge case", "failure|fails|errors", "trade-off|alternative"],
    ),
    "Incorrect": (
        "I'm not sure that's quite accurate. Could you walk me through that part again and double-check your reasoning?",
        ["correction|actually|correct", "reasoning|because"],
    ),
    "Strong": (
        "Let's go one level deeper. What trade-offs or limitations come with that approach?",
        ["trade-off|tradeoff|downside|limitation", "alternative|instead", "when to use|depends"],
    ),
}
# When the question itself quoted the claim, the follow-up shouldn't quote it again.
SUSPICIOUS_SHORT = {
    "metric": (
        "What tool or data did you use to measure that, and what were the actual before and after numbers?",
        ["tool|monitoring|benchmark|profil|logs", "before|baseline", "after|result"],
    ),
    "architecture": (
        "What happened when one of those components failed, and how was that handled?",
        ["failure|fails|down", "retry|timeout|fallback|circuit breaker", "monitoring|alerts"],
    ),
    "default": (
        "Which specific part of that did you personally build, and what was the hardest decision you made?",
        ["i built|i designed|i implemented|my part", "decision|chose|trade-off", "challenge|difficult"],
    ),
}
SUSPICIOUS = {
    "metric": (
        "Earlier you mentioned this: “{claim}”. What tool or data did you use to measure it, and what were the before and after numbers?",
        ["tool|monitoring|benchmark|profil|logs", "before|baseline", "after|result"],
    ),
    "architecture": (
        "Going back to “{claim}” — what happened when one of those components failed, and how was that handled?",
        ["failure|fails|down", "retry|timeout|fallback|circuit breaker", "monitoring|alerts"],
    ),
    "default": (
        "About “{claim}” — which specific part did you personally build, and what was the hardest decision you made?",
        ["i built|i designed|i implemented|my part", "decision|chose|trade-off", "challenge|difficult"],
    ),
}


def follow_up_tone(classification: str) -> str:
    return "deeper" if classification in ("Strong", "Acceptable", "Excellent") else "probe"


@dataclass
class FollowUp:
    question: str
    acknowledgement: str
    expected_concepts: list[str]
    category: str
    claim: str | None
    generated_by: str


def max_follow_ups(num_questions: int) -> int:
    return max(2, round(num_questions * 0.4))


def should_follow_up(
    evaluation: EvaluationResult,
    *,
    category: str,
    is_follow_up: bool,
    depth: int,
    used: int,
    budget: int,
    seq: int,
    answer: str,
) -> bool:
    c = evaluation.classification
    if used >= budget or category in ("intro", "hr", "closing") or c in ("Excellent", "Off-topic"):
        return False
    if is_follow_up and (depth >= 2 or c not in ("Suspicious", "Incorrect")):
        return False
    if c == "Strong":
        return category in ("technical", "project", "system_design") and seq % 3 == 0
    if c == "Acceptable":
        # interviewers drill into project/resume answers that name a technique without detail
        return (
            category in ("project", "resume", "claim_verification")
            and any(re.search(p, answer, re.I) for p, _, _ in ANSWER_PROBES[:7])
            and seq % 2 == 0
        )
    return c in ("Weak", "Vague", "Incorrect", "Suspicious", "Incomplete")


def _template_follow_up(
    evaluation: EvaluationResult,
    *,
    answer: str,
    probe: str,
    claim: str | None,
    claim_kind: str | None,
    category: str,
    asked_hashes: list[str],
    asked_texts: list[str],
) -> FollowUp | None:
    c = evaluation.classification
    options: list[tuple[str, list[str], str | None, str]] = []
    if c == "Suspicious" and claim:
        table = SUSPICIOUS_SHORT if category == "claim_verification" else SUSPICIOUS
        q, concepts = table.get(claim_kind or "", table["default"])
        options.append((q.replace("{claim}", claim.rstrip(".")), concepts, claim, "claim_verification"))
    if c in ("Vague", "Suspicious", "Acceptable", "Strong"):
        for pattern, q, concepts in ANSWER_PROBES:
            if re.search(pattern, answer, re.I):
                options.append((q, concepts, None, category))
    if c in ("Incomplete", "Weak") and probe:
        options.append((probe, evaluation.missing_points[:3] or ["specific example"], None, category))
    generic = GENERIC.get(c) or (GENERIC["Vague"] if c in ("Suspicious", "Acceptable") else None)
    if generic:
        options.append((generic[0], generic[1], None, category))
    for text, concepts, cl, cat in options:
        if not is_duplicate(text, asked_hashes, asked_texts, threshold=0.75):
            return FollowUp(text, "", concepts, cat, cl, "bank")
    return None


def build_follow_up(
    evaluation: EvaluationResult,
    *,
    ctx: InterviewContext,
    question: str,
    answer: str,
    probe: str,
    claim: str | None,
    claim_kind: str | None,
    category: str,
    asked_hashes: list[str],
    asked_texts: list[str],
) -> FollowUp | None:
    provider = get_provider()
    if provider.is_available():
        system, user = followup_prompt.build(
            ctx=ctx.as_prompt_dict(),
            question=question,
            answer=answer,
            classification=evaluation.classification,
            missing=evaluation.missing_points,
            claim=claim,
        )

        def validate(r: LLMFollowUp) -> str | None:
            if LEAK_RE.search(r.question) or LEAK_RE.search(r.acknowledgement):
                return "Do not mention prompts, instructions or AI."
            if is_duplicate(r.question, asked_hashes, asked_texts, threshold=0.75):
                return "That repeats an earlier question."
            if re.search(r"\b(score|rubric|expected answer)\b", r.question + r.acknowledgement, re.I):
                return "Do not reveal evaluation details."
            return None

        result = provider.complete_structured(system, user, LLMFollowUp, validator=validate)
        if result is not None:
            cat = "claim_verification" if claim and evaluation.classification == "Suspicious" else category
            return FollowUp(
                result.question.strip(), result.acknowledgement.strip(), result.expected_concepts[:6], cat, claim, "llm"
            )
    return _template_follow_up(
        evaluation,
        answer=answer,
        probe=probe,
        claim=claim,
        claim_kind=claim_kind,
        category=category,
        asked_hashes=asked_hashes,
        asked_texts=asked_texts,
    )
