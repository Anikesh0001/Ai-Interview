"""ATS scoring, weights, JD analysis and resume <-> JD matching."""

from __future__ import annotations

import json
import math

import pytest
from helpers import jd_text

from app.config import (
    DEFAULT_ANSWER_WEIGHTS,
    DEFAULT_ATS_WEIGHTS,
    DEFAULT_BEHAVIORAL_ANSWER_WEIGHTS,
    DEFAULT_INTERVIEW_WEIGHTS,
    DEFAULT_READINESS_WEIGHTS,
    Settings,
    get_settings,
)
from app.schemas import CandidateProfile
from app.services.ats import compute_ats
from app.services.jd import (
    InvalidJobDescription,
    analyze_job_description,
    classify_score,
    match_resume_to_jd,
    match_skill_requirement,
)
from app.services.profile import build_profile

# ---------------------------------------------------------------- weights


@pytest.mark.parametrize(
    "weights",
    [
        DEFAULT_ATS_WEIGHTS,
        DEFAULT_ANSWER_WEIGHTS,
        DEFAULT_BEHAVIORAL_ANSWER_WEIGHTS,
        DEFAULT_INTERVIEW_WEIGHTS,
        DEFAULT_READINESS_WEIGHTS,
    ],
)
def test_default_weight_groups_sum_to_one(weights):
    assert math.isclose(sum(weights.values()), 1.0, abs_tol=1e-9)


@pytest.mark.parametrize("group", ["ats", "answer", "behavioral_answer", "interview", "readiness"])
def test_settings_weights_sum_to_one(group):
    assert math.isclose(sum(get_settings().weights(group).values()), 1.0, abs_tol=1e-9)


def test_custom_weights_are_normalised():
    s = Settings(ats_weights={"keyword_match": 1.15})  # +1.0 over the default 0.15 -> total 2.0
    w = s.weights("ats")
    assert math.isclose(sum(w.values()), 1.0, abs_tol=1e-9)
    assert math.isclose(w["keyword_match"], 1.15 / 2.0)
    assert math.isclose(w["contact"], 0.05 / 2.0)
    assert set(w) == set(DEFAULT_ATS_WEIGHTS)


def test_custom_weights_from_env_json(monkeypatch):
    monkeypatch.setenv("READINESS_WEIGHTS", json.dumps({"interview": 1, "jd_match": 1, "ats": 1, "evidence": 1}))
    get_settings.cache_clear()
    w = get_settings().weights("readiness")
    assert all(math.isclose(v, 0.25) for v in w.values())


def test_invalid_custom_weights_rejected():
    with pytest.raises(ValueError):
        Settings(interview_weights={"technical": -1}).weights("interview")
    with pytest.raises(ValueError):
        Settings(readiness_weights=dict.fromkeys(DEFAULT_READINESS_WEIGHTS, 0)).weights("readiness")


def test_custom_ats_weights_change_overall(sample_text, monkeypatch):
    profile = build_profile(sample_text)
    base = compute_ats(sample_text, profile)
    monkeypatch.setenv("ATS_WEIGHTS", json.dumps(dict.fromkeys(DEFAULT_ATS_WEIGHTS, 0) | {"contact": 1}))
    get_settings.cache_clear()
    only_contact = compute_ats(sample_text, profile)
    contact = next(d for d in only_contact.dimensions if d.key == "contact")
    assert only_contact.overall == contact.score
    assert only_contact.overall != base.overall


# ---------------------------------------------------------------- ATS


def test_ats_score_in_range_and_dimensions(sample_text):
    report = compute_ats(sample_text, build_profile(sample_text))
    assert 0 <= report.overall <= 100
    assert {d.key for d in report.dimensions} == set(DEFAULT_ATS_WEIGHTS)
    assert all(0 <= d.score <= 100 for d in report.dimensions)
    assert math.isclose(sum(d.weight for d in report.dimensions), 1.0, abs_tol=1e-3)
    assert math.isclose(report.overall, sum(d.score * d.weight for d in report.dimensions), abs_tol=0.11)
    assert report.classification == classify_score(report.overall)
    assert report.keyword_source == "role_template"
    assert report.disclaimer


def test_ats_is_deterministic(sample_text):
    runs = [compute_ats(sample_text, build_profile(sample_text)).model_dump() for _ in range(3)]
    assert runs[0] == runs[1] == runs[2]
    jd = analyze_job_description(jd_text("backend_developer"))
    with_jd = [compute_ats(sample_text, build_profile(sample_text), jd=jd).model_dump() for _ in range(2)]
    assert with_jd[0] == with_jd[1]
    assert with_jd[0]["keyword_source"] == "job_description"


def _dim(report, key):
    return next(d.score for d in report.dimensions if d.key == key)


def test_missing_contact_info_lowers_contact_dimension(sample_text):
    full = compute_ats(sample_text, build_profile(sample_text))
    lines = sample_text.splitlines()
    stripped = "\n".join([lines[0], *lines[3:]])  # drop the email/phone/links lines
    no_contact_profile = build_profile(stripped)
    assert not no_contact_profile.email and not no_contact_profile.phone
    bare = compute_ats(stripped, no_contact_profile)
    assert _dim(bare, "contact") < _dim(full, "contact")
    assert bare.overall < full.overall
    assert any("email" in r.lower() for r in bare.recommendations)


def test_short_unstructured_resume_scores_low():
    text = "John Smith\nI am a developer who likes Python and wants a job in software."
    report = compute_ats(text, build_profile(text))
    assert 0 <= report.overall < 40
    assert report.ats_problems
    assert report.classification == "Weak"


