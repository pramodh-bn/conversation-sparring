"""Portrait tests (CS-7, stub-only).

Expression state is a pure function of score (thirds of progress).
The stub generator returns deterministic labeled-SVG bytes; nothing
here touches the network. No live calls.
"""

import base64
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient

from app.portrait import (
    EXPRESSIONS,
    StubPortraitClient,
    expression_for_score,
    portrait_payload,
)
from app.server import app

client = TestClient(app)

GOOD_RUN = [
    "Did you miss the deadline again?",
    "What's on your plate right now?",
    "How has this week actually been for you?",
    "What worries you most about falling behind?",
    "What are you afraid of here?",
    "What matters most to you in this job?",
    "What would it mean to you to get help re-prioritizing?",
]


@pytest.mark.parametrize(
    "revealed,expected",
    [
        (0, "guarded"),
        (1, "guarded"),
        (2, "guarded"),
        (3, "softening"),
        (4, "softening"),
        (5, "open"),
        (6, "open"),
        (7, "open"),
    ],
)
def test_expression_states_are_thirds_of_seven(revealed, expected):
    assert expression_for_score(revealed, 7) == expected


def test_expression_states_follow_declared_order():
    assert EXPRESSIONS == ("guarded", "softening", "open")


def test_expression_degenerate_inputs_stay_guarded():
    assert expression_for_score(0, 0) == "guarded"
    assert expression_for_score(-1, 7) == "guarded"


def test_stub_is_deterministic_per_expression():
    stub = StubPortraitClient()
    for expression in EXPRESSIONS:
        assert stub.portrait(expression) == stub.portrait(expression)


def test_stub_labels_expression_and_not_live():
    stub = StubPortraitClient()
    for expression in EXPRESSIONS:
        svg = stub.portrait(expression).decode("utf-8")
        assert expression in svg
        assert "STUB" in svg
        assert "not a live" in svg


def test_stub_rejects_unknown_expression():
    with pytest.raises(ValueError, match="unknown expression"):
        StubPortraitClient().portrait("smug")


def test_portrait_payload_shape():
    payload = portrait_payload(3, 7)
    assert payload["expression"] == "softening"
    assert payload["stub"] is True
    assert payload["image"].startswith("data:image/svg+xml;base64,")
    svg = base64.b64decode(payload["image"].split(",", 1)[1]).decode("utf-8")
    assert "<svg" in svg
    assert "softening" in svg


def test_portrait_endpoint_follows_score():
    session_id = client.post("/sessions", json={}).json()["id"]

    def portrait():
        res = client.get(f"/sessions/{session_id}/portrait")
        assert res.status_code == 200
        return res.json()

    assert portrait()["expression"] == "guarded"
    for question in GOOD_RUN[:3]:
        res = client.post(
            f"/sessions/{session_id}/messages", json={"text": question}
        )
        assert res.status_code == 200
    assert portrait()["expression"] == "softening"
    assert portrait()["stub"] is True
    for question in GOOD_RUN[3:]:
        res = client.post(
            f"/sessions/{session_id}/messages", json={"text": question}
        )
        assert res.status_code == 200
    assert portrait()["expression"] == "open"


def test_portrait_endpoint_unknown_session_404():
    res = client.get("/sessions/nope/portrait")
    assert res.status_code == 404


def test_index_contains_labeled_portrait_slot():
    html = client.get("/").text
    assert 'id="portrait-panel"' in html
    assert 'id="portrait"' in html
    assert "not a live" in html
