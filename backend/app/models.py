"""ORM models. Everything is stored in a local SQLite database."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import DateTime as _DateTime
from sqlalchemy.types import TypeDecorator

from app.db import Base


class DateTime(TypeDecorator):
    """Timezone-aware UTC datetimes, even on SQLite (which stores them naive)."""

    impl = _DateTime
    cache_ok = True

    def __init__(self, timezone: bool = True):
        super().__init__(timezone=timezone)

    def process_bind_param(self, value, dialect):
        if value is not None and value.tzinfo is not None:
            value = value.astimezone(UTC).replace(tzinfo=None)
        return value

    def process_result_value(self, value, dialect):
        if value is not None and value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value


def new_id() -> str:
    return uuid.uuid4().hex


def utcnow() -> datetime:
    return datetime.now(UTC)


class Resume(Base):
    __tablename__ = "resumes"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    filename: Mapped[str] = mapped_column(String(255))
    file_type: Mapped[str] = mapped_column(String(8))
    size_bytes: Mapped[int] = mapped_column(Integer)
    stored_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    text: Mapped[str] = mapped_column(Text)
    text_hash: Mapped[str] = mapped_column(String(64), index=True)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    parse_warnings: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    profile: Mapped[CandidateProfileRow | None] = relationship(
        back_populates="resume", cascade="all, delete-orphan", uselist=False
    )
    interviews: Mapped[list[Interview]] = relationship(back_populates="resume", cascade="all, delete-orphan")


class CandidateProfileRow(Base):
    __tablename__ = "candidate_profiles"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    resume_id: Mapped[str] = mapped_column(ForeignKey("resumes.id", ondelete="CASCADE"), unique=True)
    data: Mapped[dict[str, Any]] = mapped_column(JSON)
    ats_general: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    llm_enriched: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    resume: Mapped[Resume] = relationship(back_populates="profile")


class JobDescription(Base):
    __tablename__ = "job_descriptions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    title: Mapped[str] = mapped_column(String(200), default="")
    text: Mapped[str] = mapped_column(Text)
    text_hash: Mapped[str] = mapped_column(String(64), index=True)
    analysis: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ResumeAnalysis(Base):
    """Cached ATS (+ optional JD match) result for a resume/JD pair."""

    __tablename__ = "resume_analyses"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    resume_id: Mapped[str] = mapped_column(ForeignKey("resumes.id", ondelete="CASCADE"), index=True)
    jd_id: Mapped[str | None] = mapped_column(ForeignKey("job_descriptions.id", ondelete="SET NULL"), nullable=True)
    target_role: Mapped[str] = mapped_column(String(100), default="")
    ats: Mapped[dict[str, Any]] = mapped_column(JSON)
    jd_match: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Interview(Base):
    __tablename__ = "interviews"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    resume_id: Mapped[str] = mapped_column(ForeignKey("resumes.id", ondelete="CASCADE"), index=True)
    jd_id: Mapped[str | None] = mapped_column(ForeignKey("job_descriptions.id", ondelete="SET NULL"), nullable=True)
    config: Mapped[dict[str, Any]] = mapped_column(JSON)
    plan: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    state: Mapped[str] = mapped_column(String(20), default="CREATED", index=True)
    plan_index: Mapped[int] = mapped_column(Integer, default=0)
    follow_ups_used: Mapped[int] = mapped_column(Integer, default=0)
    asked_hashes: Mapped[list[str]] = mapped_column(JSON, default=list)
    # adaptive runtime state: current difficulty, weak streak, answer history summary, seed
    runtime: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    current_question_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    llm_used: Mapped[bool] = mapped_column(Boolean, default=False)
    llm_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    ats_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    jd_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    interview_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    readiness_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)

    resume: Mapped[Resume] = relationship(back_populates="interviews")
    job_description: Mapped[JobDescription | None] = relationship()
    questions: Mapped[list[InterviewQuestion]] = relationship(
        back_populates="interview",
        cascade="all, delete-orphan",
        order_by="InterviewQuestion.seq",
    )
    events: Mapped[list[InterviewEvent]] = relationship(
        back_populates="interview",
        cascade="all, delete-orphan",
        order_by="InterviewEvent.seq",
    )
    report: Mapped[Report | None] = relationship(
        back_populates="interview", cascade="all, delete-orphan", uselist=False
    )
    skill_scores: Mapped[list[SkillScore]] = relationship(back_populates="interview", cascade="all, delete-orphan")


class InterviewQuestion(Base):
    __tablename__ = "interview_questions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    interview_id: Mapped[str] = mapped_column(ForeignKey("interviews.id", ondelete="CASCADE"), index=True)
    seq: Mapped[int] = mapped_column(Integer)
    phase: Mapped[str] = mapped_column(String(20))
    text: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(30))
    difficulty: Mapped[str] = mapped_column(String(12))
    skill: Mapped[str] = mapped_column(String(80), default="")
    source: Mapped[str] = mapped_column(String(30))
    expected_concepts: Mapped[list[str]] = mapped_column(JSON, default=list)
    rubric: Mapped[list[str]] = mapped_column(JSON, default=list)
    ideal_answer: Mapped[str] = mapped_column(Text, default="")
    claim: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_follow_up: Mapped[bool] = mapped_column(Boolean, default=False)
    parent_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    generated_by: Mapped[str] = mapped_column(String(12), default="bank")
    scored: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    interview: Mapped[Interview] = relationship(back_populates="questions")
    answer: Mapped[Answer | None] = relationship(back_populates="question", cascade="all, delete-orphan", uselist=False)


class Answer(Base):
    __tablename__ = "answers"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    question_id: Mapped[str] = mapped_column(ForeignKey("interview_questions.id", ondelete="CASCADE"), unique=True)
    interview_id: Mapped[str] = mapped_column(ForeignKey("interviews.id", ondelete="CASCADE"), index=True)
    text: Mapped[str] = mapped_column(Text)
    input_mode: Mapped[str] = mapped_column(String(10), default="text")
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    skipped: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    question: Mapped[InterviewQuestion] = relationship(back_populates="answer")
    evaluation: Mapped[Evaluation | None] = relationship(
        back_populates="answer", cascade="all, delete-orphan", uselist=False
    )


class Evaluation(Base):
    __tablename__ = "evaluations"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    answer_id: Mapped[str] = mapped_column(ForeignKey("answers.id", ondelete="CASCADE"), unique=True)
    interview_id: Mapped[str] = mapped_column(ForeignKey("interviews.id", ondelete="CASCADE"), index=True)
    dimensions: Mapped[dict[str, int]] = mapped_column(JSON)
    score: Mapped[float] = mapped_column(Float)
    classification: Mapped[str] = mapped_column(String(20))
    strengths: Mapped[list[str]] = mapped_column(JSON, default=list)
    weaknesses: Mapped[list[str]] = mapped_column(JSON, default=list)
    missing_points: Mapped[list[str]] = mapped_column(JSON, default=list)
    covered_concepts: Mapped[list[str]] = mapped_column(JSON, default=list)
    feedback: Mapped[str] = mapped_column(Text, default="")
    improvement: Mapped[str] = mapped_column(Text, default="")
    claim_confidence: Mapped[str | None] = mapped_column(String(10), nullable=True)
    evaluator: Mapped[str] = mapped_column(String(12), default="heuristic")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    answer: Mapped[Answer] = relationship(back_populates="evaluation")


class InterviewEvent(Base):
    """Append-only interview timeline: transcript messages and state transitions."""

    __tablename__ = "interview_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    interview_id: Mapped[str] = mapped_column(ForeignKey("interviews.id", ondelete="CASCADE"), index=True)
    seq: Mapped[int] = mapped_column(Integer)
    type: Mapped[str] = mapped_column(String(20))  # message | state
    role: Mapped[str | None] = mapped_column(String(12), nullable=True)  # interviewer | candidate
    text: Mapped[str] = mapped_column(Text, default="")
    question_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    meta: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    interview: Mapped[Interview] = relationship(back_populates="events")


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    interview_id: Mapped[str] = mapped_column(ForeignKey("interviews.id", ondelete="CASCADE"), unique=True)
    data: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    interview: Mapped[Interview] = relationship(back_populates="report")


class SkillScore(Base):
    __tablename__ = "skill_scores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    interview_id: Mapped[str] = mapped_column(ForeignKey("interviews.id", ondelete="CASCADE"), index=True)
    skill: Mapped[str] = mapped_column(String(80), index=True)
    score: Mapped[float] = mapped_column(Float)
    question_count: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    interview: Mapped[Interview] = relationship(back_populates="skill_scores")


class SettingRow(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[Any] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