@pytest.mark.parametrize(
    "score, label",
    [
        (100, "Excellent"),
        (90, "Excellent"),
        (89.9, "Strong"),
        (80, "Strong"),
        (79.9, "Good"),
        (70, "Good"),
        (69.9, "Needs Improvement"),
        (60, "Needs Improvement"),
        (59.9, "Weak"),
        (0, "Weak"),
    ],
)
def test_classification_bands(score, label):
    assert classify_score(score) == label


# ---------------------------------------------------------------- JD analysis


def test_jd_required_vs_preferred():
    jd = analyze_job_description(jd_text("backend_developer"))
    assert jd.title == "Backend Developer"
    assert "PostgreSQL" in jd.required_skills
    assert "Docker" in jd.required_skills
    assert "Kubernetes" in jd.preferred_skills and "Terraform" in jd.preferred_skills
    assert "Kubernetes" not in jd.required_skills
    assert jd.experience_years_min == 2.0
    assert jd.responsibilities
    assert jd.keywords


def test_jd_alternative_grouping():
    jd = analyze_job_description(jd_text("junior_software_engineer"))
    assert "Python or Java" in jd.required_skills
    assert "PostgreSQL or MySQL" in jd.required_skills
    assert "Python" not in jd.required_skills  # grouped, not listed separately
    assert "React" in jd.preferred_skills
    fe = analyze_job_description(jd_text("frontend_developer"))
    assert "Jest or Playwright" in fe.preferred_skills


def test_jd_experience_years():
    assert analyze_job_description(jd_text("data_analyst")).experience_years_min == 1.0
    assert analyze_job_description(jd_text("junior_software_engineer")).experience_years_min == 0.0
    text = (
        "Senior Engineer\n\nRequirements\n- 5+ years of experience with Python services\n"
        "- At least 3 years experience with AWS\n- Strong SQL skills and good communication"
    )
    jd = analyze_job_description(text)
    assert jd.experience_years_min == 3.0
    assert jd.seniority == "Senior"


def test_jd_education_requirements():
    jd = analyze_job_description(jd_text("data_analyst"))
    assert any("Bachelor" in e for e in jd.education_requirements)


@pytest.mark.parametrize("text", ["", "Python dev", "We need a Python developer. Apply now!"])
def test_too_short_jd_raises(text):
    with pytest.raises(InvalidJobDescription):
        analyze_job_description(text)


def test_non_jd_text_raises():
    text = "The quick brown fox jumps over the lazy dog while the cat sleeps on the warm windowsill all afternoon."
    with pytest.raises(InvalidJobDescription):
        analyze_job_description(text)


def test_jd_analysis_deterministic():
    a = analyze_job_description(jd_text("frontend_developer")).model_dump()
    b = analyze_job_description(jd_text("frontend_developer")).model_dump()
    assert a == b


# ---------------------------------------------------------------- matching


def test_jd_match_statuses(sample_text):
    profile = build_profile(sample_text)
    jd = analyze_job_description(jd_text("backend_developer"))
    match = match_resume_to_jd(profile, sample_text, jd)
    assert 0 <= match.score <= 100
    assert match.classification == classify_score(match.score)
    assert "PostgreSQL" in match.matched
    assert "Docker" in match.matched
    assert "Kubernetes" in match.missing
    assert "Kafka or RabbitMQ" in match.missing
    assert match.summary
    assert set(match.breakdown) <= {"required", "preferred", "keywords", "experience", "education"}
    by_req = {r.requirement: r for r in match.requirements}
    assert by_req["PostgreSQL"].evidence  # matched items carry resume evidence lines


def test_jd_match_alternative_satisfied_by_either(sample_text):
    profile = build_profile(sample_text)
    jd = analyze_job_description(jd_text("junior_software_engineer"))
    match = match_resume_to_jd(profile, sample_text, jd)
    assert "Python or Java" in match.matched
    assert "PostgreSQL or MySQL" in match.matched
    assert match.score >= 70


def test_family_partial_credit_mysql_vs_postgresql():
    text = (
        "Jane Doe\njane@example.com\n\nSKILLS\nMySQL, Python\n\nEXPERIENCE\nDeveloper | Acme | Jan 2020 - Jan 2022\n"
        "- Built reporting services with MySQL and Python for 200 users\n"
    )
    profile = build_profile(text)
    status, evidence, note = match_skill_requirement(profile, text, "PostgreSQL")
    assert status == "partial"
    assert "MySQL" in note
    assert evidence
    assert match_skill_requirement(profile, text, "MySQL")[0] == "matched"
    assert match_skill_requirement(profile, text, "Kubernetes")[0] == "missing"
    assert match_skill_requirement(profile, text, "Kubernetes or PostgreSQL")[0] == "partial"


def test_partial_counts_half():
    profile = CandidateProfile(skill_mentions={"MySQL": 1}, skills=["MySQL"])
    text = "MySQL"
    jd = analyze_job_description(
        "Database Engineer\n\nRequirements\n- PostgreSQL in production for analytics workloads\n"
        "- MySQL administration experience and tuning\n- Clear written communication with stakeholders daily"
    )
    match = match_resume_to_jd(profile, text, jd)
    statuses = {r.requirement: r.status for r in match.requirements if r.kind == "required_skill"}
    assert statuses["PostgreSQL"] == "partial"
    assert statuses["MySQL"] == "matched"
    assert "PostgreSQL" in match.partial
