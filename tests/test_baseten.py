"""Tests for the Baseten backend (CS-10). Mocked HTTP only: no live
calls, and no real key anywhere in this file."""

import httpx
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


def _mock_post(monkeypatch, calls):
    def fake_post(url, **kwargs):
        calls.append((url, kwargs))
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "hi there"}}]},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx, "post", fake_post)


def test_defaults_match_hackathon_config():
    client = BasetenClient()
    assert client.base_url == "https://inference.baseten.co/v1" == DEFAULT_BASE_URL
    assert client.model == "meta-models/muse-spark-open-1026" == DEFAULT_MODEL


def test_inert_without_key_makes_no_request(monkeypatch):
    calls = []
    _mock_post(monkeypatch, calls)
    with pytest.raises(RuntimeError, match="BASETEN_API_KEY"):
        BasetenClient().respond(VIEW, "hello", [])
    assert calls == []


def test_never_falls_back_to_meta_key(monkeypatch):
    monkeypatch.setenv("META_MODEL_API_KEY", "meta-key-not-real")
    monkeypatch.setenv("META_MODEL_API_BASE", "https://meta.example/v1")
    calls = []
    _mock_post(monkeypatch, calls)
    client = BasetenClient()
    assert client.api_key == ""
    with pytest.raises(RuntimeError):
        client.respond(VIEW, "hello", [])
    assert calls == []


def test_request_shape(monkeypatch):
    monkeypatch.setenv("BASETEN_API_KEY", FAKE_KEY)
    calls = []
    _mock_post(monkeypatch, calls)
    assert BasetenClient().respond(VIEW, "hello", []) == "hi there"
    (url, kwargs), = calls
    assert url == "https://inference.baseten.co/v1/chat/completions"
    assert kwargs["json"]["model"] == "meta-models/muse-spark-open-1026"
    assert kwargs["json"]["messages"] == [
        {"role": "system", "content": "You are Alex."},
        {"role": "user", "content": "hello"},
    ]
    assert kwargs["headers"] == {"Authorization": f"Bearer {FAKE_KEY}"}


def test_env_overrides(monkeypatch):
    monkeypatch.setenv("BASETEN_API_KEY", FAKE_KEY)
    monkeypatch.setenv("BASETEN_API_BASE", "https://other.example/v1/")
    monkeypatch.setenv("BASETEN_MODEL", "some/other-model")
    calls = []
    _mock_post(monkeypatch, calls)
    BasetenClient().respond(VIEW, "hello", [])
    (url, kwargs), = calls
    assert url == "https://other.example/v1/chat/completions"
    assert kwargs["json"]["model"] == "some/other-model"


def test_coach_can_use_baseten_client(monkeypatch):
    monkeypatch.setenv("BASETEN_API_KEY", FAKE_KEY)
    calls = []
    _mock_post(monkeypatch, calls)
    coach = SparkCoach(client=BasetenClient())
    tip = coach.suggest(
        {"user_text": "Did you finish?", "revealed_anything": False,
         "score": {"revealed": 1, "total": 7}}
    )
    assert tip == "hi there"
    assert calls[0][0].startswith("https://inference.baseten.co/v1")


def test_coach_inert_without_key():
    with pytest.raises(RuntimeError, match="BASETEN_API_KEY"):
        SparkCoach(client=BasetenClient()).suggest(
            {"user_text": "Did you finish?", "revealed_anything": False,
             "score": {"revealed": 1, "total": 7}}
        )
