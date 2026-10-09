"""REST API. All routes are mounted under /api."""

from __future__ import annotations

import hashlib
import json
import logging
import re
import shutil
from pathlib import Path
from statistics import mean

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse, PlainTextResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select, text
from sqlalchemy.orm import Session

from app.ai.llm import get_provider, set_runtime_options
from app.config import get_settings
from app.data.lexicon import ROLE_TEMPLATES
from app.db import get_db
from app.interview import engine
from app.interview.state import ACTIVE_STATES
from app.models import (
    Answer,
    CandidateProfileRow,
    Evaluation,
    Interview,
    InterviewEvent,
    InterviewQuestion,
    JobDescription,
    Report,
    Resume,
    ResumeAnalysis,
    SettingRow,
    SkillScore,
)
from app.schemas import (
    AnalysisOut,
    AnalyzeRequest,
    AnswerRequest,
    ATSReport,
    CandidateProfile,
    CreateInterviewRequest,
    HistoryItem,
    InterviewOut,
    JDAnalysis,
    JDAnalyzeRequest,
    JDMatch,
    JDOut,
    ResumeOut,
    ResumeSummary,
    SkipRequest,
)
from app.services.ats import compute_ats
from app.services.jd import analyze_job_description, match_resume_to_jd
from app.services.pdf import render_report_pdf
from app.services.resumes import delete_resume_files, enrich_with_llm, ingest_resume, resume_out

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api")

SAMPLES_DIR = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "job_descriptions"


def _get_resume(db: Session, resume_id: str) -> Resume:
    resume = db.get(Resume, resume_id)
    if resume is None:
        raise HTTPException(404, "Resume not found.")
    return resume


def _get_interview(db: Session, interview_id: str) -> Interview:
    interview = db.get(Interview, interview_id)
    if interview is None:
        raise HTTPException(404, "Interview not found.")
    return interview


def _get_or_create_jd(db: Session, text_: str, title: str = "") -> JobDescription:
    clean = text_.strip()
    h = hashlib.sha256(clean.encode()).hexdigest()
    existing = db.scalar(select(JobDescription).where(JobDescription.text_hash == h))
    if existing is not None:
        return existing
    analysis = analyze_job_description(clean, title)
    jd = JobDescription(title=analysis.title or title, text=clean, text_hash=h, analysis=analysis.model_dump())
    db.add(jd)
    db.flush()
    return jd


# ---------------------------------------------------------------- health / config


@router.get("/health")
def health(db: Session = Depends(get_db)) -> dict:
    settings = get_settings()
    try:
        db.execute(text("SELECT 1"))
        database = "ok"
    except Exception as exc:
        logger.error("database health check failed: %s", type(exc).__name__)
        database = "error"
    try:
        import docx  # noqa: F401
        import pymupdf  # noqa: F401

        parser = "ok"
    except Exception:
        parser = "error"
    st = get_provider().status(refresh=True)
    llm = "ok" if st.available else ("disabled" if st.server == "disabled" else "unavailable")
    return {
        "status": "ok" if database == "ok" and parser == "ok" else "degraded",
        "application": "ok",
        "database": database,
        "resume_parser": parser,
        "llm": llm,
        "llm_provider": st.provider,
        "ollama_server": st.server,
        "ollama_model": "available" if st.model_available else ("not_installed" if st.server == "ok" else "unknown"),
        "model": st.model,
        "llm_detail": st.detail,
        "installed_models": st.installed_models,
        "test_mode": settings.test_mode,
        "voice_enabled": settings.voice_enabled,
        "version": "1.0.0",
    }


@router.get("/config")
def public_config() -> dict:
    s = get_settings()
    return {
        "voice_enabled": s.voice_enabled,
        "test_mode": s.test_mode,
        "max_resume_size_mb": s.max_resume_size_mb,
        "default_questions": s.interview_default_questions,
        "roles": list(ROLE_TEMPLATES.keys()),
        "max_answer_chars": s.max_answer_chars,
    }


class SettingsUpdate(BaseModel):
    ollama_model: str | None = Field(default=None, max_length=100)
    ollama_base_url: str | None = Field(default=None, max_length=200)


