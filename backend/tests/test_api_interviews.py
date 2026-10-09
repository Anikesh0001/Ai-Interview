"""API: interview lifecycle, answering, follow-ups, recovery, reports, history and dashboard."""

from __future__ import annotations

import pytest
from fakes import FakeProvider
from helpers import (
    SOLID_ANSWER,
    answer,
    completed_interview,
    create_interview,
    jd_text,
    run_to_end,
    start_interview,
    upload_sample,
)

from app.ai.llm import set_provider

VAGUE_CLAIM_ANSWER = (
    "We reduced the API latency by working on the backend and making a lot of optimizations across the system so it "
    "was much faster for the users."
)
INTRO_ANSWER = (
    "I'm a final-year computer science student. I build full-stack apps with React and Flask, and during my "
    "internship I built REST APIs for an order-tracking dashboard. I enjoy backend engineering because I like "
    "designing data models and making systems fast."
)


@pytest.fixture
def resume(client) -> dict:
    return upload_sample(client)


@pytest.fixture
def started(client, resume) -> dict:
    iv = create_interview(client, resume["id"], num_questions=5)
    return start_interview(client, iv["id"])


def _events(client, iid):
    return client.get(f"/api/interviews/{iid}").json()["messages"]


def test_create_interview(client, resume):
    iv = create_interview(client, resume["id"], num_questions=6, personality="Friendly", difficulty="Hard")
    assert iv["state"] == "CREATED"
    assert iv["messages"] == [] and iv["current_question"] is None
    assert iv["config"]["num_questions"] == 6 and iv["config"]["personality"] == "Friendly"
    assert iv["progress"] == {"answered": 0, "total": 6, "follow_ups": 0, "percent": 0.0}
    assert iv["interviewer"]["name"] == "Sam Rivera"
    assert iv["candidate_name"] == "Aarav Sharma"
    assert iv["ai_mode"] == "offline"


@pytest.mark.parametrize(
    "config",
    [
        {"num_questions": 2},
        {"num_questions": 26},
        {"difficulty": "Impossible"},
        {"personality": "Pirate"},
        {"unknown_field": 1},
        {"target_role": "x"},
    ],
)
def test_create_interview_validation(client, resume, config):
    resp = client.post("/api/interviews", json={"resume_id": resume["id"], "config": config})
    assert resp.status_code == 422


def test_create_interview_unknown_resume(client):
    assert client.post("/api/interviews", json={"resume_id": "nope"}).status_code == 404


def test_create_interview_with_jd(client, resume):
    resp = client.post(
        "/api/interviews",
        json={
            "resume_id": resume["id"],
            "job_description": jd_text("backend_developer"),
            "config": {"num_questions": 8},
        },
    )
    assert resp.status_code == 201
    assert resp.json()["jd_id"]


def test_start_is_idempotent(client, started):
    iid = started["id"]
    assert started["state"] == "INTRO"
    greetings = [m for m in started["messages"] if m["role"] == "interviewer"]
    assert len(greetings) == 3  # hello, format, first question
    assert greetings[0]["text"].startswith("Hi Aarav")
    cq = started["current_question"]
    assert cq["category"] == "intro" and cq["number"] == 1 and cq["is_follow_up"] is False
    again = client.post(f"/api/interviews/{iid}/start").json()
    assert again["messages"] == started["messages"]
    assert again["current_question"] == cq


def test_answer_question(client, started):
    iid = started["id"]
    q1 = started["current_question"]
    resp = answer(client, iid, q1["id"], INTRO_ANSWER)
    assert resp.status_code == 200
    iv = resp.json()
    assert iv["progress"]["answered"] == 1
    assert iv["current_question"]["id"] != q1["id"]
    assert iv["current_question"]["number"] == 2
    candidate = [m for m in iv["messages"] if m["role"] == "candidate"]
    assert [m["text"] for m in candidate] == [INTRO_ANSWER]
    assert candidate[0]["question_id"] == q1["id"]
    # the next interviewer message ends with the new question
    assert iv["messages"][-1]["role"] == "interviewer"
    assert iv["messages"][-1]["text"].endswith(iv["current_question"]["text"])


def test_answer_stale_question_409(client, started):
    resp = answer(client, started["id"], "0" * 32, "Some answer.")
    assert resp.status_code == 409
    assert resp.json()["code"] == "interview_error"


@pytest.mark.parametrize("text", ["", "   ", "\n\t"])
def test_empty_answer_422(client, started, text):
    resp = answer(client, started["id"], started["current_question"]["id"], text)
    assert resp.status_code == 422
    assert "answer" in resp.json()["detail"].lower()
    assert client.get(f"/api/interviews/{started['id']}").json()["current_question"] == started["current_question"]


def test_too_long_answer_422(client, started):
    resp = answer(client, started["id"], started["current_question"]["id"], "x" * 6001)
    assert resp.status_code == 422
    assert resp.json()["detail"].endswith("That text is too long.")


