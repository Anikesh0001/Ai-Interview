"""Database operations: cascades and full data deletion."""

from __future__ import annotations

from pathlib import Path

from helpers import completed_interview, create_interview, jd_text, start_interview, upload_sample
from sqlalchemy import func, select

from app.config import get_settings
from app.db import SessionLocal
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
    SkillScore,
)

DATA_MODELS = (
    Resume,
    CandidateProfileRow,
    JobDescription,
    ResumeAnalysis,
    Interview,
    InterviewQuestion,
    Answer,
    Evaluation,
    InterviewEvent,
    Report,
    SkillScore,
)


def _counts() -> dict[str, int]:
    with SessionLocal() as db:
        return {m.__name__: db.scalar(select(func.count()).select_from(m)) for m in DATA_MODELS}


def test_isolated_database_per_test():
    assert all(v == 0 for v in _counts().values())
    assert "test.db" in get_settings().database_url


def test_resume_delete_cascades(client):
    iv = completed_interview(client, num_questions=3)
    resume_id = iv["resume_id"]
    client.post(f"/api/resumes/{resume_id}/analyze", json={})
    before = _counts()
    for name in (
        "Interview",
        "InterviewQuestion",
        "Answer",
        "Evaluation",
        "InterviewEvent",
        "Report",
        "ResumeAnalysis",
    ):
        assert before[name] > 0, name
    with SessionLocal() as db:
        stored = Path(db.get(Resume, resume_id).stored_path)
    assert stored.exists()

    assert client.delete(f"/api/resumes/{resume_id}").status_code == 204
    after = _counts()
    for name in (
        "Resume",
        "CandidateProfileRow",
        "ResumeAnalysis",
        "Interview",
        "InterviewQuestion",
        "Answer",
        "Evaluation",
        "InterviewEvent",
        "Report",
        "SkillScore",
    ):
        assert after[name] == 0, name
    assert not stored.exists()
    assert client.get(f"/api/interviews/{iv['id']}").status_code == 404
    assert client.get(f"/api/resumes/{resume_id}").status_code == 404


def test_interview_delete_cascades_but_keeps_resume(client):
    iv = completed_interview(client, num_questions=3)
    assert client.delete(f"/api/interviews/{iv['id']}").status_code == 204
    after = _counts()
    for name in ("Interview", "InterviewQuestion", "Answer", "Evaluation", "InterviewEvent", "Report", "SkillScore"):
        assert after[name] == 0, name
    assert after["Resume"] == 1 and after["CandidateProfileRow"] == 1


def test_delete_all_data_empties_tables_and_uploads(client):
    completed_interview(client, num_questions=5)  # 5 questions include a technical (skill-scored) one
    resume = upload_sample(client, "sample_resume.pdf")
    client.post(f"/api/resumes/{resume['id']}/analyze", json={"job_description": jd_text("data_analyst")})
    iv = create_interview(client, resume["id"], num_questions=3)
    start_interview(client, iv["id"])
    upload_dir = Path(get_settings().upload_dir)
    (upload_dir / "nested").mkdir()
    (upload_dir / "nested" / "junk.txt").write_text("x")
    (upload_dir / ".gitkeep").write_text("")
    before = _counts()
    assert all(v > 0 for v in before.values()), str(before)

    assert client.delete("/api/data").status_code == 204
    assert all(v == 0 for v in _counts().values()), _counts()
    assert [p.name for p in upload_dir.iterdir()] == [".gitkeep"]
    assert client.get("/api/resumes").json() == []
    assert client.get("/api/interviews/history").json() == []
    dash = client.get("/api/dashboard").json()
    assert dash["interviews_completed"] == 0 and dash["has_resume"] is False