@router.get("/settings")
def get_app_settings() -> dict:
    s = get_settings()
    provider = get_provider()
    st = provider.status()
    return {
        "llm_provider": s.llm_provider,
        "ollama_model": st.model or s.ollama_model,
        "ollama_base_url": getattr(provider, "base_url", s.ollama_base_url),
        "llm_status": st.__dict__,
        "test_mode": s.test_mode,
        "voice_enabled": s.voice_enabled,
        "max_resume_size_mb": s.max_resume_size_mb,
        "weights": {g: s.weights(g) for g in ("ats", "answer", "behavioral_answer", "interview", "readiness")},
        "database_url": "sqlite (local file)" if s.database_url.startswith("sqlite") else "custom",
    }


@router.put("/settings")
def update_settings(body: SettingsUpdate, db: Session = Depends(get_db)) -> dict:
    if body.ollama_model is not None and not re.fullmatch(r"[A-Za-z0-9._:/-]{1,100}", body.ollama_model):
        raise HTTPException(422, "Model names may only contain letters, numbers and . _ : / -")
    if body.ollama_base_url is not None and not re.fullmatch(
        r"https?://[A-Za-z0-9.\-]+(:\d{1,5})?/?", body.ollama_base_url
    ):
        raise HTTPException(422, "The Ollama URL must look like http://localhost:11434")
    for key, value in (("ollama_model", body.ollama_model), ("ollama_base_url", body.ollama_base_url)):
        if value:
            row = db.get(SettingRow, key)
            if row is None:
                db.add(SettingRow(key=key, value=value))
            else:
                row.value = value
    db.commit()
    set_runtime_options(model=body.ollama_model, base_url=body.ollama_base_url)
    get_provider().status(refresh=True)
    return get_app_settings()


# ---------------------------------------------------------------- resumes


@router.post("/resumes/upload", response_model=ResumeOut, status_code=201)
async def upload_resume(background: BackgroundTasks, file: UploadFile = File(...), db: Session = Depends(get_db)):
    settings = get_settings()
    limit = settings.max_resume_bytes
    chunks: list[bytes] = []
    size = 0
    while True:
        chunk = await file.read(1024 * 256)
        if not chunk:
            break
        size += len(chunk)
        if size > limit:
            raise HTTPException(413, f"The file is too large. The maximum size is {settings.max_resume_size_mb:g} MB.")
        chunks.append(chunk)
    resume, created = ingest_resume(db, file.filename or "resume", b"".join(chunks))
    if created:
        background.add_task(enrich_with_llm, resume.id)
    return resume_out(resume)


@router.get("/resumes", response_model=list[ResumeSummary])
def list_resumes(db: Session = Depends(get_db)):
    out = []
    for r in db.scalars(select(Resume).order_by(Resume.created_at.desc())):
        prof = r.profile
        out.append(
            ResumeSummary(
                id=r.id,
                filename=r.filename,
                file_type=r.file_type,
                size_bytes=r.size_bytes,
                created_at=r.created_at,
                candidate_name=(prof.data.get("name", "") if prof else ""),
                ats_score=(prof.ats_general or {}).get("overall") if prof else None,
            )
        )
    return out


@router.get("/resumes/{resume_id}", response_model=ResumeOut)
def get_resume(resume_id: str, db: Session = Depends(get_db)):
    return resume_out(_get_resume(db, resume_id))


@router.delete("/resumes/{resume_id}", status_code=204)
def delete_resume(resume_id: str, db: Session = Depends(get_db)):
    resume = _get_resume(db, resume_id)
    delete_resume_files(resume)
    db.delete(resume)
    db.commit()
    return Response(status_code=204)


