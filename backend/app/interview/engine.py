"""Interview orchestration: create, start, answer, skip, finish. Persists after every step."""

from __future__ import annotations

import logging
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.ai.llm import get_provider
from app.config import get_settings
from app.data.question_bank import CLOSING_LINES
from app.interview import phrasing
from app.interview.evaluator import evaluate_answer
from app.interview.followups import build_follow_up, follow_up_tone, max_follow_ups, should_follow_up
from app.interview.generator import DIFFICULTIES, GeneratedQuestion, InterviewContext, generate_question
from app.interview.planner import build_plan
from app.interview.state import QUESTION_STATES, State, assert_transition
from app.interview.textutil import question_hash
from app.models import (
    Answer,
    Evaluation,
    Interview,
    InterviewEvent,
    InterviewQuestion,
    JobDescription,
    Resume,
)
from app.schemas import (
    AnswerRequest,
    CandidateProfile,
    CurrentQuestionOut,
    EvaluationResult,
    InterviewConfig,
    InterviewerOut,
    InterviewOut,
    JDAnalysis,
    MessageOut,
    ProgressOut,
)
from app.services.ats import compute_ats
from app.services.jd import match_resume_to_jd

logger = logging.getLogger(__name__)


class InterviewError(Exception):
    def __init__(self, user_message: str, status_code: int = 400):
        super().__init__(user_message)
        self.user_message = user_message
        self.status_code = status_code


# SQLite allows one writer at a time, and LLM calls can take minutes on a laptop CPU. So every step below
# does its slow LLM work *before* its first write (sessions don't autoflush), then writes and commits at once.
# Steps on the same interview are also serialized: a duplicate submit (double click, page reload mid-request)
# waits for the first one and then sees its result, instead of racing it.
_interview_locks: dict[str, threading.Lock] = {}
_interview_locks_guard = threading.Lock()


@contextmanager
def interview_lock(interview_id: str) -> Iterator[None]:
    with _interview_locks_guard:
        lock = _interview_locks.setdefault(interview_id, threading.Lock())
    with lock:
        yield


def _now() -> datetime:
    return datetime.now(UTC)


def _aware(dt: datetime | None) -> datetime | None:
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


# ---------------------------------------------------------------- helpers


def _profile(interview: Interview) -> CandidateProfile:
    return CandidateProfile.model_validate(interview.resume.profile.data if interview.resume.profile else {})


def _jd(interview: Interview) -> JDAnalysis | None:
    jd = interview.job_description
    return JDAnalysis.model_validate(jd.analysis) if jd else None


def _context(interview: Interview) -> InterviewContext:
    cfg = InterviewConfig.model_validate(interview.config)
    jd = _jd(interview)
    jd_summary = ""
    if jd:
        jd_summary = (
            f"Title: {jd.title}\nRequired: {', '.join(jd.required_skills)}\nPreferred: {', '.join(jd.preferred_skills)}\n"
            f"Responsibilities: {'; '.join(jd.responsibilities[:6])}"
        )
    return InterviewContext(
        role=cfg.target_role,
        level=cfg.experience_level,
        personality=cfg.personality,
        profile=_profile(interview),
        resume_text=interview.resume.text,
        jd_summary=jd_summary,
        answer_history=list(interview.runtime.get("history", [])),
        seed=int(interview.runtime.get("seed", 0)),
    )


def _next_question_seq(interview: Interview) -> int:
    return (interview.questions[-1].seq + 1) if interview.questions else 1


def _event(
    db: Session,
    interview: Interview,
    *,
    type_: str,
    role: str | None = None,
    text: str = "",
    question_id: str | None = None,
    meta: dict | None = None,
) -> None:
    seq = (interview.events[-1].seq + 1) if interview.events else 1
    interview.events.append(
        InterviewEvent(seq=seq, type=type_, role=role, text=text, question_id=question_id, meta=meta or {})
    )
    db.flush()


def _transition(db: Session, interview: Interview, new: str) -> None:
    if interview.state == new:
        return
    assert_transition(interview.state, new)
    _event(db, interview, type_="state", meta={"from": interview.state, "to": new})
    interview.state = new


def _set_runtime(interview: Interview, **values) -> None:
    rt = dict(interview.runtime or {})
    rt.update(values)
    interview.runtime = rt  # reassign so SQLAlchemy detects the change


