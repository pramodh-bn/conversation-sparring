"""Live wiring tests (CS-6).

The server uses the scripted character + RuleCoach by default and
switches to MetaSparkClient + SparkCoach only when BOTH
META_MODEL_API_KEY and META_MODEL_API_BASE are set. Partial config
stays on the scripted path. Every live-path test below uses mocked
OpenAI client (fake_openai in conftest.py). No live calls.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient

import app.server as server
from app.character import MetaSparkClient, ScriptedCharacter
from app.coach import RuleCoach, SparkCoach
from app.server import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_live_env(monkeypatch):
    monkeypatch.delenv("META_MODEL_API_KEY", raising=False)
    monkeypatch.delenv("META_MODEL_API_BASE", raising=False)
    monkeypatch.delenv("META_MODEL_API_MODEL", raising=False)


def test_default_character_and_coach_are_scripted():
    assert isinstance(server.get_character(), ScriptedCharacter)
    assert isinstance(server.get_coach(), RuleCoach)


def test_both_env_vars_select_live_client(monkeypatch):
    monkeypatch.setenv("META_MODEL_API_KEY", "test-key")
    monkeypatch.setenv("META_MODEL_API_BASE", "https://model.test")
    character = server.get_character()
    coach = server.get_coach()
    assert isinstance(character, MetaSparkClient)
    assert isinstance(coach, SparkCoach)
    assert character.base_url == "https://model.test"
    assert character.model == "muse-spark-1.3"


def test_model_env_override_reaches_live_client(monkeypatch):
    monkeypatch.setenv("META_MODEL_API_KEY", "test-key")
    monkeypatch.setenv("META_MODEL_API_BASE", "https://model.test")
    monkeypatch.setenv("META_MODEL_API_MODEL", "custom-model")
    assert server.get_character().model == "custom-model"


def test_key_without_base_stays_scripted(monkeypatch):
    monkeypatch.setenv("META_MODEL_API_KEY", "test-key")
    assert isinstance(server.get_character(), ScriptedCharacter)
    assert isinstance(server.get_coach(), RuleCoach)


def test_base_without_key_stays_scripted(monkeypatch):
    monkeypatch.setenv("META_MODEL_API_BASE", "https://model.test")
    assert isinstance(server.get_character(), ScriptedCharacter)
    assert isinstance(server.get_coach(), RuleCoach)


def test_live_character_reply_uses_mocked_model(monkeypatch, fake_openai):
    monkeypatch.setenv("META_MODEL_API_KEY", "test-key")
    monkeypatch.setenv("META_MODEL_API_BASE", "https://model.test")
    fake_openai.reply = "Mocked teammate voice."
    session_id = client.post("/sessions", json={}).json()["id"]
    res = client.post(
        f"/sessions/{session_id}/messages",
        json={"text": "What's on your plate right now?"},
    )
    assert res.status_code == 200
    assert res.json()["reply"] == "Mocked teammate voice."
    (init,) = fake_openai.clients
    (call,) = fake_openai.calls
    assert init["base_url"] == "https://model.test"
    assert init["api_key"] == "test-key"
    assert call["model"] == "muse-spark-1.3"
    assert call["messages"][0]["role"] == "system"
    assert call["messages"][1]["content"] == "What's on your plate right now?"


def test_live_coach_whisper_uses_mocked_model(monkeypatch, fake_openai):
    monkeypatch.setenv("META_MODEL_API_KEY", "test-key")
    monkeypatch.setenv("META_MODEL_API_BASE", "https://model.test")
    fake_openai.reply = "Mocked better question?"
    session_id = client.post("/sessions", json={}).json()["id"]
    # Same stalling sequence as test_session_stalled_turn_gets_whisper:
    # two reveals, then the third closed turn stalls -> live whisper.
    res = None
    for text in (
        "Did you miss the deadline again?",
        "Is the report finished yet?",
        "Is it going to be late again?",
    ):
        res = client.post(
            f"/sessions/{session_id}/messages", json={"text": text}
        )
    assert res.status_code == 200
    assert res.json()["newly_revealed"] == []
    assert res.json()["coach_whisper"] == "Mocked better question?"