@router.post("/resumes/{resume_id}/analyze", response_model=AnalysisOut)
def analyze_resume(resume_id: str, body: AnalyzeRequest, db: Session = Depends(get_db)):
    resume = _get_resume(db, resume_id)
    if resume.profile is None:
        raise HTTPException(409, "This resume has not been parsed. Please upload it again.")
    profile = CandidateProfile.model_validate(resume.profile.data)
    jd_row = None
    if body.jd_id:
        jd_row = db.get(JobDescription, body.jd_id)
        if jd_row is None:
            raise HTTPException(404, "Job description not found.")
    elif body.job_description and body.job_description.strip():
        jd_row = _get_or_create_jd(db, body.job_description)
    role = body.target_role or "Software Engineer"

    jd_cond = ResumeAnalysis.jd_id == jd_row.id if jd_row else ResumeAnalysis.jd_id.is_(None)
    cached = db.scalar(
        select(ResumeAnalysis).where(ResumeAnalysis.resume_id == resume.id, jd_cond, ResumeAnalysis.target_role == role)
    )
    jd = JDAnalysis.model_validate(jd_row.analysis) if jd_row else None
    if cached is not None:
        ats = ATSReport.model_validate(cached.ats)
        match = JDMatch.model_validate(cached.jd_match) if cached.jd_match else None
    else:
        ats = compute_ats(
            resume.text,
            profile,
            target_role=role,
            jd=jd,
            parse_warnings=resume.parse_warnings,
            page_count=resume.page_count,
        )
        match = match_resume_to_jd(profile, resume.text, jd) if jd else None
        db.add(
            ResumeAnalysis(
                resume_id=resume.id,
                jd_id=jd_row.id if jd_row else None,
                target_role=role,
                ats=ats.model_dump(),
                jd_match=match.model_dump() if match else None,
            )
        )
    db.commit()
    return AnalysisOut(
        resume_id=resume.id, jd_id=jd_row.id if jd_row else None, ats=ats, jd_match=match, jd_analysis=jd
    )


# ---------------------------------------------------------------- job descriptions


@router.post("/job-descriptions/analyze", response_model=JDOut)
def analyze_jd(body: JDAnalyzeRequest, db: Session = Depends(get_db)):
    jd = _get_or_create_jd(db, body.text, body.title)
    db.commit()
    return JDOut(id=jd.id, title=jd.title, analysis=JDAnalysis.model_validate(jd.analysis))


@router.get("/job-descriptions/samples")
def jd_samples() -> list[dict]:
    out = []
    if SAMPLES_DIR.is_dir():
        for p in sorted(SAMPLES_DIR.glob("*.txt")):
            body = p.read_text(encoding="utf-8")
            out.append({"id": p.stem, "title": body.strip().splitlines()[0], "text": body})
    return out


# ---------------------------------------------------------------- interviews


@router.post("/interviews", response_model=InterviewOut, status_code=201)
def create_interview(body: CreateInterviewRequest, db: Session = Depends(get_db)):
    resume = _get_resume(db, body.resume_id)
    jd_row = None
    if body.jd_id:
        jd_row = db.get(JobDescription, body.jd_id)
        if jd_row is None:
            raise HTTPException(404, "Job description not found.")
    elif body.job_description and body.job_description.strip():
        jd_row = _get_or_create_jd(db, body.job_description)
    interview = engine.create_interview(db, resume, body.config, jd_row)
    return engine.interview_view(interview)


@router.get("/interviews/history", response_model=list[HistoryItem])
def interview_history(db: Session = Depends(get_db)):
    items = []
    for i in db.scalars(select(Interview).order_by(Interview.created_at.desc())):
        c = i.config
        items.append(
            HistoryItem(
                id=i.id,
                created_at=i.created_at,
                finished_at=i.finished_at,
                state=i.state,
                target_role=c.get("target_role", ""),
                interview_type=c.get("interview_type", ""),
                difficulty=c.get("difficulty", ""),
                experience_level=c.get("experience_level", ""),
                num_questions=c.get("num_questions", 0),
                interview_score=i.interview_score,
                ats_score=i.ats_score,
                jd_score=i.jd_score,
                readiness_score=i.readiness_score,
                duration_seconds=i.duration_seconds,
                resume_filename=i.resume.filename if i.resume else "",
                has_jd=i.jd_id is not None,
            )
        )
    return items


