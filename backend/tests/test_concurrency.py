"""A slow LLM call must never hold SQLite's write lock: other requests keep working while an answer is evaluated,
and a duplicate submit (page reload mid-request) waits for the first one instead of failing."""

from __future__ import annotations

import threading
import time

import pytest
from helpers import SOLID_ANSWER, answer, create_interview, start_interview, upload_sample

from app.interview import engine


@pytest.fixture
def slow_evaluation(monkeypatch):
    """Make answer evaluation block (like a slow local model) until the test releases it."""
    entered = threading.Event()
    release = threading.Event()
    real = engine.evaluate_answer

    def slow(*args, **kwargs):
        entered.set()
        assert release.wait(30), "test never released the evaluation"
        return real(*args, **kwargs)

    monkeypatch.setattr(engine, "evaluate_answer", slow)
    yield entered, release
    release.set()


def _in_thread(fn):
    out: dict = {}
    t = threading.Thread(target=lambda: out.setdefault("resp", fn()))
    t.start()
    return t, out


def test_other_writes_succeed_while_an_answer_is_being_evaluated(client, slow_evaluation):
    entered, release = slow_evaluation
    resume = upload_sample(client)
    iv = start_interview(client, create_interview(client, resume["id"])["id"])
    t, out = _in_thread(lambda: answer(client, iv["id"], iv["current_question"]["id"], SOLID_ANSWER))
    assert entered.wait(10)

    # Before the fix this waited for SQLite's 5 s busy timeout and failed with 503 "database is locked".
    began = time.monotonic()
    other = client.post("/api/interviews", json={"resume_id": resume["id"], "config": {"num_questions": 5}})
    assert other.status_code == 201, other.text
    assert time.monotonic() - began < 3

    release.set()
    t.join(30)
    assert out["resp"].status_code == 200, out["resp"].text


def test_duplicate_submit_during_evaluation_returns_the_same_result(client, slow_evaluation):
    entered, release = slow_evaluation
    resume = upload_sample(client)
    iv = start_interview(client, create_interview(client, resume["id"])["id"])
    qid = iv["current_question"]["id"]
    first, first_out = _in_thread(lambda: answer(client, iv["id"], qid, SOLID_ANSWER))
    assert entered.wait(10)
    second, second_out = _in_thread(lambda: answer(client, iv["id"], qid, SOLID_ANSWER))
    time.sleep(0.3)  # the second request is now waiting for the first one
    release.set()
    first.join(30)
    second.join(30)

    a, b = first_out["resp"], second_out["resp"]
    assert a.status_code == 200, a.text
    assert b.status_code == 200, b.text
    assert a.json()["current_question"]["id"] == b.json()["current_question"]["id"] != qid
    final = client.get(f"/api/interviews/{iv['id']}").json()
    candidate = [m for m in final["messages"] if m["role"] == "candidate"]
    assert len(candidate) == 1  # answered once, not twice