def test_duplicate_submit_is_noop(client, started):
    iid = started["id"]
    q1 = started["current_question"]
    first = answer(client, iid, q1["id"], INTRO_ANSWER).json()
    dup = answer(client, iid, q1["id"], INTRO_ANSWER)
    assert dup.status_code == 200
    assert dup.json()["messages"] == first["messages"]
    assert dup.json()["current_question"] == first["current_question"]
    assert dup.json()["progress"] == first["progress"]


def test_answer_before_start_409(client, resume):
    iv = create_interview(client, resume["id"])
    resp = answer(client, iv["id"], "x", "hello")
    assert resp.status_code == 409


def test_vague_claim_answer_triggers_follow_up(client, started):
    iid = started["id"]
    iv = answer(client, iid, started["current_question"]["id"], INTRO_ANSWER).json()
    claim_q = iv["current_question"]
    assert claim_q["category"] == "claim_verification"
    assert "40%" in claim_q["text"]
    iv = answer(client, iid, claim_q["id"], VAGUE_CLAIM_ANSWER).json()
    fu = iv["current_question"]
    assert fu["is_follow_up"] is True
    assert fu["number"] == claim_q["number"]  # follow-ups don't advance the main question number
    assert iv["state"] == "CHALLENGE"
    assert iv["progress"]["follow_ups"] == 1
    assert iv["messages"][-1]["kind"] == "follow_up"
    assert fu["text"] != claim_q["text"]


def test_skip_via_next_question(client, started):
    iid = started["id"]
    q1 = started["current_question"]
    resp = client.post(f"/api/interviews/{iid}/next-question", json={"question_id": q1["id"]})
    assert resp.status_code == 200
    iv = resp.json()
    assert iv["current_question"]["id"] != q1["id"]
    assert any(m["text"] == "(Skipped this question)" for m in iv["messages"])
    assert iv["messages"][-1]["text"].startswith("No problem, let's move on.")
    # skipping a stale question is rejected
    stale = client.post(f"/api/interviews/{iid}/next-question", json={"question_id": q1["id"]})
    assert stale.status_code == 409


def test_finish_and_report(client, started):
    iid = started["id"]
    assert client.get(f"/api/interviews/{iid}/report").status_code == 404
    final = run_to_end(client, iid)
    assert final["state"] == "COMPLETED"
    assert final["finished_at"] and final["progress"]["percent"] == 100.0
    assert final["current_question"] is None
    report = client.get(f"/api/interviews/{iid}/report").json()
    assert report["interview_id"] == iid
    assert len([q for q in report["questions"] if not q["is_follow_up"]]) == 5
    # finishing twice is harmless
    again = client.post(f"/api/interviews/{iid}/finish")
    assert again.status_code == 200 and again.json()["state"] == "COMPLETED"
    # completed interviews accept no more answers
    assert answer(client, iid, "x", "late").status_code == 409


def test_finish_early_mid_interview(client, started):
    iid = started["id"]
    answer(client, iid, started["current_question"]["id"], INTRO_ANSWER)
    resp = client.post(f"/api/interviews/{iid}/finish")
    assert resp.status_code == 200
    data = resp.json()
    assert data["state"] == "COMPLETED"
    assert any("Let's stop here for today." in m["text"] for m in data["messages"])
    report = client.get(f"/api/interviews/{iid}/report").json()
    assert report["unanswered_questions"]  # the open question is listed, not scored


def test_finish_before_start_409(client, resume):
    iv = create_interview(client, resume["id"])
    assert client.post(f"/api/interviews/{iv['id']}/finish").status_code == 409


def test_report_pdf(client):
    iv = completed_interview(client, num_questions=4)
    resp = client.get(f"/api/interviews/{iv['id']}/report.pdf")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content.startswith(b"%PDF")
    assert "attachment" in resp.headers["content-disposition"]


def test_report_pdf_404_before_finish(client, started):
    assert client.get(f"/api/interviews/{started['id']}/report.pdf").status_code == 404


def test_transcript(client):
    iv = completed_interview(client, num_questions=3)
    resp = client.get(f"/api/interviews/{iv['id']}/transcript")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/plain")
    assert "attachment" in resp.headers["content-disposition"]
    body = resp.text
    assert body.startswith("InterviewForge transcript")
    assert "Maya Chen: Hi Aarav" in body
    assert f"Aarav Sharma: {SOLID_ANSWER}" in body


def test_history_and_dashboard(client):
    iv = completed_interview(client, num_questions=4)
    history = client.get("/api/interviews/history").json()
    assert len(history) == 1
    h = history[0]
    assert h["id"] == iv["id"] and h["state"] == "COMPLETED"
    assert h["num_questions"] == 4 and h["resume_filename"] == "sample_resume.txt" and h["has_jd"] is False
    for k in ("interview_score", "ats_score", "readiness_score"):
        assert 0 <= h[k] <= 100
    assert h["jd_score"] is None

    dash = client.get("/api/dashboard").json()
    assert dash["interviews_completed"] == 1
    assert dash["latest_interview_score"] == h["interview_score"]
    assert dash["best_score"] == dash["average_score"] == h["interview_score"]
    assert dash["improvement"] is None
    assert [t["id"] for t in dash["trend"]] == [iv["id"]]
    assert [r["id"] for r in dash["recent"]] == [iv["id"]]
    assert dash["active_interviews"] == []
    assert dash["has_resume"] is True
    assert dash["resume_health"]["filename"] == "sample_resume.txt"
    assert 0 <= dash["resume_health"]["ats_score"] <= 100
    assert all(w["score"] < 75 for w in dash["weak_skills"])


