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


def test_message_response_carries_coach_whisper_on_stalled_turn():
    session_id = client.post("/sessions", json={}).json()["id"]
    client.post(
        f"/sessions/{session_id}/messages",
        json={"text": "Did you miss the deadline again?"},
    )
    client.post(
        f"/sessions/{session_id}/messages",
        json={"text": "Is the report finished yet?"},
    )
    res = client.post(
        f"/sessions/{session_id}/messages",
        json={"text": "Is it going to be late again?"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["newly_revealed"] == []
    assert data["coach_whisper"] == "What would you say is going on here?"


def test_message_response_whisper_null_on_revealing_turn():
    session_id = client.post("/sessions", json={}).json()["id"]
    res = client.post(
        f"/sessions/{session_id}/messages",
        json={"text": "Did you miss the deadline again?"},
    )
    assert res.status_code == 200
    assert res.json()["coach_whisper"] is None


def test_coach_meaning_rotation_is_per_session():
    # CS-C43: rotation must not leak across sessions. Two fresh
    # sessions asking the same stalling sequence must open with
    # identical meaning whispers.
    setup = [
        "Did you miss the deadline again?",
        "Is the report finished yet?",
        "What's on your plate right now?",
        "How has this week actually been for you?",
    ]
    final = "What color is the status report?"
    whispers = []
    for _ in range(2):
        session_id = client.post("/sessions", json={}).json()["id"]
        for text in setup:
            res = client.post(
                f"/sessions/{session_id}/messages", json={"text": text}
            )
            assert res.status_code == 200
        res = client.post(
            f"/sessions/{session_id}/messages", json={"text": final}
        )
        assert res.status_code == 200
        data = res.json()
        assert data["question_type"] == "open"
        assert data["newly_revealed"] == []
        whispers.append(data["coach_whisper"])
    assert whispers == ["How did that feel?", "How did that feel?"]


def _run_closed_script(session_id, count=5):
    for text in [
        "Did you miss the deadline again?",
        "Is the report finished yet?",
        "You're behind, right?",
        "Did you tell your manager?",
        "Is it going to be late again?",
    ][:count]:
        client.post(f"/sessions/{session_id}/messages", json={"text": text})


def test_create_branch_endpoint_forks_and_activates():
    session_id = client.post("/sessions", json={}).json()["id"]
    _run_closed_script(session_id)
    res = client.post(
        f"/sessions/{session_id}/branches", json={"from_turn": 2}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["branch"]["id"] == "B"
    assert data["branch"]["turn_count"] == 2
    assert data["active_branch_id"] == "B"
    # The original branch score is unchanged after the fork.
    tree = client.get(f"/sessions/{session_id}/branches").json()
    main = next(b for b in tree["branches"] if b["id"] == "main")
    assert main["score"] == {"revealed": 2, "total": 7}


def test_branch_listing_tree_shape():
    session_id = client.post("/sessions", json={}).json()["id"]
    _run_closed_script(session_id, count=3)
    client.post(f"/sessions/{session_id}/branches", json={"from_turn": 2})
    res = client.get(f"/sessions/{session_id}/branches")
    assert res.status_code == 200
    data = res.json()
    assert data["active_branch_id"] == "B"
    by_id = {b["id"]: b for b in data["branches"]}
    assert by_id["main"]["label"] == "Main"
    assert by_id["main"]["turn_count"] == 3
    assert by_id["B"]["parent_branch_id"] == "main"
    assert by_id["B"]["fork_turn_index"] == 2
    assert by_id["B"]["turn_count"] == 2


def test_branch_switching_via_messages_branch_id():
    session_id = client.post("/sessions", json={}).json()["id"]
    _run_closed_script(session_id)
    client.post(f"/sessions/{session_id}/branches", json={"from_turn": 2})
    res = client.post(
        f"/sessions/{session_id}/messages",
        json={"text": "What's on your plate right now?", "branch_id": "main"},
    )
    assert res.status_code == 200
    assert res.json()["branch_id"] == "main"
    tree = client.get(f"/sessions/{session_id}/branches").json()
    assert tree["active_branch_id"] == "main"
    main = next(b for b in tree["branches"] if b["id"] == "main")
    assert main["turn_count"] == 6


def test_message_response_carries_branch_id():
    session_id = client.post("/sessions", json={}).json()["id"]
    res = client.post(
        f"/sessions/{session_id}/messages",
        json={"text": "Did you miss the deadline again?"},
    )
    assert res.json()["branch_id"] == "main"


def test_unknown_branch_id_404():
    session_id = client.post("/sessions", json={}).json()["id"]
    assert (
        client.post(
            f"/sessions/{session_id}/messages",
            json={"text": "Hello?", "branch_id": "zzz"},
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"/sessions/{session_id}/branches",
            json={"from_turn": 0, "from_branch_id": "zzz"},
        ).status_code
        == 404
    )


def test_bad_from_turn_422():
    session_id = client.post("/sessions", json={}).json()["id"]
    _run_closed_script(session_id, count=1)
    assert (
        client.post(
            f"/sessions/{session_id}/branches", json={"from_turn": 99}
        ).status_code
        == 422
    )


def test_get_session_gains_branches_summary():
    session_id = client.post("/sessions", json={}).json()["id"]
    _run_closed_script(session_id, count=2)
    client.post(f"/sessions/{session_id}/branches", json={"from_turn": 1})
    data = client.get(f"/sessions/{session_id}").json()
    assert data["active_branch_id"] == "B"
    assert {b["id"] for b in data["branches"]} == {"main", "B"}
