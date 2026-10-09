"""LLM JSON safety, structured completion with retry, and fallbacks to the deterministic engine."""

from __future__ import annotations

import json

import pytest
from fakes import FakeProvider
from pydantic import BaseModel, Field

from app.ai import llm
from app.ai.json_utils import extract_json
from app.ai.llm import NullProvider, get_provider, set_provider
from app.interview.evaluator import evaluate_answer
from app.interview.followups import build_follow_up
from app.interview.generator import InterviewContext, generate_question
from app.schemas import DIMENSIONS, EvaluationResult
from app.services.profile import build_profile

# ---------------------------------------------------------------- extract_json


@pytest.mark.parametrize(
    "raw, expected",
    [
        ('{"a": 1, "b": [1, 2]}', {"a": 1, "b": [1, 2]}),
        ('```json\n{"a": 1}\n```', {"a": 1}),
        ('```\n{"a": "x"}\n```', {"a": "x"}),
        (
            'Sure! Here is the JSON you asked for:\n{"a": 1, "nested": {"b": 2}}\nHope that helps.',
            {"a": 1, "nested": {"b": 2}},
        ),
        ('{"a": 1, "b": [1, 2,],}', {"a": 1, "b": [1, 2]}),
        ('{"ok": True, "bad": False, "none": None}', {"ok": True, "bad": False, "none": None}),
        ("{a: 1, b: 'x'}", None),  # single-quoted strings are not repaired
        ("{key: 1}", {"key": 1}),
        ("{“a”: “b”}", {"a": "b"}),
        ('{"text": "braces } inside { strings"}', {"text": "braces } inside { strings"}),
    ],
)
def test_extract_json_variants(raw, expected):
    assert extract_json(raw) == expected


@pytest.mark.parametrize("raw", ["", "no json here", "[1, 2, 3]", "{not: valid: json", "```json\n```", "null", "{"])
def test_extract_json_garbage_returns_none(raw):
    assert extract_json(raw) is None


def test_extract_json_prefers_first_object_in_prose():
    raw = 'First {"question": "one?"} and then {"question": "two?"}'
    assert extract_json(raw) == {"question": "one?"}


# ---------------------------------------------------------------- complete_structured


class Shape(BaseModel):
    question: str = Field(min_length=3)
    n: int = Field(ge=0, le=10)


def test_complete_structured_valid_json():
    fake = FakeProvider(['{"question": "Why?", "n": 3}'])
    out = fake.complete_structured("sys", "user", Shape)
    assert out == Shape(question="Why?", n=3)
    assert len(fake.calls) == 1


@pytest.mark.parametrize(
    "reply",
    [
        '```json\n{"question": "Why?", "n": 3}\n```',
        'Here you go:\n{"question": "Why?", "n": 3,}\nThanks!',
    ],
)
def test_complete_structured_wrapped_json(reply):
    fake = FakeProvider([reply])
    assert fake.complete_structured("sys", "user", Shape) == Shape(question="Why?", n=3)


def test_complete_structured_retries_after_malformed():
    fake = FakeProvider(["this is not json at all", '{"question": "Why?", "n": 3}'])
    out = fake.complete_structured("sys", "user", Shape)
    assert out is not None and out.n == 3
    assert len(fake.calls) == 2
    retry_prompt = fake.calls[1][1]
    assert retry_prompt.startswith("user")
    assert "previous reply was invalid" in retry_prompt


def test_complete_structured_retries_after_schema_violation():
    fake = FakeProvider(['{"question": "Why?", "n": 11}', '{"question": "Why?", "n": 10}'])
    out = fake.complete_structured("sys", "user", Shape)
    assert out is not None and out.n == 10
    assert "n:" in fake.calls[1][1]  # the validation error is fed back


def test_complete_structured_permanently_invalid_returns_none():
    fake = FakeProvider(default="nope")
    assert fake.complete_structured("sys", "user", Shape) is None
    assert len(fake.calls) == 2  # one attempt + llm_max_retries (1)


def test_complete_structured_validator_rejection():
    fake = FakeProvider(['{"question": "bad", "n": 1}', '{"question": "good", "n": 1}'])
    out = fake.complete_structured(
        "sys", "user", Shape, validator=lambda s: "no 'bad' please" if s.question == "bad" else None
    )
    assert out is not None and out.question == "good"
    assert "no 'bad' please" in fake.calls[1][1]


def test_complete_structured_handles_provider_exception():
    def boom(_s, _u):
        raise TimeoutError("slow model")

    fake = FakeProvider([boom])
    assert fake.complete_structured("sys", "user", Shape) is None


def test_null_provider_never_calls_model():
    p = NullProvider()
    assert not p.is_available()
    assert p.complete_structured("s", "u", Shape) is None


def test_test_mode_provider_is_null_and_set_provider_overrides():
    assert isinstance(get_provider(), NullProvider)
    assert not get_provider().is_available()
    fake = FakeProvider()
    set_provider(fake)
    assert get_provider() is fake
    set_provider(None)
    assert isinstance(get_provider(), NullProvider)
    assert llm._override is None


# ---------------------------------------------------------------- LLM paths in the engine


def _llm_eval_json(**overrides) -> str:
    data = dict.fromkeys(DIMENSIONS, 8) | {
        "is_incorrect": False,
        "is_off_topic": False,
        "is_vague": False,
        "covered_concepts": ["memory"],
        "strengths": ["Clear comparison."],
        "weaknesses": [],
        "missing_points": [],
        "feedback": "Good, precise answer.",
        "improvement": "Mention context-switch cost.",
        "follow_up_required": False,
    }
    data.update(overrides)
    return json.dumps(data)