def _asked(interview: Interview) -> tuple[list[str], list[str]]:
    return list(interview.asked_hashes or []), [q.text for q in interview.questions]


# ---------------------------------------------------------------- lifecycle


def create_interview(db: Session, resume: Resume, config: InterviewConfig, jd_row: JobDescription | None) -> Interview:
    if resume.profile is None:
        raise InterviewError("This resume has not been analyzed yet. Please re-upload it.", 409)
    profile = CandidateProfile.model_validate(resume.profile.data)
    jd = JDAnalysis.model_validate(jd_row.analysis) if jd_row else None
    jd_match = match_resume_to_jd(profile, resume.text, jd) if jd else None
    ats = compute_ats(
        resume.text,
        profile,
        target_role=config.target_role,
        experience_level=config.experience_level,
        jd=jd,
        parse_warnings=resume.parse_warnings,
        page_count=resume.page_count,
    )
    plan = build_plan(config, profile, jd, jd_match)
    interview = Interview(
        resume_id=resume.id,
        jd_id=jd_row.id if jd_row else None,
        config=config.model_dump(),
        plan=plan,
        state=State.CREATED.value,
        asked_hashes=[],
        ats_score=ats.overall,
        jd_score=jd_match.score if jd_match else None,
        runtime={"difficulty": config.difficulty, "weak_streak": 0, "history": []},
    )
    db.add(interview)
    db.flush()
    seed = 0 if get_settings().test_mode else int(interview.id[:6], 16)
    _set_runtime(interview, seed=seed)
    _event(db, interview, type_="state", meta={"from": None, "to": State.CREATED.value})
    db.commit()
    return interview


def _prepare_main(interview: Interview) -> GeneratedQuestion | None:
    """Generate the next planned question (may call the LLM; writes nothing). None when the plan is exhausted."""
    if interview.plan_index >= len(interview.plan):
        return None
    slot = interview.plan[interview.plan_index]
    hashes, texts = _asked(interview)
    difficulty = interview.runtime.get("difficulty", "Medium")
    return generate_question(slot, _context(interview), difficulty, hashes, texts)


def _ask_main(db: Session, interview: Interview, lead_in: str, generated: GeneratedQuestion | None) -> None:
    """Ask the question from _prepare_main, or close the interview when the plan is exhausted."""
    if generated is None:
        _close(db, interview, lead_in)
        return
    slot = interview.plan[interview.plan_index]
    profile = _profile(interview)
    q = generated.schema
    phase = slot["phase"]
    phase_changed = interview.state not in (phase, State.CHALLENGE.value) or (
        interview.state == State.CHALLENGE.value and interview.runtime.get("phase") != phase
    )
    if interview.llm_used is False and generated.generated_by == "llm":
        interview.llm_used = True
        interview.llm_model = get_provider().model
    question = InterviewQuestion(
        seq=_next_question_seq(interview),
        phase=phase,
        text=q.question,
        category=q.category,
        difficulty=q.difficulty,
        skill=q.skill,
        source=q.source,
        expected_concepts=q.expected_concepts,
        rubric=q.evaluation_rubric,
        ideal_answer=q.ideal_answer,
        claim=q.claim or _project_claim(profile, slot),
        is_follow_up=False,
        generated_by=generated.generated_by,
    )
    interview.questions.append(question)
    db.flush()
    _transition(db, interview, phase)
    parts = [lead_in]
    if phase_changed and phase != "INTRO" and interview.plan_index > 0:
        parts.append(phrasing.transition(phase, interview.plan_index))
    parts.append(q.question)
    _event(
        db,
        interview,
        type_="message",
        role="interviewer",
        text=" ".join(p for p in parts if p),
        question_id=question.id,
        meta={"phase": phase, "category": q.category, "follow_up": False},
    )
    interview.current_question_id = question.id
    interview.asked_hashes = [*interview.asked_hashes, question_hash(q.question)]
    interview.plan_index += 1
    _set_runtime(interview, phase=phase, probe=generated.probe, claim_kind=slot.get("claim_kind"))


