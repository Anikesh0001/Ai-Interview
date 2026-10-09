"""Final report generation and score aggregation."""

from __future__ import annotations

import json
import math

import pytest
from fakes import FakeProvider
from helpers import completed_interview, create_interview, jd_text, run_to_end, start_interview, upload_sample

from app.ai.llm import set_provider
from app.config import get_settings
from app.interview.report import DISCLAIMERS, _weighted

REQUIRED_SECTIONS = (
    "executive_summary",
    "verdict",
    "skills",
    "questions",
    "claims",
    "study_topics",
    "action_plan",
    "readiness_formula",
)


def _narrative_text(report: dict) -> str:
    return " ".join(
        [report["executive_summary"], report["verdict"], report["communication_feedback"], *report["action_plan"]]
    )


def test_weighted_redistributes_missing_parts():
    weights = {"interview": 0.4, "jd_match": 0.3, "ats": 0.2, "evidence": 0.1}
    score, eff = _weighted({"interview": 80, "jd_match": None, "ats": 60, "evidence": 50}, weights)
    assert set(eff) == {"interview", "ats", "evidence"}
    assert math.isclose(sum(eff.values()), 1.0)
    assert math.isclose(eff["interview"], 0.4 / 0.7)
    assert math.isclose(score, (80 * 0.4 + 60 * 0.2 + 50 * 0.1) / 0.7)
    full, eff_full = _weighted({"interview": 80, "jd_match": 70, "ats": 60, "evidence": 50}, weights)
    assert math.isclose(full, 80 * 0.4 + 70 * 0.3 + 60 * 0.2 + 50 * 0.1)
    assert eff_full == pytest.approx(weights)
    assert _weighted({"interview": None}, weights) == (None, {})


def test_report_sections_and_scores_without_jd(client):
    iv = completed_interview(client, num_questions=5)
    assert iv["state"] == "COMPLETED"
    report = client.get(f"/api/interviews/{iv['id']}/report").json()
    for key in REQUIRED_SECTIONS:
        assert key in report, key
    assert report["executive_summary"] and report["verdict"]
    assert report["questions"] and all(0 <= q["score"] <= 100 for q in report["questions"])
    assert report["action_plan"]
    assert report["disclaimers"] == DISCLAIMERS
    assert report["ai_mode"] == "offline" and report["narrative_source"] == "rules"
    scores = report["scores"]
    assert scores["jd_match"] is None and report["jd"] is None
    for k in ("ats", "interview", "readiness"):
        assert 0 <= scores[k] <= 100

    # readiness: JD weight is redistributed proportionally over the remaining components
    comps = {c["key"]: c for c in report["readiness_formula"]["components"]}
    assert comps["jd_match"]["weight"] == 0 and comps["jd_match"]["score"] is None
    configured = get_settings().weights("readiness")
    remaining = 1 - configured["jd_match"]
    for k in ("interview", "ats", "evidence"):
        assert comps[k]["weight"] == pytest.approx(configured[k] / remaining, abs=1e-3)
        assert comps[k]["configured_weight"] == pytest.approx(configured[k], abs=1e-3)
    expected = sum(comps[k]["score"] * configured[k] / remaining for k in ("interview", "ats", "evidence"))
    assert scores["readiness"] == pytest.approx(expected, abs=0.2)

    # category weights also sum to one over the available categories
    cats = [c for c in report["category_scores"] if c["key"] != "resume_knowledge"]
    assert sum(c["weight"] for c in cats) == pytest.approx(1.0, abs=1e-2)

    text = _narrative_text(report)
    assert "probability of" not in text.lower()
    assert "hired" not in report["verdict"].lower()


