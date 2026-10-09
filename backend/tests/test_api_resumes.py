"""API: health, config, settings, resume upload and analysis, job descriptions."""

from __future__ import annotations

from pathlib import Path

import pytest
from helpers import jd_text, upload, upload_sample

from app.config import get_settings


def test_health(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["database"] == "ok" and data["resume_parser"] == "ok"
    assert data["llm"] == "disabled"
    assert data["test_mode"] is True
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert resp.headers["X-Request-ID"]


def test_config(client):
    data = client.get("/api/config").json()
    assert data["test_mode"] is True
    assert data["max_resume_size_mb"] == 10
    assert data["max_answer_chars"] == 6000
    assert "Software Engineer" in data["roles"]
    assert data["default_questions"] == 10


def test_settings_get(client):
    data = client.get("/api/settings").json()
    assert data["test_mode"] is True
    assert data["database_url"] == "sqlite (local file)"
    for group, weights in data["weights"].items():
        assert sum(weights.values()) == pytest.approx(1.0), group
    assert data["llm_status"]["available"] is False


@pytest.mark.parametrize(
    "body",
    [
        {"ollama_base_url": "not a url"},
        {"ollama_base_url": "ftp://localhost:11434"},
        {"ollama_base_url": "http://localhost:11434/api; rm -rf /"},
        {"ollama_base_url": "http://user@evil.com"},
        {"ollama_model": "llama3; drop table"},
        {"ollama_model": "x" * 101},
    ],
)
def test_settings_put_validation(client, body):
    resp = client.put("/api/settings", json=body)
    assert resp.status_code == 422
    assert resp.json()["detail"]


def test_settings_put_persists(client):
    resp = client.put(
        "/api/settings", json={"ollama_model": "llama3.2:3b", "ollama_base_url": "http://127.0.0.1:11500"}
    )
    assert resp.status_code == 200
    from app.db import SessionLocal
    from app.models import SettingRow

    with SessionLocal() as db:
        saved = {r.key: r.value for r in db.query(SettingRow).all()}
    assert saved == {"ollama_model": "llama3.2:3b", "ollama_base_url": "http://127.0.0.1:11500"}
    # test mode keeps the offline engine regardless of the saved model
    assert client.get("/api/health").json()["llm"] == "disabled"


@pytest.mark.parametrize("name", ["sample_resume.pdf", "sample_resume.docx", "sample_resume.txt"])
def test_upload_resume(client, name):
    resp = upload(client, name)
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["file_type"] == name.rsplit(".", 1)[1]
    assert data["filename"] == name
    assert data["profile"]["name"] == "Aarav Sharma"
    assert len(data["profile"]["projects"]) == 3
    assert data["word_count"] > 200
    assert data["llm_enriched"] is False
    listed = client.get("/api/resumes").json()
    assert [r["id"] for r in listed] == [data["id"]]
    assert listed[0]["candidate_name"] == "Aarav Sharma"
    assert 0 <= listed[0]["ats_score"] <= 100
    stored = list(Path(get_settings().upload_dir).iterdir())
    assert [p.name for p in stored] == [f"{data['id']}.{data['file_type']}"]


def test_duplicate_upload_returns_cached_resume(client):
    first = upload_sample(client)
    second = upload_sample(client)
    assert second["id"] == first["id"]
    assert len(client.get("/api/resumes").json()) == 1
    assert len(list(Path(get_settings().upload_dir).iterdir())) == 1


def test_upload_filename_is_sanitised(client, sample_text):
    resp = upload(client, data=sample_text.encode(), filename="../../etc/evil<name>.txt")
    assert resp.status_code == 201
    assert resp.json()["filename"] == "evil_name_.txt"
    upload_dir = Path(get_settings().upload_dir).resolve()
    assert all(p.parent == upload_dir for p in upload_dir.rglob("*"))


@pytest.mark.parametrize(
    "name, status, fragment",
    [
        ("scanned_resume.pdf", 422, "scanned/image-based"),
        ("corrupt_resume.pdf", 422, "corrupted"),
        ("empty_resume.txt", 422, "empty"),
    ],
)
def test_upload_invalid_files(client, name, status, fragment):
    resp = upload(client, name)
    assert resp.status_code == status
    body = resp.json()
    assert fragment in body["detail"]
    assert body["code"] == "resume_parse_error"
    assert client.get("/api/resumes").json() == []


def test_upload_unsupported_type_415(client):
    resp = upload(client, data=b"MZ\x90\x00binary", filename="resume.exe")
    assert resp.status_code == 415
    assert "Unsupported file type" in resp.json()["detail"]


def test_upload_oversize_413(client, monkeypatch, sample_text):
    monkeypatch.setenv("MAX_RESUME_SIZE_MB", "0.001")  # ~1 KB
    get_settings.cache_clear()
    resp = upload(client, data=sample_text.encode(), filename="big.txt")
    assert resp.status_code == 413
    assert "too large" in resp.json()["detail"]


def test_upload_requires_file(client):
    resp = client.post("/api/resumes/upload")
    assert resp.status_code == 422
    assert resp.json()["code"] == "validation_error"


def test_get_unknown_resume_404(client):
    resp = client.get("/api/resumes/doesnotexist")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Resume not found."


def test_analyze_without_jd(client):
    resume = upload_sample(client)
    resp = client.post(f"/api/resumes/{resume['id']}/analyze", json={})
    assert resp.status_code == 200
    data = resp.json()
    assert data["jd_match"] is None and data["jd_analysis"] is None and data["jd_id"] is None
    assert 0 <= data["ats"]["overall"] <= 100
    assert data["ats"]["keyword_source"] == "role_template"
    again = client.post(f"/api/resumes/{resume['id']}/analyze", json={}).json()
    assert again["ats"] == data["ats"]


def test_analyze_with_jd(client):
    resume = upload_sample(client)
    resp = client.post(
        f"/api/resumes/{resume['id']}/analyze",
        json={"job_description": jd_text("backend_developer"), "target_role": "Backend Developer"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["jd_id"]
    assert data["jd_match"] is not None
    assert 0 <= data["jd_match"]["score"] <= 100
    assert data["jd_analysis"]["title"] == "Backend Developer"
    assert data["ats"]["keyword_source"] == "job_description"
    # reuse by jd_id
    by_id = client.post(
        f"/api/resumes/{resume['id']}/analyze", json={"jd_id": data["jd_id"], "target_role": "Backend Developer"}
    )
    assert by_id.json()["jd_match"] == data["jd_match"]


def test_analyze_with_invalid_jd(client):
    resume = upload_sample(client)
    resp = client.post(f"/api/resumes/{resume['id']}/analyze", json={"job_description": "Python dev wanted"})
    assert resp.status_code == 422
    assert resp.json()["code"] == "invalid_job_description"
    assert client.post(f"/api/resumes/{resume['id']}/analyze", json={"jd_id": "nope"}).status_code == 404


def test_jd_samples(client):
    data = client.get("/api/job-descriptions/samples").json()
    assert len(data) == 4
    assert {d["id"] for d in data} == {
        "backend_developer",
        "data_analyst",
        "frontend_developer",
        "junior_software_engineer",
    }
    assert all(d["title"] and d["text"] for d in data)


def test_jd_analyze_endpoint(client):
    resp = client.post("/api/job-descriptions/analyze", json={"text": jd_text("frontend_developer")})
    assert resp.status_code == 200
    data = resp.json()
    assert "React" in data["analysis"]["required_skills"]
    same = client.post("/api/job-descriptions/analyze", json={"text": jd_text("frontend_developer")}).json()
    assert same["id"] == data["id"]
    assert client.post("/api/job-descriptions/analyze", json={"text": "too short"}).status_code == 422
    assert client.post("/api/job-descriptions/analyze", json={"text": "x" * 20001}).status_code == 422