def _project_claim(profile: CandidateProfile, slot: dict) -> str | None:
    """Link a project question to a verifiable claim made about that project, if any."""
    if slot.get("focus_kind") == "project":
        for c in profile.claims:
            if c.subject == slot.get("focus") and c.kind in ("metric", "architecture", "scale"):
                return c.text
    return None


def _close(db: Session, interview: Interview, lead_in: str) -> None:
    closing = CLOSING_LINES[int(interview.runtime.get("seed", 0)) % len(CLOSING_LINES)]
    _transition(db, interview, State.CLOSING.value)
    _event(
        db,
        interview,
        type_="message",
        role="interviewer",
        text=" ".join(p for p in (lead_in, closing) if p),
        meta={"phase": "CLOSING"},
    )
    interview.current_question_id = None


def start_interview(db: Session, interview: Interview) -> Interview:
    if interview.state != State.CREATED.value:
        return interview  # idempotent: a refresh/double-click must not restart the interview
    cfg = InterviewConfig.model_validate(interview.config)
    try:
        first = _prepare_main(interview)
    except Exception:
        logger.exception("failed to prepare first question")
        raise InterviewError("We couldn't prepare the interview. Please try again.", 500) from None
    _transition(db, interview, State.PREPARING.value)
    interview.started_at = _now()
    profile = _profile(interview)
    for line in phrasing.greeting(cfg.personality, cfg.target_role, profile.name, cfg.num_questions, cfg.mode):
        _event(db, interview, type_="message", role="interviewer", text=line, meta={"phase": "INTRO"})
    try:
        _ask_main(db, interview, "", first)
    except Exception:
        logger.exception("failed to prepare first question")
        db.rollback()
        raise InterviewError("We couldn't prepare the interview. Please try again.", 500) from None
    db.commit()
    return interview


def _current_question(interview: Interview) -> InterviewQuestion | None:
    if not interview.current_question_id:
        return None
    return next((q for q in interview.questions if q.id == interview.current_question_id), None)


def _follow_up_depth(interview: Interview, question: InterviewQuestion) -> int:
    depth = 0
    by_id = {q.id: q for q in interview.questions}
    node = question
    while node.is_follow_up and node.parent_id in by_id:
        depth += 1
        node = by_id[node.parent_id]
    return depth


def _store_evaluation(db: Session, interview: Interview, answer: Answer, result: EvaluationResult) -> None:
    answer.evaluation = Evaluation(
        interview_id=interview.id,
        dimensions=result.dimensions,
        score=result.score,
        classification=result.classification,
        strengths=result.strengths,
        weaknesses=result.weaknesses,
        missing_points=result.missing_points,
        covered_concepts=result.covered_concepts,
        feedback=result.feedback,
        improvement=result.improvement,
        claim_confidence=result.claim_confidence,
        evaluator=result.evaluator,
    )
    if result.evaluator == "llm" and not interview.llm_used:
        interview.llm_used = True
        interview.llm_model = get_provider().model


def _adapt(interview: Interview, classification: str) -> None:
    rt = interview.runtime or {}
    diff = rt.get("difficulty", "Medium")
    idx = DIFFICULTIES.index(diff) if diff in DIFFICULTIES else 1
    streak = int(rt.get("weak_streak", 0))
    if classification == "Excellent":
        idx = min(len(DIFFICULTIES) - 1, idx + 1)
        streak = 0
    elif classification in ("Weak", "Incomplete", "Off-topic", "Incorrect"):
        streak += 1
        if streak >= 2:
            idx = max(0, idx - 1)
            streak = 0
    else:
        streak = 0
    _set_runtime(interview, difficulty=DIFFICULTIES[idx], weak_streak=streak)


