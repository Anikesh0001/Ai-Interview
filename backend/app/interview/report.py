"""Final interview report.

All numbers are computed here from stored per-answer evaluations with documented, configurable
weights. When a local LLM is available it only rewrites the narrative (summary, verdict,
communication feedback); it never changes a score.
"""

from __future__ import annotations

import logging
import re
from collections import Counter, defaultdict
from datetime import UTC, datetime
from statistics import mean

from sqlalchemy.orm import Session

from app.ai.llm import get_provider
from app.ai.prompts import report_generation
from app.ai.prompts.base import PROMPT_VERSION
from app.config import get_settings
from app.data.lexicon import role_template
from app.interview.evaluator import BEHAVIORAL_CATEGORIES
from app.models import Interview, Report, SkillScore
from app.schemas import (
    DIMENSIONS,
    CandidateProfile,
    InterviewConfig,
    JDAnalysis,
    LLMReportNarrative,
)
from app.services.ats import compute_ats
from app.services.jd import classify_score, match_resume_to_jd

logger = logging.getLogger(__name__)

CATEGORY_GROUPS = {
    "technical": {"technical", "skills", "coding", "system_design", "jd_specific", "role_specific"},
    "problem_solving": {"problem_solving", "situational", "coding", "system_design"},
    "project_knowledge": {"project", "claim_verification", "resume"},
    "behavioral": {"behavioral", "hr", "intro"},
}
CATEGORY_LABELS = {
    "technical": "Technical",
    "problem_solving": "Problem Solving",
    "project_knowledge": "Project Knowledge",
    "communication": "Communication",
    "behavioral": "Behavioral",
    "role_fit": "Role Fit",
    "resume_knowledge": "Resume Knowledge",
}
CONFIDENCE_POINTS = {"High": 100.0, "Medium": 65.0, "Low": 25.0}
DIMENSION_LABELS = {
    "technical_correctness": "Technical correctness",
    "relevance": "Relevance",
    "depth": "Depth",
    "completeness": "Completeness",
    "problem_solving": "Problem solving",
    "communication": "Communication",
    "confidence_indicators": "Confidence indicators",
}
DISCLAIMERS = [
    "The InterviewForge Readiness Score is a practice metric. It is not a probability of being hired.",
    "The ATS score is an ATS-style compatibility estimate; real applicant tracking systems differ.",
    "Answers are evaluated on content only — never on accent, voice, identity or other personal characteristics.",
]


def _r(v: float | None) -> float | None:
    return None if v is None else round(v, 1)


def _weighted(parts: dict[str, float | None], weights: dict[str, float]) -> tuple[float | None, dict[str, float]]:
    """Weighted mean over available parts; missing parts' weight is redistributed proportionally."""
    avail = {k: v for k, v in parts.items() if v is not None and k in weights}
    total = sum(weights[k] for k in avail)
    if not avail or total <= 0:
        return None, {}
    eff = {k: weights[k] / total for k in avail}
    return sum(avail[k] * eff[k] for k in avail), eff