def test_report_with_jd_uses_configured_readiness_weights(client):
    resume = upload_sample(client)
    resp = client.post(
        "/api/interviews",
        json={
            "resume_id": resume["id"],
            "job_description": jd_text("backend_developer"),
            "config": {"num_questions": 5},
        },
    )
    iv = resp.json()
    start_interview(client, iv["id"])
    run_to_end(client, iv["id"])
    report = client.get(f"/api/interviews/{iv['id']}/report").json()
    assert report["scores"]["jd_match"] is not None
    assert report["jd"]["score"] == report["scores"]["jd_match"]
    comps = {c["key"]: c for c in report["readiness_formula"]["components"]}
    assert all(c["weight"] == pytest.approx(c["configured_weight"], abs=1e-3) for c in comps.values())
    # required JD skills missing from the resume become study topics
    topics = {t["topic"] for t in report["study_topics"]}
    assert "Kubernetes" not in topics  # preferred, not required
    assert "Kafka or RabbitMQ" in topics


def test_claims_section_reports_confidence(client):
    resume = upload_sample(client)
    iv = create_interview(client, resume["id"], num_questions=5)
    iv = start_interview(client, iv["id"])
    iv = client.post(
        f"/api/interviews/{iv['id']}/answer",
        json={"question_id": iv["current_question"]["id"], "answer": "I am a final-year student who builds web apps."},
    ).json()
    assert iv["current_question"]["category"] == "claim_verification"
    final = run_to_end(client, iv["id"])
    report = client.get(f"/api/interviews/{final['id']}/report").json()
    assert report["claims"]
    for c in report["claims"]:
        assert c["confidence"] in ("High", "Medium", "Low") and c["claim"] and c["note"]


def test_report_rejects_llm_hiring_probability_narrative(client):
    bad = json.dumps(
        {
            "executive_summary": "You did well overall and have an 85% probability of being hired at this company.",
            "verdict": "Your probability of getting hired is high.",
            "communication_feedback": "Clear.",
        }
    )
    resume = upload_sample(client)
    iv = create_interview(client, resume["id"], num_questions=3)
    start_interview(client, iv["id"])
    # Every LLM call before finish returns garbage (deterministic fallback); the report call gets 'bad' twice.
    fake = FakeProvider(default="not json")
    set_provider(fake)
    run_iv = client.get(f"/api/interviews/{iv['id']}").json()
    for _ in range(20):
        cq = run_iv["current_question"]
        if cq is None:
            break
        run_iv = client.post(
            f"/api/interviews/{iv['id']}/answer", json={"question_id": cq["id"], "answer": "I used Flask and SQL."}
        ).json()
    fake.replies.extend([bad, bad])
    done = client.post(f"/api/interviews/{iv['id']}/finish").json()
    assert done["state"] == "COMPLETED"
    report = client.get(f"/api/interviews/{iv['id']}/report").json()
    assert report["narrative_source"] == "rules"
    assert "probability of" not in _narrative_text(report).lower()


def test_report_accepts_valid_llm_narrative(client):
    good = json.dumps(
        {
            "executive_summary": "You explained Flask APIs well but struggled with database indexing depth.",
            "verdict": "Approaching readiness for junior roles; practise indexing trade-offs first.",
            "communication_feedback": "Answers were short; add a concrete example.",
        }
    )
    resume = upload_sample(client)
    iv = create_interview(client, resume["id"], num_questions=3)
    start_interview(client, iv["id"])
    run_iv = client.get(f"/api/interviews/{iv['id']}").json()
    for _ in range(20):
        cq = run_iv["current_question"]
        if cq is None:
            break
        run_iv = client.post(
            f"/api/interviews/{iv['id']}/answer", json={"question_id": cq["id"], "answer": "I used Flask and SQL."}
        ).json()
    set_provider(FakeProvider([good]))
    client.post(f"/api/interviews/{iv['id']}/finish")
    report = client.get(f"/api/interviews/{iv['id']}/report").json()
    assert report["narrative_source"] == "llm"
    assert report["executive_summary"].startswith("You explained Flask APIs well")
    assert report["scores"]["interview"] is not None  # numbers still computed by the backend