def submit_answer(db: Session, interview: Interview, req: AnswerRequest) -> Interview:
    if interview.state not in {s.value for s in QUESTION_STATES}:
        raise InterviewError("This interview is not currently accepting answers.", 409)
    question = _current_question(interview)
    if question is None or req.question_id != question.id:
        answered = next((q for q in interview.questions if q.id == req.question_id and q.answer is not None), None)
        if answered is not None:
            return interview  # duplicate submit (e.g. retry after a network error): no-op
        raise InterviewError("That question is no longer active. Refresh to continue the interview.", 409)
    text = (req.answer or "").strip()
    if not text:
        raise InterviewError("Please give an answer before submitting, or skip the question.", 422)
    text = text[: get_settings().max_answer_chars]
    cfg = InterviewConfig.model_validate(interview.config)

    # 1) Slow LLM work first, nothing written yet (see interview_lock).
    result = evaluate_answer(
        question=question.text,
        category=question.category,
        expected_concepts=question.expected_concepts,
        rubric=question.rubric,
        answer=text,
        claim=question.claim,
        role=cfg.target_role,
        level=cfg.experience_level,
    )
    _adapt(interview, result.classification)
    history = list(interview.runtime.get("history", []))
    history.append(f"Q: {question.text[:160]} | A: {text[:240]}")
    _set_runtime(interview, history=history[-6:])

    seq_main = sum(1 for q in interview.questions if not q.is_follow_up)
    depth = _follow_up_depth(interview, question)
    fu = None
    if should_follow_up(
        result,
        category=question.category,
        is_follow_up=question.is_follow_up,
        depth=depth,
        used=interview.follow_ups_used,
        budget=max_follow_ups(cfg.num_questions),
        seq=seq_main,
        answer=text,
    ):
        hashes, texts = _asked(interview)
        fu = build_follow_up(
            result,
            ctx=_context(interview),
            question=question.text,
            answer=text,
            probe=interview.runtime.get("probe", ""),
            claim=question.claim,
            claim_kind=interview.runtime.get("claim_kind"),
            category=question.category,
            asked_hashes=hashes,
            asked_texts=texts,
        )
    following = _prepare_main(interview) if fu is None else None

    # 2) Write everything in one short transaction.
    answer = Answer(
        interview_id=interview.id, text=text, input_mode=req.input_mode, duration_seconds=req.duration_seconds
    )
    question.answer = answer
    db.flush()
    _event(
        db,
        interview,
        type_="message",
        role="candidate",
        text=text,
        question_id=question.id,
        meta={"input_mode": req.input_mode},
    )
    _store_evaluation(db, interview, answer, result)
    if fu is not None:
        _ask_follow_up(db, interview, question, fu, result.classification, cfg)
    else:
        tone = "positive" if result.classification in ("Excellent", "Strong") else "neutral"
        ack = phrasing.acknowledgement(cfg.personality, tone, seq_main)
        _ask_main(db, interview, ack, following)
    db.commit()
    return interview


def _ask_follow_up(
    db: Session, interview: Interview, parent: InterviewQuestion, fu, classification: str, cfg: InterviewConfig
) -> None:
    challenge = classification in ("Vague", "Suspicious", "Incorrect", "Weak", "Incomplete")
    phase = State.CHALLENGE.value if challenge else parent.phase
    question = InterviewQuestion(
        seq=_next_question_seq(interview),
        phase=phase,
        text=fu.question,
        category=fu.category,
        difficulty=interview.runtime.get("difficulty", parent.difficulty),
        skill=parent.skill,
        source="previous_answer",
        expected_concepts=fu.expected_concepts,
        rubric=["Responds directly to the follow-up", "Adds concrete detail beyond the first answer"],
        ideal_answer=parent.ideal_answer,
        claim=fu.claim or parent.claim,
        is_follow_up=True,
        parent_id=parent.id,
        generated_by=fu.generated_by,
    )
    interview.questions.append(question)
    db.flush()
    _transition(db, interview, phase)
    ack = fu.acknowledgement or phrasing.acknowledgement(
        cfg.personality, follow_up_tone(classification), interview.follow_ups_used
    )
    _event(
        db,
        interview,
        type_="message",
        role="interviewer",
        text=f"{ack} {fu.question}".strip(),
        question_id=question.id,
        meta={"phase": phase, "category": fu.category, "follow_up": True},
    )
    interview.current_question_id = question.id
    interview.asked_hashes = [*interview.asked_hashes, question_hash(fu.question)]
    interview.follow_ups_used += 1