@router.get("/interviews/active", response_model=list[InterviewOut])
def active_interviews(db: Session = Depends(get_db)):
    states = [s.value for s in ACTIVE_STATES if s.value != "CREATED"]
    rows = db.scalars(select(Interview).where(Interview.state.in_(states)).order_by(Interview.created_at.desc()))
    return [engine.interview_view(i) for i in rows]


@router.get("/interviews/{interview_id}", response_model=InterviewOut)
def get_interview(interview_id: str, db: Session = Depends(get_db)):
    return engine.interview_view(_get_interview(db, interview_id))


@router.post("/interviews/{interview_id}/start", response_model=InterviewOut)
def start_interview(interview_id: str, db: Session = Depends(get_db)):
    with engine.interview_lock(interview_id):
        interview = engine.start_interview(db, _get_interview(db, interview_id))
    return engine.interview_view(interview)


@router.post("/interviews/{interview_id}/answer", response_model=InterviewOut)
def answer_question(interview_id: str, body: AnswerRequest, db: Session = Depends(get_db)):
    with engine.interview_lock(interview_id):
        interview = engine.submit_answer(db, _get_interview(db, interview_id), body)
    return engine.interview_view(interview)


@router.post("/interviews/{interview_id}/next-question", response_model=InterviewOut)
def skip_to_next(interview_id: str, body: SkipRequest, db: Session = Depends(get_db)):
    with engine.interview_lock(interview_id):
        interview = engine.skip_question(db, _get_interview(db, interview_id), body.question_id)
    return engine.interview_view(interview)


@router.post("/interviews/{interview_id}/finish", response_model=InterviewOut)
def finish(interview_id: str, db: Session = Depends(get_db)):
    with engine.interview_lock(interview_id):
        interview = engine.finish_interview(db, _get_interview(db, interview_id))
    return engine.interview_view(interview)


@router.get("/interviews/{interview_id}/report")
def get_report(interview_id: str, db: Session = Depends(get_db)):
    interview = _get_interview(db, interview_id)
    if interview.report is None:
        raise HTTPException(404, "The report isn't ready yet. Finish the interview to generate it.")
    return JSONResponse(interview.report.data)


@router.get("/interviews/{interview_id}/report.pdf")
def get_report_pdf(interview_id: str, db: Session = Depends(get_db)):
    interview = _get_interview(db, interview_id)
    if interview.report is None:
        raise HTTPException(404, "The report isn't ready yet.")
    pdf = render_report_pdf(interview.report.data)
    return Response(
        pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="interviewforge-report-{interview.id[:8]}.pdf"'},
    )


@router.get("/interviews/{interview_id}/transcript")
def get_transcript(interview_id: str, db: Session = Depends(get_db)):
    interview = _get_interview(db, interview_id)
    view = engine.interview_view(interview)
    cfg = view.config
    lines = [
        "InterviewForge transcript",
        f"Role: {cfg.experience_level} {cfg.target_role} | Type: {cfg.interview_type} | Difficulty: {cfg.difficulty}",
        f"Interviewer: {view.interviewer.name} ({view.interviewer.title})",
        f"Date: {view.created_at:%Y-%m-%d %H:%M} UTC",
        "",
    ]
    for m in view.messages:
        who = view.interviewer.name if m.role == "interviewer" else (view.candidate_name or "Candidate")
        lines.append(f"[{m.created_at:%H:%M:%S}] {who}: {m.text}")
        lines.append("")
    return PlainTextResponse(
        "\n".join(lines),
        headers={"Content-Disposition": f'attachment; filename="interviewforge-transcript-{interview.id[:8]}.txt"'},
    )


@router.delete("/interviews/{interview_id}", status_code=204)
def delete_interview(interview_id: str, db: Session = Depends(get_db)):
    db.delete(_get_interview(db, interview_id))
    db.commit()
    return Response(status_code=204)


