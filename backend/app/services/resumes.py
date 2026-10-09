"""Resume upload pipeline: validate -> extract -> parse -> cache -> (optional) LLM enrichment."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.llm import get_provider
from app.ai.prompts import resume_analysis
from app.config import get_settings
from app.data.skills import canonical, find_skills, skill_category
from app.db import SessionLocal
from app.models import CandidateProfileRow, Resume
from app.schemas import CandidateProfile, ResumeOut
from app.services.ats import compute_ats
from app.services.extract import extract_text, file_extension, sanitize_filename
from app.services.profile import build_profile

logger = logging.getLogger(__name__)


class ProjectHighlight(BaseModel):
    name: str = Field(default="", max_length=120)
    problem: str = Field(default="", max_length=300)
    role: str = Field(default="", max_length=200)


class LLMResumeEnrichment(BaseModel):
    name: str = Field(default="", max_length=80)
    location: str = Field(default="", max_length=80)
    summary: str = Field(default="", max_length=600)
    skills: list[str] = Field(default_factory=list, max_length=40)
    project_highlights: list[ProjectHighlight] = Field(default_factory=list, max_length=6)


def resume_out(resume: Resume) -> ResumeOut:
    profile = CandidateProfile.model_validate(resume.profile.data if resume.profile else {})
    return ResumeOut(
        id=resume.id,
        filename=resume.filename,
        file_type=resume.file_type,
        size_bytes=resume.size_bytes,
        page_count=resume.page_count,
        created_at=resume.created_at,
        warnings=resume.parse_warnings or [],
        profile=profile,
        llm_enriched=bool(resume.profile and resume.profile.llm_enriched),
        word_count=len(resume.text.split()),
    )


def ingest_resume(db: Session, filename: str, data: bytes) -> tuple[Resume, bool]:
    """Parse and store a resume. Returns (resume, created). Identical text reuses the cached parse."""
    settings = get_settings()
    doc = extract_text(filename, data, settings.max_resume_bytes)
    text_hash = hashlib.sha256(doc.text.encode()).hexdigest()
    existing = db.scalar(select(Resume).where(Resume.text_hash == text_hash).order_by(Resume.created_at.desc()))
    if existing is not None and existing.profile is not None:
        return existing, False

    safe_name = sanitize_filename(filename)
    resume = Resume(
        filename=safe_name,
        file_type=doc.file_type,
        size_bytes=len(data),
        text=doc.text,
        text_hash=text_hash,
        page_count=doc.page_count,
        parse_warnings=doc.warnings,
    )
    db.add(resume)
    db.flush()

    upload_dir = Path(settings.upload_dir).resolve()
    upload_dir.mkdir(parents=True, exist_ok=True)
    # Stored name is derived only from our own UUID, never from the client filename.
    target = (upload_dir / f"{resume.id}.{file_extension(safe_name)}").resolve()
    if target.parent != upload_dir:
        raise RuntimeError("unsafe upload path")
    target.write_bytes(data)
    resume.stored_path = str(target)

    profile = build_profile(doc.text)
    ats = compute_ats(doc.text, profile, parse_warnings=doc.warnings, page_count=doc.page_count)
    db.add(CandidateProfileRow(resume_id=resume.id, data=profile.model_dump(), ats_general=ats.model_dump()))
    db.commit()
    db.refresh(resume)
    return resume, True


def merge_enrichment(profile: CandidateProfile, resume_text: str, enr: LLMResumeEnrichment) -> CandidateProfile:
    """Merge LLM output conservatively: only fill gaps, and only with facts present in the resume text."""
    low = resume_text.lower()
    if not profile.name and enr.name and enr.name.lower() in low:
        profile.name = enr.name.strip()
    if not profile.location and enr.location and enr.location.lower() in low:
        profile.location = enr.location.strip()
    present = find_skills(resume_text, include_weak=True)
    buckets = {
        "programming_languages": profile.programming_languages,
        "frameworks": profile.frameworks,
        "databases": profile.databases,
        "tools": profile.tools,
        "concepts": profile.concepts,
    }
    for raw in enr.skills:
        name = canonical(raw)
        if name and name in present and name not in profile.skills and skill_category(name) != "soft":
            profile.skills.append(name)
            profile.skill_mentions.setdefault(name, present[name])
            bucket = buckets.get(skill_category(name))
            if bucket is not None and name not in bucket:
                bucket.append(name)
    return profile


def enrich_with_llm(resume_id: str) -> None:
    """Background task: optional LLM enrichment of a parsed resume. Silent no-op without an LLM."""
    provider = get_provider()
    if not provider.is_available():
        return
    db = SessionLocal()
    try:
        resume = db.get(Resume, resume_id)
        if resume is None or resume.profile is None or resume.profile.llm_enriched:
            return
        system, user = resume_analysis.build(resume.text)
        result = provider.complete_structured(system, user, LLMResumeEnrichment, temperature=0.0)
        if result is None:
            return
        profile = merge_enrichment(CandidateProfile.model_validate(resume.profile.data), resume.text, result)
        data = profile.model_dump()
        if result.summary:
            data["ai_summary"] = result.summary
        resume.profile.data = data
        resume.profile.llm_enriched = True
        db.commit()
        logger.info("resume enriched by llm")
    except Exception as exc:
        logger.warning("resume enrichment failed: %s", type(exc).__name__)
        db.rollback()
    finally:
        db.close()


def delete_resume_files(resume: Resume) -> None:
    if resume.stored_path:
        path = Path(resume.stored_path).resolve()
        if path.parent == Path(get_settings().upload_dir).resolve() and path.exists():
            path.unlink()