def skip_question(db: Session, interview: Interview, question_id: str) -> Interview:
    if interview.state not in {s.value for s in QUESTION_STATES}:
        raise InterviewError("This interview is not currently accepting answers.", 409)
    question = _current_question(interview)
    if question is None or question.id != question_id:
        raise InterviewError("That question is no longer active. Refresh to continue the interview.", 409)
    result = evaluate_answer(
        question=question.text,
        category=question.category,
        expected_concepts=question.expected_concepts,
        rubric=question.rubric,
        answer="",
        claim=question.claim,
        role="",
        level="",
    )
    result.weaknesses = ["Question was skipped."]
    result.feedback = "You skipped this question."
    if question.claim and question.category == "claim_verification":
        result.claim_confidence = "Low"
    _adapt(interview, "Incomplete")
    following = _prepare_main(interview)  # may call the LLM: before any write

    answer = Answer(interview_id=interview.id, text="", input_mode="text", skipped=True)
    question.answer = answer
    db.flush()
    _event(
        db,
        interview,
        type_="message",
        role="candidate",
        text="(Skipped this question)",
        question_id=question.id,
        meta={"skipped": True},
    )
    _store_evaluation(db, interview, answer, result)
    _ask_main(db, interview, "No problem, let's move on.", following)
    db.commit()
    return interview


def finish_interview(db: Session, interview: Interview) -> Interview:
    from app.interview.report import build_report  # local import: report depends on engine helpers

    if interview.state == State.COMPLETED.value:
        return interview
    if interview.state == State.CREATED.value:
        raise InterviewError("This interview hasn't started yet.", 409)
    if interview.state in {s.value for s in QUESTION_STATES} | {State.PREPARING.value}:
        if interview.state == State.PREPARING.value:
            raise InterviewError("This interview is still being prepared.", 409)
        _close(db, interview, "Let's stop here for today.")
    _transition(db, interview, State.EVALUATING.value)
    db.commit()
    try:
        build_report(db, interview)
        interview.finished_at = _now()
        started = _aware(interview.started_at) or _aware(interview.created_at)
        interview.duration_seconds = int((interview.finished_at - started).total_seconds()) if started else None
        _transition(db, interview, State.COMPLETED.value)
        interview.error = None
        db.commit()
    except Exception:
        logger.exception("report generation failed")
        db.rollback()
        interview = db.get(Interview, interview.id)
        assert interview is not None
        interview.error = "We couldn't generate the report. Please retry."
        if interview.state != State.FAILED.value:
            _transition(db, interview, State.FAILED.value)
        db.commit()
        raise InterviewError("We couldn't generate the report. Please retry.", 500) from None
    return interview


# ---------------------------------------------------------------- views


def interview_view(interview: Interview) -> InterviewOut:
    cfg = InterviewConfig.model_validate(interview.config)
    persona = phrasing.persona(cfg.personality)
    messages = [
        MessageOut(
            seq=e.seq,
            role=e.role or "system",
            text=e.text,
            question_id=e.question_id,
            created_at=_aware(e.created_at),
            kind="follow_up" if e.meta.get("follow_up") else "message",
        )
        for e in interview.events
        if e.type == "message"
    ]
    current = _current_question(interview)
    main_questions = [q for q in interview.questions if not q.is_follow_up]
    answered_main = sum(1 for q in main_questions if q.answer is not None)
    current_out = None
    if current is not None and current.answer is None:
        current_out = CurrentQuestionOut(
            id=current.id,
            text=current.text,
            category=current.category,
            phase=current.phase,
            is_follow_up=current.is_follow_up,
            number=len(main_questions),
        )
    total = len(interview.plan) or cfg.num_questions
    done = interview.state in (State.CLOSING.value, State.EVALUATING.value, State.COMPLETED.value)
    profile = _profile(interview)
    return InterviewOut(
        id=interview.id,
        state=interview.state,
        phase=interview.runtime.get("phase"),
        config=cfg,
        resume_id=interview.resume_id,
        jd_id=interview.jd_id,
        candidate_name=profile.name,
        created_at=_aware(interview.created_at),
        started_at=_aware(interview.started_at),
        finished_at=_aware(interview.finished_at),
        messages=messages,
        current_question=current_out,
        progress=ProgressOut(
            answered=answered_main,
            total=total,
            follow_ups=interview.follow_ups_used,
            percent=100.0 if done else round(100 * answered_main / max(1, total), 1),
        ),
        interviewer=InterviewerOut(name=persona["name"], title=persona["title"], personality=cfg.personality),
        ai_mode="llm" if (interview.llm_used or get_provider().is_available()) else "offline",
        error=interview.error,
    )
