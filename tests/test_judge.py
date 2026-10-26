"""Judge tests: determinism and score math.

The judge is pure and deterministic and does not import app.session,
so these tests use a small fake session object (plus a scenario-dict
variant) and need no classifier, graph file, network, or API key.
"""

import pytest

from app.judge import score


class FakeSession:
    """Minimal session-like object: .revealed + .scenario."""

    def __init__(self, revealed_ids, total=7):
        self.revealed = set(revealed_ids)
        self.scenario = {"nodes": [{"id": f"node-{i}"} for i in range(total)]}


class FakeSessionWithScoreTotal:
    """Session-like object exposing .score_total instead of .scenario."""

    def __init__(self, revealed_ids, total=7):
        self.revealed = set(revealed_ids)
        self.score_total = total


def test_score_math_partial():
    session = FakeSession({"a", "b", "c"})
    assert score(session) == {
        "revealed": 3,
        "total": 7,
        "fraction": pytest.approx(3 / 7),
    }


def test_score_math_zero_of_seven():
    assert score(FakeSession(set())) == {
        "revealed": 0,
        "total": 7,
        "fraction": 0.0,
    }


def test_score_math_seven_of_seven():
    revealed = {f"node-{i}" for i in range(7)}
    assert score(FakeSession(revealed)) == {
        "revealed": 7,
        "total": 7,
        "fraction": 1.0,
    }


def test_score_uses_score_total_when_present():
    session = FakeSessionWithScoreTotal({"a", "b"}, total=7)
    assert score(session) == {
        "revealed": 2,
        "total": 7,
        "fraction": pytest.approx(2 / 7),
    }


def test_judge_determinism_same_session_twice():
    session = FakeSession({"a", "b", "c", "d"})
    first = score(session)
    second = score(session)
    assert first == second
    assert first == {
        "revealed": 4,
        "total": 7,
        "fraction": pytest.approx(4 / 7),
    }


def test_judge_does_not_mutate_session():
    session = FakeSession({"a", "b"})
    before = set(session.revealed)
    score(session)
    assert session.revealed == before
