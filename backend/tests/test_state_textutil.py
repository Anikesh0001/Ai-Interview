"""Interview state machine and question de-duplication."""

from __future__ import annotations

import pytest

from app.interview.state import (
    ACTIVE_STATES,
    QUESTION_STATES,
    TRANSITIONS,
    InvalidTransition,
    State,
    assert_transition,
    can_transition,
)
from app.interview.textutil import concept_covered, content_stems, is_duplicate, normalize, question_hash, similarity


@pytest.mark.parametrize(
    "current, new",
    [
        ("CREATED", "PREPARING"),
        ("PREPARING", "INTRO"),
        ("PREPARING", "TECHNICAL"),
        ("INTRO", "RESUME"),
        ("RESUME", "CHALLENGE"),
        ("CHALLENGE", "PROJECT"),
        ("TECHNICAL", "CLOSING"),
        ("BEHAVIORAL", "EVALUATING"),
        ("CLOSING", "EVALUATING"),
        ("EVALUATING", "COMPLETED"),
        ("EVALUATING", "FAILED"),
        ("FAILED", "EVALUATING"),
        ("CREATED", "FAILED"),
        ("INTRO", "INTRO"),  # self-transition is a no-op
    ],
)
def test_valid_transitions(current, new):
    assert can_transition(current, new)
    assert_transition(current, new)


@pytest.mark.parametrize(
    "current, new",
    [
        ("CREATED", "INTRO"),
        ("CREATED", "COMPLETED"),
        ("PREPARING", "COMPLETED"),
        ("INTRO", "COMPLETED"),
        ("CLOSING", "INTRO"),
        ("EVALUATING", "INTRO"),
        ("FAILED", "COMPLETED"),
        ("FAILED", "INTRO"),
        ("COMPLETED", "EVALUATING"),
        ("COMPLETED", "FAILED"),
        ("COMPLETED", "INTRO"),
    ],
)
def test_invalid_transitions(current, new):
    assert not can_transition(current, new)
    with pytest.raises(InvalidTransition):
        assert_transition(current, new)


def test_completed_is_terminal():
    assert TRANSITIONS[State.COMPLETED] == set()
    for s in State:
        if s is not State.COMPLETED:
            assert not can_transition("COMPLETED", s.value)


def test_every_state_has_transitions_defined():
    assert set(TRANSITIONS) == set(State)


def test_question_states_reach_closing_and_each_other():
    for s in QUESTION_STATES:
        assert can_transition(s.value, "CLOSING")
        assert can_transition(s.value, "FAILED")
        for other in QUESTION_STATES - {s}:
            assert can_transition(s.value, other.value)


def test_active_states_exclude_terminal():
    assert State.COMPLETED not in ACTIVE_STATES
    assert State.FAILED not in ACTIVE_STATES
    assert State.EVALUATING not in ACTIVE_STATES


def test_unknown_state_raises():
    with pytest.raises(ValueError):
        can_transition("NOPE", "INTRO")


# ---------------------------------------------------------------- de-duplication


def test_question_hash_ignores_case_and_punctuation():
    a = "What is a REST API?"
    assert question_hash(a) == question_hash("what is a rest api")
    assert question_hash(a) == question_hash("  What   is a REST-API!! ")
    assert question_hash(a) != question_hash("What is a GraphQL API?")
    assert len(question_hash(a)) == 16


def test_normalize():
    assert normalize("Hello, World! C++ & C#") == "hello world c++ c#"


def test_is_duplicate_exact_hash():
    q = "Explain how database indexes speed up queries."
    assert is_duplicate(q, [question_hash(q)], [])
    assert is_duplicate(q.upper(), [question_hash(q)], [])


def test_is_duplicate_near_paraphrase():
    prev = "Explain how database indexes speed up queries and when they hurt performance."
    para = "Explain how database indexes speed up the queries, and when do they hurt performance?"
    assert similarity(prev, para) >= 0.6
    assert is_duplicate(para, [], [prev])


def test_is_duplicate_rejects_different_questions():
    asked = ["Explain how database indexes speed up queries.", "Tell me about a time you resolved a conflict."]
    assert not is_duplicate(
        "How does React's virtual DOM reconciliation work?", [question_hash(a) for a in asked], asked
    )


def test_similarity_edge_cases():
    assert similarity("", "anything") == 0.0
    assert similarity("the a of", "the a of") == 0.0  # stopwords only
    assert similarity("caching invalidation strategy", "caching invalidation strategy") == 1.0


def test_concept_covered_alternatives_and_stems():
    answer = "We invalidated the cache entries with a TTL and measured the hit rate."
    low = answer.lower()
    stems = content_stems(answer)
    assert concept_covered(low, stems, "expiry|ttl")
    assert concept_covered(low, stems, "hit rate")
    assert not concept_covered(low, stems, "sharding|partitioning")