# ---------------------------------------------------------------- dashboard / data


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db)) -> dict:
    completed = list(
        db.scalars(select(Interview).where(Interview.state == "COMPLETED").order_by(Interview.finished_at))
    )
    latest_resume = db.scalar(select(Resume).order_by(Resume.created_at.desc()))
    scores = [i.interview_score for i in completed if i.interview_score is not None]
    latest = completed[-1] if completed else None
    weak_rows = db.execute(
        select(SkillScore.skill, func.avg(SkillScore.score), func.count(SkillScore.id))
        .group_by(SkillScore.skill)
        .order_by(func.avg(SkillScore.score))
        .limit(6)
    ).all()
    resume_health = None
    if latest_resume is not None and latest_resume.profile is not None and latest_resume.profile.ats_general:
        ats = latest_resume.profile.ats_general
        resume_health = {
            "resume_id": latest_resume.id,
            "filename": latest_resume.filename,
            "ats_score": ats.get("overall"),
            "classification": ats.get("classification"),
            "top_recommendations": ats.get("recommendations", [])[:3],
            "dimensions": [{"label": d["label"], "score": d["score"]} for d in ats.get("dimensions", [])],
        }
    active = db.scalars(
        select(Interview)
        .where(Interview.state.in_([s.value for s in ACTIVE_STATES if s.value != "CREATED"]))
        .order_by(Interview.created_at.desc())
    ).all()
    return {
        "interviews_completed": len(completed),
        "latest_interview_score": latest.interview_score if latest else None,
        "latest_readiness": latest.readiness_score if latest else None,
        "latest_jd_match": latest.jd_score if latest else None,
        "latest_ats": (latest.ats_score if latest else None) or (resume_health or {}).get("ats_score"),
        "best_score": max(scores) if scores else None,
        "average_score": round(mean(scores), 1) if scores else None,
        "improvement": round(scores[-1] - scores[0], 1) if len(scores) >= 2 else None,
        "trend": [
            {
                "id": i.id,
                "date": i.finished_at.isoformat() if i.finished_at else None,
                "interview": i.interview_score,
                "readiness": i.readiness_score,
                "ats": i.ats_score,
                "role": i.config.get("target_role", ""),
            }
            for i in completed[-12:]
        ],
        "weak_skills": [{"skill": s, "score": round(float(a), 1), "count": int(n)} for s, a, n in weak_rows if a < 75],
        "recent": [
            {
                "id": i.id,
                "date": (i.finished_at or i.created_at).isoformat(),
                "role": i.config.get("target_role", ""),
                "type": i.config.get("interview_type", ""),
                "score": i.interview_score,
                "readiness": i.readiness_score,
            }
            for i in reversed(completed[-5:])
        ],
        "active_interviews": [
            {
                "id": i.id,
                "role": i.config.get("target_role", ""),
                "state": i.state,
                "created_at": i.created_at.isoformat(),
            }
            for i in active
        ],
        "resume_health": resume_health,
        "has_resume": latest_resume is not None,
    }


@router.delete("/data", status_code=204)
def delete_all_data(db: Session = Depends(get_db)):
    """Delete every stored resume, job description, interview and report, plus uploaded files."""
    for model in (
        SkillScore,
        Report,
        Evaluation,
        Answer,
        InterviewEvent,
        InterviewQuestion,
        Interview,
        ResumeAnalysis,
        CandidateProfileRow,
        Resume,
        JobDescription,
    ):
        db.execute(delete(model))
    db.commit()
    upload_dir = Path(get_settings().upload_dir).resolve()
    if upload_dir.is_dir():
        for child in upload_dir.iterdir():
            if child.name == ".gitkeep":
                continue
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
    logger.info("all local data deleted")
    return Response(status_code=204)


@router.get("/export")
def export_all(db: Session = Depends(get_db)):
    """Export interview history as JSON (for the user's own backup)."""
    data = [
        {
            "id": i.id,
            "config": i.config,
            "state": i.state,
            "scores": {
                "interview": i.interview_score,
                "ats": i.ats_score,
                "jd": i.jd_score,
                "readiness": i.readiness_score,
            },
            "report": i.report.data if i.report else None,
        }
        for i in db.scalars(select(Interview).order_by(Interview.created_at))
    ]
    return Response(
        json.dumps(data, indent=2, default=str),
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="interviewforge-export.json"'},
    )
