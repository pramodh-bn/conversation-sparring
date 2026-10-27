"""Tests for the Baseten backend (CS-10, on the openai library per CS-11).

The OpenAI client is mocked (see ``fake_openai`` in conftest.py): no
live calls, and no real key anywhere in this file."""

import pytest

from app.baseten import DEFAULT_BASE_URL, DEFAULT_MODEL, BasetenClient
from app.coach import SparkCoach

FAKE_KEY = "test-key-not-real"
VIEW = {"character": {"persona": "You are Alex."}, "revealed": [], "turn_count": 0}


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for name in (
        "BASETEN_API_KEY",
        "BASETEN_API_BASE",
        "BASETEN_MODEL",
        "META_MODEL_API_KEY",
        "META_MODEL_API_BASE",
    ):
        monkeypatch.delenv(name, raising=False)


def test_defaults_match_hackathon_config():
    client = BasetenClient()
    assert client.base_url == "https://inference.baseten.co/v1" == DEFAULT_BASE_URL
    assert client.model == "meta-models/muse-spark-open-1026" == DEFAULT_MODEL


def test_inert_without_key_makes_no_request(fake_openai):
    with pytest.raises(RuntimeError, match="BASETEN_API_KEY"):
        BasetenClient().respond(VIEW, "hello", [])
    assert fake_openai.clients == []
    assert fake_openai.calls == []


def test_never_falls_back_to_meta_key(monkeypatch, fake_openai):
    monkeypatch.setenv("META_MODEL_API_KEY", "meta-key-not-real")
    monkeypatch.setenv("META_MODEL_API_BASE", "https://meta.example/v1")
    client = BasetenClient()
    assert client.api_key == ""
    with pytest.raises(RuntimeError):
        client.respond(VIEW, "hello", [])
    assert fake_openai.clients == []
    assert fake_openai.calls == []


def test_request_shape(monkeypatch, fake_openai):
    monkeypatch.setenv("BASETEN_API_KEY", FAKE_KEY)
    fake_openai.reply = "hi there"
    assert BasetenClient().respond(VIEW, "hello", []) == "hi there"
    (init,) = fake_openai.clients
    assert init["base_url"] == "https://inference.baseten.co/v1"
    assert init["api_key"] == FAKE_KEY
    (call,) = fake_openai.calls
    assert call["model"] == "meta-models/muse-spark-open-1026"
    assert call["messages"] == [
        {"role": "system", "content": "You are Alex."},
        {"role": "user", "content": "hello"},
    ]


def test_env_overrides(monkeypatch, fake_openai):
    monkeypatch.setenv("BASETEN_API_KEY", FAKE_KEY)
    monkeypatch.setenv("BASETEN_API_BASE", "https://other.example/v1/")
    monkeypatch.setenv("BASETEN_MODEL", "some/other-model")
    BasetenClient().respond(VIEW, "hello", [])
    (init,) = fake_openai.clients
    (call,) = fake_openai.calls
    assert init["base_url"] == "https://other.example/v1/"
    assert call["model"] == "some/other-model"


def test_coach_can_use_baseten_client(monkeypatch, fake_openai):
    monkeypatch.setenv("BASETEN_API_KEY", FAKE_KEY)
    fake_openai.reply = "hi there"
    coach = SparkCoach(client=BasetenClient())
    tip = coach.suggest(
        {"user_text": "Did you finish?", "revealed_anything": False,
         "score": {"revealed": 1, "total": 7}}
    )
    assert tip == "hi there"
    assert fake_openai.clients[0]["base_url"] == "https://inference.baseten.co/v1"


def test_coach_inert_without_key(fake_openai):
    with pytest.raises(RuntimeError, match="BASETEN_API_KEY"):
        SparkCoach(client=BasetenClient()).suggest(
            {"user_text": "Did you finish?", "revealed_anything": False,
             "score": {"revealed": 1, "total": 7}}
        )
    assert fake_openai.calls == []
