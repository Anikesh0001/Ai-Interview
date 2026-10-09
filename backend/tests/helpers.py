"""Test helpers shared across test modules (fixture paths, upload and interview shortcuts)."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "tests" / "fixtures"
JD_DIR = FIXTURES_DIR / "job_descriptions"
MIME = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "txt": "text/plain",
}


def upload(client: TestClient, name: str = "sample_resume.txt", data: bytes | None = None, filename: str | None = None):
    """Upload a fixture (or raw bytes) and return the response."""
    if data is None:
        data = (FIXTURES_DIR / name).read_bytes()
    filename = filename or name
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return client.post(
        "/api/resumes/upload", files={"file": (filename, data, MIME.get(ext, "application/octet-stream"))}
    )


def upload_sample(client: TestClient, name: str = "sample_resume.txt") -> dict:
    resp = upload(client, name)
    assert resp.status_code == 201, resp.text
    return resp.json()


def jd_text(name: str = "backend_developer") -> str:
    return (JD_DIR / f"{name}.txt").read_text(encoding="utf-8")


def create_interview(client: TestClient, resume_id: str, **config) -> dict:
    body: dict = {"resume_id": resume_id, "config": {"num_questions": 5, **config}}
    resp = client.post("/api/interviews", json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()


def start_interview(client: TestClient, iid: str) -> dict:
    resp = client.post(f"/api/interviews/{iid}/start")
    assert resp.status_code == 200, resp.text
    return resp.json()


def answer(client: TestClient, iid: str, qid: str, text: str):
    return client.post(f"/api/interviews/{iid}/answer", json={"question_id": qid, "answer": text})


SOLID_ANSWER = (
    "In my internship at BrightCart I built REST API endpoints in Flask backed by PostgreSQL. First I profiled the "
    "slow queries with EXPLAIN, then I added indexes and cached frequent reads in Redis, because the dashboard was "
    "read-heavy. For example, p95 latency dropped from 500 ms to 300 ms, which I measured before and after with a "
    "load test. The trade-off was cache invalidation, so I used a short TTL and invalidated keys on writes."
)


def run_to_end(client: TestClient, iid: str, text: str = SOLID_ANSWER, limit: int = 60) -> dict:
    """Answer every question until the interview reaches CLOSING, then finish it. Returns the final view."""
    iv = client.get(f"/api/interviews/{iid}").json()
    for _ in range(limit):
        cq = iv["current_question"]
        if cq is None:
            break
        resp = answer(client, iid, cq["id"], text)
        assert resp.status_code == 200, resp.text
        iv = resp.json()
    assert iv["state"] == "CLOSING", iv["state"]
    resp = client.post(f"/api/interviews/{iid}/finish")
    assert resp.status_code == 200, resp.text
    return resp.json()


def completed_interview(client: TestClient, resume_name: str = "sample_resume.txt", **config) -> dict:
    resume = upload_sample(client, resume_name)
    iv = create_interview(client, resume["id"], **config)
    start_interview(client, iv["id"])
    return run_to_end(client, iv["id"])
