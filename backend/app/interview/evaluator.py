"""Answer evaluation.

The LLM (when available) or a transparent heuristic produces seven 0-10 dimension scores.
The backend *always* computes the final 0-100 score from those dimensions with configurable
weights, and assigns the classification with explicit rules, so scoring is reproducible.

Only answer content is evaluated. Nothing about accent, voice, identity or any protected
characteristic is ever an input.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.ai.llm import get_provider
from app.ai.prompts import answer_evaluation
from app.config import get_settings
from app.data.lexicon import FILLER_WORDS, HEDGE_WORDS, STAR_MARKERS
from app.data.skills import find_skills
from app.interview.textutil import concept_covered, concept_label, content_stems
from app.schemas import DIMENSIONS, AnswerEvaluationLLM, EvaluationResult

BEHAVIORAL_CATEGORIES = {"behavioral", "hr", "intro", "situational"}
DONT_KNOW_RE = re.compile(
    r"\b(i (really )?(don'?t|do not) know|no idea|not sure|i haven'?t (used|worked)|never (used|worked))\b", re.I
)
REASONING_RE = re.compile(
    r"\b(because|so that|therefore|trade-?offs?|instead of|alternatively|compared to|on the other hand|"
    r"the reason|which means|root cause|if .{0,40} then|depends on|edge case|bottleneck|measured|benchmark)\b",
    re.I,
)
STRUCTURE_RE = re.compile(
    r"\b(first(ly)?|second(ly)?|then|next|finally|after that|as a result|in summary|for example|for instance|specifically)\b",
    re.I,
)
SPECIFIC_RE = re.compile(r"(\d|%|\bms\b|\bseconds?\b|\bfor example\b|\bfor instance\b|\bspecifically\b|\be\.g\.)", re.I)
SELF_CORRECTION_RE = re.compile(r"\b(i mean|sorry|wait|no,? actually|let me rephrase)\b", re.I)
SUBSTANTIATION_RE = re.compile(
    r"\b(baseline|measur\w*|benchmark\w*|profil\w*|monitor\w*|metrics?|dashboard|grafana|prometheus|new relic|"
    r"datadog|logs?|load test\w*|jmeter|locust|explain|before and after|p\d\d|percentile|average|median)\b",
    re.I,
)


@dataclass
class AnswerSignals:
    words: int
    sentences: int
    coverage: float
    covered: list[str]
    missing: list[str]
    relevance_overlap: float
    specificity: int
    reasoning: int
    structure: int
    hedges: int
    fillers: int
    self_corrections: int
    dont_know: bool
    star: dict[str, bool]
    substantiated: bool
    technical_terms: int


def analyze_signals(question: str, answer: str, concepts: list[str], category: str) -> AnswerSignals:
    low = answer.lower()
    stems = content_stems(answer)
    words = len(re.findall(r"\b\w+\b", answer))
    sentences = max(1, len(re.findall(r"[.!?]+(\s|$)", answer)) or (1 if words else 0))
    covered = [concept_label(c) for c in concepts if concept_covered(low, stems, c)]
    missing = [concept_label(c) for c in concepts if concept_label(c) not in covered]
    coverage = len(covered) / len(concepts) if concepts else 0.5
    q_stems = content_stems(question) | {s for c in concepts for s in content_stems(c.replace("|", " "))}
    overlap = len(stems & q_stems) / max(1, min(len(q_stems), 12))
    hedges = sum(low.count(h) for h in HEDGE_WORDS)
    fillers = sum(len(re.findall(rf"(?<![a-z]){re.escape(f)}(?![a-z])", low)) for f in FILLER_WORDS)
    star = {k: any(m in low for m in markers) for k, markers in STAR_MARKERS.items()}
    return AnswerSignals(
        words=words,
        sentences=sentences,
        coverage=coverage,
        covered=covered,
        missing=missing,
        relevance_overlap=min(1.0, overlap),
        specificity=len(SPECIFIC_RE.findall(answer)),
        reasoning=len(REASONING_RE.findall(answer)),
        structure=len(STRUCTURE_RE.findall(answer)),
        hedges=hedges,
        fillers=fillers,
        self_corrections=len(SELF_CORRECTION_RE.findall(answer)),
        dont_know=bool(DONT_KNOW_RE.search(answer)),
        star=star,
        substantiated=bool(SUBSTANTIATION_RE.search(answer)) and bool(re.search(r"\d", answer)),
        technical_terms=len(find_skills(answer)),
    )


def _clamp10(v: float) -> int:
    return int(round(max(0.0, min(10.0, v))))


def heuristic_dimensions(sig: AnswerSignals, category: str) -> dict[str, int]:
    """Transparent proxy scores from observable text features (used when no LLM is available)."""
    if sig.words == 0:
        return dict.fromkeys(DIMENSIONS, 0)
    # STAR heuristics apply to story questions; the intro is judged on coverage like other questions.
    behavioral = category in BEHAVIORAL_CATEGORIES and category != "intro"
    length_factor = min(1.0, sig.words / 90)  # ~90+ words is a full spoken answer
    star_parts = sum(sig.star.values())

    if behavioral:
        technical = 3 + 4 * min(1.0, star_parts / 3) + 3 * length_factor
    else:
        technical = 1.5 + 7 * sig.coverage + min(1.5, sig.technical_terms * 0.5)
    if sig.dont_know and sig.words < 40:
        technical = min(technical, 2)

    relevance = 2 + 5 * sig.relevance_overlap + 3 * (sig.coverage if not behavioral else min(1.0, star_parts / 3))
    depth = 1 + 4 * length_factor + min(3, sig.specificity * 0.75) + min(2, sig.reasoning * 0.7)
    if behavioral:
        completeness = 1 + 7 * (star_parts / 4) + 2 * length_factor
    else:
        completeness = 1 + 7 * sig.coverage + 2 * length_factor
    problem_solving = 2 + min(5, sig.reasoning * 1.5) + min(2, sig.specificity * 0.5) + 1 * length_factor
    if behavioral and sig.star["action"] and sig.star["result"]:
        problem_solving += 2
    avg_sentence = sig.words / max(1, sig.sentences)
    communication = 4 + min(3, sig.structure * 1.0) + (2 if 8 <= avg_sentence <= 30 else 0) + 1 * length_factor
    communication -= min(3, sig.fillers * 0.5)
    confidence = 8 - min(4, sig.hedges * 1.2) - min(2, sig.fillers * 0.3) - min(2, sig.self_corrections * 0.7)
    if sig.words < 20:
        depth = min(depth, 3)
        completeness = min(completeness, 4)
        confidence -= 2
        communication = min(communication, 5)
    return {
        "technical_correctness": _clamp10(technical),
        "relevance": _clamp10(relevance),
        "depth": _clamp10(depth),
        "completeness": _clamp10(completeness),
        "problem_solving": _clamp10(problem_solving),
        "communication": _clamp10(communication),
        "confidence_indicators": _clamp10(confidence),
    }


def weighted_score(dimensions: dict[str, int], category: str) -> float:
    group = "behavioral_answer" if category in BEHAVIORAL_CATEGORIES else "answer"
    w = get_settings().weights(group)
    return round(sum(dimensions[k] * 10 * w[k] for k in DIMENSIONS), 1)


def classify(
    score: float,
    sig: AnswerSignals,
    category: str,
    *,
    has_concepts: bool,
    flags: dict[str, bool] | None = None,
) -> str:
    flags = flags or {}
    if sig.words == 0:
        return "Incomplete"
    looks_off_topic = (
        sig.words >= 12
        and sig.relevance_overlap < 0.08
        and sig.coverage == 0
        and sig.technical_terms == 0
        and not any(sig.star.values())
    )
    if flags.get("off_topic") or looks_off_topic:
        return "Off-topic"
    if flags.get("incorrect"):
        return "Incorrect"
    if sig.dont_know and sig.words < 30:
        return "Weak"
    claim_like = category in ("claim_verification", "project", "resume")
    if category == "claim_verification" and not sig.substantiated and score < 72:
        return "Suspicious"
    if score >= 85:
        return "Excellent"
    if score >= 72:
        return "Strong"
    vague = flags.get("vague") or (
        sig.words >= 25 and sig.specificity == 0 and (not has_concepts or sig.coverage < 0.34)
    )
    if vague:
        return (
            "Suspicious" if claim_like and sig.specificity == 0 and sig.words < 60 and category != "resume" else "Vague"
        )
    if sig.words < 25:
        return "Incomplete"
    if score >= 55:
        return "Acceptable"
    if has_concepts and sig.coverage < 0.6:
        return "Incomplete"
    return "Weak"


def _feedback(sig: AnswerSignals, category: str, classification: str) -> tuple[list[str], list[str], str, str]:
    strengths: list[str] = []
    weaknesses: list[str] = []
    behavioral = category in BEHAVIORAL_CATEGORIES
    if sig.covered:
        strengths.append(f"Covered key points: {', '.join(sig.covered[:4])}.")
    if sig.specificity >= 2:
        strengths.append("Used concrete specifics (numbers or examples).")
    if sig.reasoning >= 2:
        strengths.append("Explained the reasoning behind decisions.")
    if sig.structure >= 2:
        strengths.append("Answer had a clear structure.")
    if behavioral and sum(sig.star.values()) >= 3:
        strengths.append("Followed a recognisable situation-action-result structure.")
    if sig.missing and not behavioral:
        weaknesses.append(f"Did not address: {', '.join(sig.missing[:4])}.")
    if sig.words < 25:
        weaknesses.append("The answer was very short for an interview response.")
    if sig.specificity == 0 and sig.words >= 15:
        weaknesses.append("Lacked concrete details such as numbers, tools or a specific example.")
    if sig.hedges >= 2:
        weaknesses.append("Frequent hedging language made the answer sound less certain.")
    if behavioral:
        missing_star = [k for k, v in sig.star.items() if not v]
        if missing_star and sig.words > 0:
            weaknesses.append(f"STAR elements not clearly stated: {', '.join(missing_star)}.")
    if category == "claim_verification" and not sig.substantiated:
        weaknesses.append("Did not explain how the result was measured or verified.")

    feedback = {
        "Excellent": "A thorough, specific answer that would hold up well in a real interview.",
        "Strong": "A solid answer. A bit more depth or a concrete example would make it excellent.",
        "Acceptable": "A reasonable answer that covers the basics but stays at the surface.",
        "Weak": "The answer missed most of what the interviewer was looking for.",
        "Vague": "The answer stayed general; interviewers look for concrete actions, numbers and decisions.",
        "Incorrect": "Part of the answer was technically inaccurate.",
        "Off-topic": "The answer did not address the question that was asked.",
        "Suspicious": "The answer did not substantiate the claim with how it was achieved or measured.",
        "Incomplete": "The answer addressed only part of the question.",
    }[classification]
    if behavioral:
        improvement = "Use STAR: one sentence of context, your specific actions (say 'I', not just 'we'), a measurable result, and what you learned."
    elif category == "claim_verification":
        improvement = "Prepare the story behind each metric on your resume: baseline, what you changed, how you measured it, and the result."
    elif category == "project":
        improvement = "Describe the problem, architecture and your own contribution, then a trade-off you made and what you'd change."
    elif sig.missing:
        improvement = f"Strengthen the answer by explaining {', '.join(sig.missing[:3])}, with a short example from your own work."
    else:
        improvement = "Add a concrete example from your experience and explain the trade-offs behind your approach."
    return strengths, weaknesses, feedback, improvement


def claim_confidence(category: str, sig: AnswerSignals, score: float) -> str | None:
    if category != "claim_verification":
        return None
    if sig.substantiated and score >= 65:
        return "High"
    if score >= 55 or sig.substantiated:
        return "Medium"
    return "Low"


def evaluate_answer(
    *,
    question: str,
    category: str,
    expected_concepts: list[str],
    rubric: list[str],
    answer: str,
    claim: str | None,
    role: str,
    level: str,
) -> EvaluationResult:
    answer = (answer or "").strip()
    sig = analyze_signals(question, answer, expected_concepts, category)
    flags: dict[str, bool] = {}
    evaluator = "heuristic"
    llm_result: AnswerEvaluationLLM | None = None
    if sig.words > 0:
        provider = get_provider()
        if provider.is_available():
            system, user = answer_evaluation.build(
                question=question,
                category=category,
                expected=expected_concepts,
                rubric=rubric,
                answer=answer,
                claim=claim,
                role=role,
                level=level,
            )
            llm_result = provider.complete_structured(system, user, AnswerEvaluationLLM, temperature=0.1)

    if llm_result is not None:
        evaluator = "llm"
        dims = {k: int(getattr(llm_result, k)) for k in DIMENSIONS}
        flags = {
            "incorrect": llm_result.is_incorrect,
            "off_topic": llm_result.is_off_topic,
            "vague": llm_result.is_vague,
        }
        covered = llm_result.covered_concepts or sig.covered
    else:
        dims = heuristic_dimensions(sig, category)
        covered = sig.covered

    score = weighted_score(dims, category)
    classification = classify(score, sig, category, has_concepts=bool(expected_concepts), flags=flags)
    strengths, weaknesses, feedback, improvement = _feedback(sig, category, classification)
    missing = sig.missing
    if llm_result is not None:
        strengths = llm_result.strengths[:5] or strengths
        weaknesses = llm_result.weaknesses[:5] or weaknesses
        missing = llm_result.missing_points[:6] or missing
        feedback = llm_result.feedback or feedback
        improvement = llm_result.improvement or improvement

    follow_up = classification in ("Weak", "Vague", "Incorrect", "Suspicious", "Incomplete")
    conf = claim_confidence(category, sig, score)
    if conf is None and claim and classification == "Suspicious":
        conf = "Low"
    return EvaluationResult(
        dimensions=dims,
        score=score,
        classification=classification,
        covered_concepts=covered[:12],
        strengths=strengths,
        weaknesses=weaknesses,
        missing_points=missing,
        feedback=feedback,
        improvement=improvement,
        follow_up_required=follow_up,
        claim_confidence=conf,
        evaluator=evaluator,
    )