def test_empty_dashboard(client):
    dash = client.get("/api/dashboard").json()
    assert dash["interviews_completed"] == 0
    assert dash["latest_interview_score"] is None and dash["resume_health"] is None
    assert dash["has_resume"] is False


def test_session_recovery(client, started):
    iid = started["id"]
    mid = answer(client, iid, started["current_question"]["id"], INTRO_ANSWER).json()
    recovered = client.get(f"/api/interviews/{iid}")
    assert recovered.status_code == 200
    data = recovered.json()
    assert data["current_question"] == mid["current_question"]
    assert data["messages"] == mid["messages"]
    assert [m["seq"] for m in data["messages"]] == sorted(m["seq"] for m in data["messages"])
    assert data["state"] == mid["state"]
    active = client.get("/api/interviews/active").json()
    assert [a["id"] for a in active] == [iid]
    assert active[0]["current_question"] == mid["current_question"]
    # created-but-not-started and completed interviews are not "active"
    create_interview(client, started["resume_id"])
    assert [a["id"] for a in client.get("/api/interviews/active").json()] == [iid]
    run_to_end(client, iid)
    assert client.get("/api/interviews/active").json() == []


def test_delete_interview(client, started):
    iid = started["id"]
    assert client.delete(f"/api/interviews/{iid}").status_code == 204
    assert client.get(f"/api/interviews/{iid}").status_code == 404
    assert client.delete(f"/api/interviews/{iid}").status_code == 404
    assert client.get("/api/interviews/history").json() == []


def test_unknown_interview_404(client):
    for method, path in (
        ("get", "/api/interviews/nope"),
        ("post", "/api/interviews/nope/start"),
        ("post", "/api/interviews/nope/finish"),
        ("get", "/api/interviews/nope/report"),
        ("get", "/api/interviews/nope/transcript"),
    ):
        assert getattr(client, method)(path).status_code == 404, path


@pytest.mark.parametrize("itype", ["Mixed", "Behavioral", "Technical", "HR", "Project Deep Dive", "Coding"])
def test_whole_interview_never_repeats_a_question(client, resume, itype):
    iv = create_interview(client, resume["id"], num_questions=15, interview_type=itype)
    start_interview(client, iv["id"])
    final = run_to_end(client, iv["id"], text="I'm not sure, we just made it work somehow.")
    report = client.get(f"/api/interviews/{final['id']}/report").json()
    texts = [q["question"] for q in report["questions"]]
    assert len(texts) >= 15
    assert len(texts) == len(set(texts)), texts
    from app.interview.textutil import question_hash

    hashes = [question_hash(t) for t in texts]
    assert len(hashes) == len(set(hashes))


def test_interview_completes_with_failing_llm(client, resume):
    """A provider that is 'available' but never returns valid JSON must not break the interview."""
    fake = FakeProvider(default="```json\n{oops\n```")
    set_provider(fake)
    iv = create_interview(client, resume["id"], num_questions=4)
    start_interview(client, iv["id"])
    final = run_to_end(client, iv["id"])
    assert final["state"] == "COMPLETED"
    assert fake.calls  # the LLM was tried
    report = client.get(f"/api/interviews/{iv['id']}/report").json()
    assert report["narrative_source"] == "rules"
    assert set(report["evaluators"]) == {"heuristic"}
    assert all(q["evaluator"] == "heuristic" for q in report["questions"])


def test_report_failure_then_retry(client, started, monkeypatch):
    """A crash while building the report moves the interview to FAILED; finishing again recovers it."""
    import app.interview.report as report_mod

    iid = started["id"]
    answer(client, iid, started["current_question"]["id"], INTRO_ANSWER)
    real = report_mod.build_report

    def boom(db, interview):
        raise RuntimeError("disk full")

    monkeypatch.setattr(report_mod, "build_report", boom)
    resp = client.post(f"/api/interviews/{iid}/finish")
    assert resp.status_code == 500
    assert resp.json()["detail"] == "We couldn't generate the report. Please retry."
    failed = client.get(f"/api/interviews/{iid}").json()
    assert failed["state"] == "FAILED"
    assert failed["error"]
    assert answer(client, iid, "x", "late").status_code == 409

    monkeypatch.setattr(report_mod, "build_report", real)
    resp = client.post(f"/api/interviews/{iid}/finish")
    assert resp.status_code == 200
    assert resp.json()["state"] == "COMPLETED" and resp.json()["error"] is None
    assert client.get(f"/api/interviews/{iid}/report").status_code == 200
