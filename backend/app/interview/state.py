"""Explicit interview state machine. Every transition is validated and persisted as an event."""

from __future__ import annotations

from enum import StrEnum


class State(StrEnum):
    CREATED = "CREATED"
    PREPARING = "PREPARING"
    INTRO = "INTRO"
    RESUME = "RESUME"
    PROJECT = "PROJECT"
    TECHNICAL = "TECHNICAL"
    PROBLEM_SOLVING = "PROBLEM_SOLVING"
    BEHAVIORAL = "BEHAVIORAL"
    CHALLENGE = "CHALLENGE"
    CLOSING = "CLOSING"
    EVALUATING = "EVALUATING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


QUESTION_STATES = {
    State.INTRO,
    State.RESUME,
    State.PROJECT,
    State.TECHNICAL,
    State.PROBLEM_SOLVING,
    State.BEHAVIORAL,
    State.CHALLENGE,
}
ACTIVE_STATES = QUESTION_STATES | {State.CREATED, State.PREPARING, State.CLOSING}
_ANY_QUESTION = QUESTION_STATES | {State.CLOSING, State.EVALUATING, State.FAILED}

TRANSITIONS: dict[State, set[State]] = {
    State.CREATED: {State.PREPARING, State.FAILED},
    State.PREPARING: {State.INTRO, State.FAILED} | QUESTION_STATES,
    **{s: _ANY_QUESTION - {s} for s in QUESTION_STATES},
    State.CLOSING: {State.EVALUATING, State.FAILED},
    State.EVALUATING: {State.COMPLETED, State.FAILED},
    State.FAILED: {State.EVALUATING},
    State.COMPLETED: set(),
}


class InvalidTransition(Exception):
    pass


def can_transition(current: str, new: str) -> bool:
    return State(new) in TRANSITIONS[State(current)] or current == new


def assert_transition(current: str, new: str) -> None:
    if not can_transition(current, new):
        raise InvalidTransition(f"Cannot move interview from {current} to {new}")
