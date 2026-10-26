"""API tests for Conversation Sparring (Days 1-2).

In-process only: fastapi.testclient.TestClient makes no network calls.
No API key is needed (scripted character default); the tests ensure
META_MODEL_API_KEY is unset.
"""

import pytest
from fastapi.testclient import TestClient

from app.server import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def no_api_key(monkeypatch):
    monkeypatch.delenv("META_MODEL_API_KEY", raising=False)


def test_create_session():
    res = client.post("/sessions", json={})
    assert res.status_code == 200
    data = res.json()
    assert data["id"]
    assert data["scenario_id"]
    assert data["title"]
    assert data["character"]["name"]
    assert data["character"]["opening_line"]
    assert data["score"] == {"revealed": 0, "total": 7}
    assert data["revealed_titles"] == []
    assert data["turns"] == []


def test_message_round_trip_advances_score():
    session_id = client.post("/sessions", json={}).json()["id"]
    res = client.post(
        f"/sessions/{session_id}/messages",
        json={"text": "What's on your plate right now?"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["reply"]
    assert data["question_type"] in ("closed", "open", "meaning")
    assert data["score"]["total"] == 7
    assert data["score_display"] == f"{data['score']['revealed']}/7"
    assert data["newly_revealed"]

    state = client.get(f"/sessions/{session_id}").json()
    assert state["revealed_titles"] == data["newly_revealed"]
    assert len(state["turns"]) == 1
    assert state["turns"][0]["user_text"] == "What's on your plate right now?"


def test_get_session_returns_turns_and_decisions():
    session_id = client.post("/sessions", json={}).json()["id"]
    client.post(
        f"/sessions/{session_id}/messages",
        json={"text": "What's on your plate right now?"},
    )
    res = client.get(f"/sessions/{session_id}")
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == session_id
    assert len(data["turns"]) == 1
    assert data["decisions"]
    assert data["score"]["revealed"] >= 1
    assert data["score_display"] == f"{data['score']['revealed']}/7"


def test_unknown_session_404():
    assert client.get("/sessions/no-such-id").status_code == 404
    res = client.post(
        "/sessions/no-such-id/messages", json={"text": "Hello?"}
    )
    assert res.status_code == 404


def test_empty_text_422():
    session_id = client.post("/sessions", json={}).json()["id"]
    assert (
        client.post(f"/sessions/{session_id}/messages", json={}).status_code
        == 422
    )
    assert (
        client.post(
            f"/sessions/{session_id}/messages", json={"text": "   "}
        ).status_code
        == 422
    )


def test_index_serves_html_with_input():
    res = client.get("/")
    assert res.status_code == 200
    assert "text/html" in res.headers["content-type"]
    assert "<input" in res.text