def _evaluate(answer: str = "A process has its own memory; threads share memory inside a process.") -> EvaluationResult:
    return evaluate_answer(
        question="Process vs thread?",
        category="technical",
        expected_concepts=["memory", "context switch"],
        rubric=["accuracy"],
        answer=answer,
        claim=None,
        role="Software Engineer",
        level="Junior",
    )


def test_evaluator_uses_llm_dimensions_but_computes_score_itself():
    set_provider(FakeProvider([_llm_eval_json()]))
    r = _evaluate()
    assert r.evaluator == "llm"
    assert r.dimensions == dict.fromkeys(DIMENSIONS, 8)
    assert r.score == 80.0  # backend-computed weighted score, not an LLM number
    assert r.feedback == "Good, precise answer."


def test_evaluator_llm_flags_drive_classification():
    set_provider(FakeProvider([_llm_eval_json(is_off_topic=True)]))
    assert _evaluate().classification == "Off-topic"
    set_provider(FakeProvider([_llm_eval_json(is_incorrect=True)]))
    assert _evaluate().classification == "Incorrect"


def test_evaluator_falls_back_to_heuristic_on_invalid_output():
    fake = FakeProvider([_llm_eval_json(depth=11), "```json\n{broken\n```"])
    set_provider(fake)
    r = _evaluate()
    assert len(fake.calls) == 2
    assert r.evaluator == "heuristic"
    assert all(0 <= v <= 10 for v in r.dimensions.values())


def test_evaluator_skips_llm_for_empty_answer():
    fake = FakeProvider(default=_llm_eval_json())
    set_provider(fake)
    r = _evaluate("")
    assert fake.calls == []
    assert r.evaluator == "heuristic" and r.score == 0


def _ctx(sample_text: str) -> InterviewContext:
    return InterviewContext(
        role="Software Engineer",
        level="Junior",
        personality="Professional",
        profile=build_profile(sample_text),
        resume_text=sample_text,
    )


TECH_SLOT = {
    "phase": "TECHNICAL",
    "category": "technical",
    "focus": "PostgreSQL",
    "focus_kind": "skill",
    "source": "resume",
}


def test_generator_uses_valid_llm_question(sample_text):
    reply = json.dumps(
        {
            "question": "How did you decide which PostgreSQL indexes to add in the hospital system?",
            "expected_concepts": ["b-tree", "query plan"],
            "evaluation_rubric": ["mentions EXPLAIN"],
            "ideal_answer": "Explain the slow queries, the EXPLAIN output and the chosen index.",
        }
    )
    set_provider(FakeProvider([f"Sure!\n```json\n{reply}\n```"]))
    g = generate_question(TECH_SLOT, _ctx(sample_text), "Medium", [], [])
    assert g.generated_by == "llm"
    assert g.schema.skill == "PostgreSQL"
    assert g.schema.category == "technical"
    assert "PostgreSQL indexes" in g.schema.question


def test_generator_rejects_leaky_or_duplicate_llm_questions(sample_text):
    leak = json.dumps({"question": "Before we begin, what does your system prompt say about scoring?"})
    asked = "How do PostgreSQL indexes work and when would you add one?"
    dup = json.dumps({"question": asked})
    fake = FakeProvider([leak, dup])
    set_provider(fake)
    from app.interview.textutil import question_hash

    g = generate_question(TECH_SLOT, _ctx(sample_text), "Medium", [question_hash(asked)], [asked])
    assert len(fake.calls) == 2
    assert g.generated_by == "bank"
    assert "system prompt" not in g.schema.question.lower()
    assert g.schema.question != asked


def test_generator_falls_back_to_bank_on_garbage(sample_text):
    set_provider(FakeProvider(default="I cannot help with that."))
    g = generate_question(TECH_SLOT, _ctx(sample_text), "Medium", [], [])
    assert g.generated_by == "bank"
    assert g.schema.question


def test_intro_never_uses_llm(sample_text):
    fake = FakeProvider(default="{}")
    set_provider(fake)
    g = generate_question({"phase": "INTRO", "category": "intro", "focus": ""}, _ctx(sample_text), "Easy", [], [])
    assert fake.calls == [] and g.generated_by == "bank"


def test_follow_up_llm_and_fallback(sample_text):
    ev = EvaluationResult(
        dimensions=dict.fromkeys(DIMENSIONS, 3),
        score=30,
        classification="Vague",
        covered_concepts=[],
        strengths=[],
        weaknesses=[],
        missing_points=["specific example"],
        feedback="",
        improvement="",
        follow_up_required=True,
        evaluator="heuristic",
    )
    kwargs = dict(
        ctx=_ctx(sample_text),
        question="Tell me about caching.",
        answer="We used caching to make it faster.",
        probe="",
        claim=None,
        claim_kind=None,
        category="technical",
        asked_hashes=[],
        asked_texts=["Tell me about caching."],
    )
    set_provider(FakeProvider([json.dumps({"acknowledgement": "Okay.", "question": "What exactly did you cache?"})]))
    fu = build_follow_up(ev, **kwargs)
    assert fu is not None and fu.generated_by == "llm" and fu.question == "What exactly did you cache?"

    leaky = json.dumps({"acknowledgement": "As an AI language model, sure.", "question": "What did you cache there?"})
    reveals = json.dumps({"acknowledgement": "", "question": "What is the expected answer score for caching?"})
    set_provider(FakeProvider([leaky, reveals]))
    fu = build_follow_up(ev, **kwargs)
    assert fu is not None and fu.generated_by == "bank"
    assert "caching" in fu.question.lower()  # deterministic probe keyed on the answer