def _readable_list(items: list[str], limit: int = 3) -> str:
    items = [i for i in items if i][:limit]
    if not items:
        return ""
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def build_report(db: Session, interview: Interview) -> dict:
    settings = get_settings()
    cfg = InterviewConfig.model_validate(interview.config)
    profile = CandidateProfile.model_validate(interview.resume.profile.data if interview.resume.profile else {})
    jd = JDAnalysis.model_validate(interview.job_description.analysis) if interview.job_description else None
    resume = interview.resume

    ats = compute_ats(
        resume.text,
        profile,
        target_role=cfg.target_role,
        experience_level=cfg.experience_level,
        jd=jd,
        parse_warnings=resume.parse_warnings,
        page_count=resume.page_count,
    )
    jd_match = match_resume_to_jd(profile, resume.text, jd) if jd else None

    rows = []
    main_no = 0
    for q in interview.questions:
        if not q.is_follow_up:
            main_no += 1
        if q.answer is None:
            continue
        ev = q.answer.evaluation
        if ev is None:
            continue
        rows.append((main_no, q, q.answer, ev))

    scored = [r for r in rows]
    answer_scores = [ev.score for _, _, _, ev in scored]

    def group_mean(cats: set[str]) -> float | None:
        vals = [ev.score for _, q, _, ev in scored if q.category in cats]
        return mean(vals) if vals else None

    category_scores: dict[str, float | None] = {k: group_mean(v) for k, v in CATEGORY_GROUPS.items()}
    if category_scores["problem_solving"] is None and scored:
        category_scores["problem_solving"] = mean(ev.dimensions["problem_solving"] * 10 for *_, ev in scored)
    content = [ev for _, _, a, ev in scored if not a.skipped]
    category_scores["communication"] = mean(ev.dimensions["communication"] * 10 for ev in content) if content else None

    tpl = role_template(cfg.target_role)
    role_skills = set(tpl["core_skills"]) | set(tpl["nice_skills"])
    if jd:
        role_skills |= {s for r in jd.required_skills + jd.preferred_skills for s in r.split(" or ")}
    role_vals = [
        ev.score for _, q, _, ev in scored if (q.skill and q.skill in role_skills) or q.category == "jd_specific"
    ]
    role_answers = mean(role_vals) if role_vals else (mean(answer_scores) if answer_scores else None)
    if role_answers is not None and jd_match is not None:
        category_scores["role_fit"] = 0.7 * role_answers + 0.3 * jd_match.score
    else:
        category_scores["role_fit"] = role_answers
    resume_vals = [ev.score for _, q, _, ev in scored if q.category in ("intro", "resume", "claim_verification")]
    resume_knowledge = mean(resume_vals) if resume_vals else None

    interview_weights = settings.weights("interview")
    interview_score, interview_eff = _weighted(category_scores, interview_weights)

    claims = []
    for _, q, a, ev in scored:
        if q.category == "claim_verification" and q.claim and ev.claim_confidence:
            note = {
                "High": "Explained clearly, including how the result was achieved or measured.",
                "Medium": "Partially explained; more specifics on method or measurement would strengthen it.",
                "Low": "Unable to substantiate the claim during this interview.",
            }[ev.claim_confidence]
            claims.append(
                {
                    "claim": q.claim,
                    "confidence": ev.claim_confidence,
                    "note": note,
                    "question": q.text,
                    "skipped": a.skipped,
                }
            )
    # keep the most informative (latest) verdict per claim
    by_claim: dict[str, dict] = {}
    for c in claims:
        prev = by_claim.get(c["claim"])
        if prev is None or CONFIDENCE_POINTS[c["confidence"]] > CONFIDENCE_POINTS[prev["confidence"]]:
            by_claim[c["claim"]] = c
    claims = list(by_claim.values())

    if claims:
        evidence = mean(CONFIDENCE_POINTS[c["confidence"]] for c in claims)
    else:
        evidence = (
            category_scores["project_knowledge"]
            if category_scores["project_knowledge"] is not None
            else interview_score
        )

    readiness_weights = settings.weights("readiness")
    readiness_parts = {
        "interview": interview_score,
        "jd_match": jd_match.score if jd_match else None,
        "ats": ats.overall,
        "evidence": evidence,
    }
    readiness, readiness_eff = (
        _weighted(readiness_parts, readiness_weights) if interview_score is not None else (None, {})
    )

    # ---- skills table
    by_skill: dict[str, list] = defaultdict(list)
    for _, q, a, ev in scored:
        if q.skill:
            by_skill[q.skill].append((q, a, ev))
    skills_table = []
    for skill, items in by_skill.items():
        sc = mean(ev.score for _, _, ev in items)
        covered = [c for _, _, ev in items for c in ev.covered_concepts]
        missing = [m for _, _, ev in items for m in ev.missing_points]
        if covered:
            evidence_txt = f"Covered: {_readable_list(list(dict.fromkeys(covered)), 4)}."
        else:
            first = next((a.text for _, a, _ in items if a.text), "")
            evidence_txt = (first[:140] + ("…" if len(first) > 140 else "")) if first else "No answer given."
        if sc >= 75:
            rec = f"Strong. Keep a concrete {skill} example ready that shows depth and trade-offs."
        elif sc >= 60:
            rec = f"Practice explaining {skill} with a real example and the trade-offs you made."
        else:
            gap = _readable_list(list(dict.fromkeys(missing)), 3)
            rec = f"Review {skill} fundamentals" + (f", especially {gap}." if gap else ".")
        skills_table.append(
            {"skill": skill, "score": _r(sc), "evidence": evidence_txt, "recommendation": rec, "questions": len(items)}
        )
    skills_table.sort(key=lambda s: -s["score"])

    # ---- question-by-question review
    questions = []
    for number, q, a, ev in rows:
        questions.append(
            {
                "id": q.id,
                "number": number,
                "question": q.text,
                "category": q.category,
                "phase": q.phase,
                "difficulty": q.difficulty,
                "skill": q.skill,
                "source": q.source,
                "is_follow_up": q.is_follow_up,
                "answer": a.text,
                "skipped": a.skipped,
                "input_mode": a.input_mode,
                "score": ev.score,
                "classification": ev.classification,
                "dimensions": ev.dimensions,
                "strengths": ev.strengths,
                "missing": ev.missing_points,
                "weaknesses": ev.weaknesses,
                "feedback": ev.feedback,
                "improvement": ev.improvement,
                "ideal_answer": q.ideal_answer
                or (
                    "Use STAR: situation, task, your actions, measurable result, lesson learned."
                    if q.category in BEHAVIORAL_CATEGORIES
                    else ""
                ),
                "claim": q.claim if q.category == "claim_verification" else None,
                "claim_confidence": ev.claim_confidence,
                "evaluator": ev.evaluator,
            }
        )
    unanswered = [q.text for q in interview.questions if q.answer is None]

    # ---- strengths / weaknesses
    labelled = [(CATEGORY_LABELS[k], v) for k, v in category_scores.items() if v is not None]
    strongest = [
        {"area": name, "score": _r(v), "detail": f"{name} answers averaged {v:.0f}/100."}
        for name, v in sorted(labelled, key=lambda x: -x[1])
        if v >= 65
    ][:3]
    strongest += [
        {"area": s["skill"], "score": s["score"], "detail": s["evidence"]} for s in skills_table if s["score"] >= 70
    ][:3]
    weakest = [
        {"area": name, "score": _r(v), "detail": f"{name} answers averaged {v:.0f}/100."}
        for name, v in sorted(labelled, key=lambda x: x[1])
        if v < 60
    ][:3]
    weakest += [
        {"area": s["skill"], "score": s["score"], "detail": s["recommendation"]}
        for s in sorted(skills_table, key=lambda s: s["score"])
        if s["score"] < 60
    ][:3]

    # ---- technical gaps and study topics
    # Concept gaps only count for knowledge questions (not project/behavioral templates).
    knowledge_cats = {"technical", "skills", "coding", "system_design", "role_specific"}
    topic_label = {
        "coding": "Coding & algorithms",
        "system_design": "System design",
        "jd_specific": "Job requirements",
        "technical": "Technical fundamentals",
    }
    gap_by_topic: dict[str, list[str]] = defaultdict(list)
    for _, q, _, ev in scored:
        if q.category in knowledge_cats and ev.score < 70 and ev.missing_points:
            topic = q.skill or topic_label.get(q.category, "Technical fundamentals")
            gap_by_topic[topic].extend(m for m in ev.missing_points if m not in gap_by_topic[topic])
    technical_gaps = [f"{topic}: {_readable_list(missing, 4)}" for topic, missing in gap_by_topic.items()][:8]

    study: list[dict] = []
    seen_topics: set[str] = set()

    def add_topic(topic: str, reason: str, priority: str) -> None:
        key = topic.lower()
        if key not in seen_topics and topic:
            seen_topics.add(key)
            study.append({"topic": topic, "reason": reason, "priority": priority})

    for s in sorted(skills_table, key=lambda s: s["score"]):
        if s["score"] < 65:
            missed = gap_by_topic.get(s["skill"], [])
            reason = f"Scored {s['score']:.0f}/100 in the interview"
            reason += f"; missed {_readable_list(missed, 3)}." if missed else "."
            add_topic(s["skill"], reason, "High")
    for topic, missing in gap_by_topic.items():
        add_topic(topic, f"Answers missed: {_readable_list(missing, 3)}.", "High" if len(missing) > 2 else "Medium")
    if jd_match:
        for r in jd_match.requirements:
            if r.kind == "required_skill" and r.status == "missing":
                add_topic(r.requirement, "Required by the job description but not shown on your resume.", "High")
    for s in ats.missing_important_skills[:3]:
        add_topic(s, f"Core skill for {cfg.target_role} roles not found on your resume.", "Medium")
    if category_scores["behavioral"] is not None and category_scores["behavioral"] < 65:
        add_topic("STAR storytelling", "Behavioral answers lacked a clear situation-action-result structure.", "Medium")
    if category_scores["project_knowledge"] is not None and category_scores["project_knowledge"] < 65:
        add_topic(
            "Explaining your own projects",
            "Project answers needed more detail on architecture, decisions and impact.",
            "High",
        )
    study = study[:10]

    # ---- communication feedback (content-based only)
    lengths = [len(a.text.split()) for _, _, a, _ in scored if not a.skipped]
    avg_len = mean(lengths) if lengths else 0
    comm = category_scores["communication"]
    conf = mean(ev.dimensions["confidence_indicators"] * 10 for ev in content) if content else None
    if not lengths:
        communication_feedback = "No answers were recorded, so communication could not be assessed."
    else:
        bits = []
        if avg_len < 40:
            bits.append(
                f"Your answers averaged {avg_len:.0f} words, which is short for an interview; aim for 90-180 words with one concrete example."
            )
        elif avg_len > 260:
            bits.append(
                f"Your answers averaged {avg_len:.0f} words; lead with the key point first and keep answers under about two minutes."
            )
        else:
            bits.append(f"Your answers averaged {avg_len:.0f} words, a reasonable length for spoken answers.")
        if comm is not None:
            bits.append(
                "Explanations were generally clear and structured."
                if comm >= 70
                else "Structure your answers more explicitly: state the point, give the example, then the result."
            )
        if conf is not None and conf < 60:
            bits.append(
                "Frequent hedging ('I think', 'maybe') weakened otherwise reasonable points; state what you know directly."
            )
        communication_feedback = " ".join(bits)

    # ---- narrative (deterministic first)
    top_skills = [s["skill"] for s in skills_table if s["score"] >= 70][:3]
    weak_bits = [s["skill"] for s in sorted(skills_table, key=lambda s: s["score"]) if s["score"] < 60][:2]
    weak_bits += list(gap_by_topic)[:2]
    weak_bits = list(dict.fromkeys(weak_bits))[:3]
    strong_areas = [a["area"] for a in strongest[:2]]
    if interview_score is None:
        summary = "No answers were submitted, so this interview could not be scored."
    else:
        positive = _readable_list(top_skills) or _readable_list([a.lower() for a in strong_areas]) or "the basics"
        summary = f"You demonstrated solid {positive} in this {cfg.interview_type.lower()} interview"
        summary += f" but struggled to explain {_readable_list(weak_bits)}." if weak_bits else " with no major gaps."
        if claims and any(c["confidence"] == "Low" for c in claims):
            summary += " Some resume claims could not be substantiated during the interview."

    lvl = cfg.experience_level.lower()
    role = cfg.target_role
    focus = _readable_list(weak_bits or [a["area"].lower() for a in weakest[:2]]) or "depth and concrete examples"
    if interview_score is None:
        verdict = "Complete an interview to receive a verdict."
    elif interview_score >= 80:
        verdict = f"Strong performance for {lvl} {role} interviews. Sharpen {focus} to stand out at the next level."
    elif interview_score >= 65:
        verdict = f"Ready for many {lvl} {role} interviews; improving {focus} first would make your answers noticeably stronger."
    elif interview_score >= 50:
        verdict = f"Approaching readiness for {lvl} {role} interviews. Focus on {focus} before your next round."
    else:
        verdict = f"More preparation is needed for {lvl} {role} interviews. Build fundamentals in {focus} and practise structured answers."

    narrative_source = "rules"
    provider = get_provider()
    if interview_score is not None and provider.is_available():
        findings = [f"[{q['classification']}] {q['question'][:90]} — {q['feedback'][:120]}" for q in questions]
        system, user = report_generation.build(
            role=role,
            level=cfg.experience_level,
            scores={"interview": _r(interview_score), **{k: _r(v) for k, v in category_scores.items()}},
            strengths=[a["area"] for a in strongest],
            weaknesses=[a["area"] for a in weakest],
            findings=findings,
        )

        def validate(n: LLMReportNarrative) -> str | None:
            blob = f"{n.executive_summary} {n.verdict} {n.communication_feedback}"
            if re.search(r"probabilit|chance of (getting )?hired|will (be|get) hired|guarantee", blob, re.I):
                return "Do not mention hiring probability or guarantees."
            return None

        narrative = provider.complete_structured(system, user, LLMReportNarrative, validator=validate)
        if narrative is not None:
            summary, verdict = narrative.executive_summary, narrative.verdict
            if narrative.communication_feedback:
                communication_feedback = narrative.communication_feedback
            narrative_source = "llm"

    action_plan = []
    for t in study[:3]:
        action_plan.append(f"Study {t['topic']}: {t['reason']}")
    if any(c["confidence"] != "High" for c in claims):
        action_plan.append(
            "For every metric on your resume, write down the baseline, what you changed, how you measured it and the result."
        )
    if category_scores["behavioral"] is not None and category_scores["behavioral"] < 70:
        action_plan.append("Prepare 4-5 STAR stories (conflict, failure, ownership, fast learning, tight deadline).")
    for rec in ats.recommendations[:2]:
        action_plan.append(f"Resume: {rec}")
    action_plan.append("Do another mock interview in a week and compare your scores.")
    action_plan = list(dict.fromkeys(action_plan))[:7]

    dim_avgs = {d: _r(mean(ev.dimensions[d] for ev in content)) if content else None for d in DIMENSIONS}
    evaluators = Counter(ev.evaluator for *_, ev in scored)
    started = interview.started_at or interview.created_at
    if started is not None and started.tzinfo is None:
        started = started.replace(tzinfo=UTC)
    duration = int((datetime.now(UTC) - started).total_seconds()) if started else None

    report = {
        "interview_id": interview.id,
        "generated_at": datetime.now(UTC).isoformat(),
        "candidate_name": profile.name,
        "config": cfg.model_dump(),
        "duration_seconds": duration,
        "ai_mode": "llm" if (evaluators.get("llm") or narrative_source == "llm") else "offline",
        "model": interview.llm_model if interview.llm_used else None,
        "evaluators": dict(evaluators),
        "narrative_source": narrative_source,
        "prompt_version": PROMPT_VERSION,
        "scores": {
            "ats": ats.overall,
            "ats_classification": ats.classification,
            "jd_match": jd_match.score if jd_match else None,
            "interview": _r(interview_score),
            "interview_classification": classify_score(interview_score) if interview_score is not None else None,
            "readiness": _r(readiness),
            "readiness_classification": classify_score(readiness) if readiness is not None else None,
        },
        "readiness_formula": {
            "label": "InterviewForge Readiness Score",
            "components": [
                {
                    "key": k,
                    "label": {
                        "interview": "Interview",
                        "jd_match": "JD Match",
                        "ats": "ATS",
                        "evidence": "Resume Evidence Confidence",
                    }[k],
                    "score": _r(readiness_parts[k]),
                    "weight": round(readiness_eff.get(k, 0.0), 3),
                    "configured_weight": round(readiness_weights[k], 3),
                }
                for k in readiness_weights
            ],
            "note": "Weighted average of the available components; when no job description is provided its "
            "weight is redistributed proportionally. This is a practice metric, not a hiring prediction.",
        },
        "category_scores": [
            {
                "key": k,
                "label": CATEGORY_LABELS[k],
                "score": _r(category_scores.get(k)),
                "weight": round(interview_eff.get(k, 0.0), 3),
            }
            for k in interview_weights
        ]
        + [
            {
                "key": "resume_knowledge",
                "label": CATEGORY_LABELS["resume_knowledge"],
                "score": _r(resume_knowledge),
                "weight": 0.0,
            }
        ],
        "dimension_averages": [{"key": d, "label": DIMENSION_LABELS[d], "score": dim_avgs[d]} for d in DIMENSIONS],
        "executive_summary": summary,
        "verdict": verdict,
        "communication_feedback": communication_feedback,
        "skills": skills_table,
        "questions": questions,
        "unanswered_questions": unanswered,
        "strongest_areas": strongest,
        "weakest_areas": weakest,
        "claims": claims,
        "technical_gaps": technical_gaps,
        "study_topics": study,
        "action_plan": action_plan,
        "ats": {
            "overall": ats.overall,
            "classification": ats.classification,
            "recommendations": ats.recommendations[:5],
            "missing_important_skills": ats.missing_important_skills,
            "dimensions": [d.model_dump() for d in ats.dimensions],
        },
        "jd": (
            {
                "score": jd_match.score,
                "classification": jd_match.classification,
                "matched": jd_match.matched[:12],
                "missing": jd_match.missing[:12],
                "partial": jd_match.partial[:12],
                "summary": jd_match.summary,
            }
            if jd_match
            else None
        ),
        "timeline": [
            {
                "number": q["number"],
                "score": q["score"],
                "classification": q["classification"],
                "category": q["category"],
                "is_follow_up": q["is_follow_up"],
            }
            for q in questions
        ],
        "stats": {
            "questions_answered": sum(1 for q in questions if not q["skipped"]),
            "questions_skipped": sum(1 for q in questions if q["skipped"]),
            "follow_ups": sum(1 for q in questions if q["is_follow_up"]),
            "average_answer_words": round(avg_len, 1),
        },
        "disclaimers": DISCLAIMERS,
    }

    # ---- persist
    interview.skill_scores = [
        SkillScore(skill=s["skill"], score=s["score"], question_count=s["questions"]) for s in skills_table
    ]
    if interview.report is None:
        interview.report = Report(data=report)
    else:
        interview.report.data = report
    interview.ats_score = ats.overall
    interview.jd_score = jd_match.score if jd_match else None
    interview.interview_score = _r(interview_score)
    interview.readiness_score = _r(readiness)
    db.flush()
    return report
