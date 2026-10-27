"""openai-library client tests (CS-11).

MetaSparkClient and BasetenClient both call the model through the
``openai`` package. Everything here is mocked: ``fake_openai`` replaces
the client class, and the transport test below feeds the real library a
mocked HTTP transport. No live calls, no real key.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx
import openai
import pytest

from app.baseten import BasetenClient
from app.character import MetaSparkClient

KEY_VARS = (
    "META_MODEL_API_KEY",
    "META_MODEL_API_BASE",
    "META_MODEL_API_MODEL",
    "BASETEN_API_KEY",
    "BASETEN_API_BASE",
    "BASETEN_MODEL",
    "OPENAI_API_KEY",
    "OPENAI_BASE_URL",
)
VIEW = {"character": {"persona": "You are Alex."}, "revealed": [], "turn_count": 0}


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for name in KEY_VARS:
        monkeypatch.delenv(name, raising=False)


# --- MetaSparkClient on the openai library ---


def test_meta_request_shape(monkeypatch, fake_openai):
    monkeypatch.setenv("META_MODEL_API_KEY", "meta-test-key")
    monkeypatch.setenv("META_MODEL_API_BASE", "https://meta.test/v1")
    fake_openai.reply = "hello back"
    assert MetaSparkClient().respond(VIEW, "hello", []) == "hello back"
    (init,) = fake_openai.clients
    assert init["base_url"] == "https://meta.test/v1"
    assert init["api_key"] == "meta-test-key"
    assert init["max_retries"] == 0
    (call,) = fake_openai.calls
    assert call["model"] == "muse-spark-1.3"
    assert call["timeout"] == 30.0
    assert call["messages"] == [
        {"role": "system", "content": "You are Alex."},
        {"role": "user", "content": "hello"},
    ]


def test_meta_env_overrides(monkeypatch, fake_openai):
    monkeypatch.setenv("META_MODEL_API_KEY", "meta-test-key")
    monkeypatch.setenv("META_MODEL_API_BASE", "https://other.test/v1/")
    monkeypatch.setenv("META_MODEL_API_MODEL", "some-other-model")
    MetaSparkClient().respond(VIEW, "hello", [])
    assert fake_openai.clients[0]["base_url"] == "https://other.test/v1/"
    assert fake_openai.calls[0]["model"] == "some-other-model"


def test_meta_inert_without_key_or_base_builds_no_client(monkeypatch, fake_openai):
    with pytest.raises(RuntimeError, match="META_MODEL_API_KEY"):
        MetaSparkClient().respond(VIEW, "hello", [])
    monkeypatch.setenv("META_MODEL_API_KEY", "meta-test-key")
    with pytest.raises(RuntimeError, match="META_MODEL_API_BASE"):
        MetaSparkClient().respond(VIEW, "hello", [])
    assert fake_openai.clients == []
    assert fake_openai.calls == []


# --- No cross-backend key fallback, and no OPENAI_* leakage ---


def test_meta_never_falls_back_to_baseten_key(monkeypatch, fake_openai):
    monkeypatch.setenv("BASETEN_API_KEY", "baseten-test-key")
    monkeypatch.setenv("META_MODEL_API_BASE", "https://meta.test/v1")
    client = MetaSparkClient()
    assert client.api_key is None
    with pytest.raises(RuntimeError, match="META_MODEL_API_KEY"):
        client.respond(VIEW, "hello", [])
    assert fake_openai.clients == []


def test_baseten_never_falls_back_to_meta_key(monkeypatch, fake_openai):
    monkeypatch.setenv("META_MODEL_API_KEY", "meta-test-key")
    monkeypatch.setenv("META_MODEL_API_BASE", "https://meta.test/v1")
    with pytest.raises(RuntimeError, match="BASETEN_API_KEY"):
        BasetenClient().respond(VIEW, "hello", [])
    assert fake_openai.clients == []


def test_each_backend_uses_only_its_own_key(monkeypatch, fake_openai):
    monkeypatch.setenv("META_MODEL_API_KEY", "meta-test-key")
    monkeypatch.setenv("META_MODEL_API_BASE", "https://meta.test/v1")
    monkeypatch.setenv("BASETEN_API_KEY", "baseten-test-key")
    MetaSparkClient().respond(VIEW, "hi", [])
    BasetenClient().respond(VIEW, "hi", [])
    meta_init, baseten_init = fake_openai.clients
    assert meta_init["api_key"] == "meta-test-key"
    assert meta_init["base_url"] == "https://meta.test/v1"
    assert baseten_init["api_key"] == "baseten-test-key"
    assert baseten_init["base_url"] == "https://inference.baseten.co/v1"


def test_openai_env_vars_are_never_used(monkeypatch, fake_openai):
    """The library's own OPENAI_API_KEY / OPENAI_BASE_URL fallbacks must
    not be able to stand in for a missing key or base URL."""
    monkeypatch.setenv("OPENAI_API_KEY", "openai-test-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://openai.test/v1")
    for client in (MetaSparkClient(), BasetenClient()):
        with pytest.raises(RuntimeError):
            client.respond(VIEW, "hello", [])
    assert fake_openai.clients == []


# --- The real openai library over a mocked HTTP transport (no network) ---


@pytest.mark.parametrize(
    "client_factory, env, expected_url, expected_model, expected_key",
    [
        (
            MetaSparkClient,
            {
                "META_MODEL_API_KEY": "meta-test-key",
                "META_MODEL_API_BASE": "https://meta.test/v1/",
            },
            "https://meta.test/v1/chat/completions",
            "muse-spark-1.3",
            "meta-test-key",
        ),
        (
            BasetenClient,
            {"BASETEN_API_KEY": "baseten-test-key"},
            "https://inference.baseten.co/v1/chat/completions",
            "meta-models/muse-spark-open-1026",
            "baseten-test-key",
        ),
    ],
)
def test_real_library_sends_expected_http_request(
    monkeypatch, client_factory, env, expected_url, expected_model, expected_key
):
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(
            200,
            json={
                "id": "x",
                "object": "chat.completion",
                "created": 0,
                "model": expected_model,
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {
                            "role": "assistant",
                            "content": "pong",
                            # Baseten returns reasoning separately.
                            "reasoning_content": "thinking",
                        },
                    }
                ],
            },
        )

    real_openai = openai.OpenAI

    def openai_with_mock_transport(**kwargs):
        return real_openai(
            http_client=httpx.Client(transport=httpx.MockTransport(handler)),
            **kwargs,
        )

    monkeypatch.setattr("app.character.OpenAI", openai_with_mock_transport)
    assert client_factory().respond(VIEW, "ping", []) == "pong"
    (request,) = seen
    assert str(request.url) == expected_url
    assert request.method == "POST"
    assert request.headers["authorization"] == f"Bearer {expected_key}"
    body = request.read().decode()
    assert expected_model in body
    assert "You are Alex." in body and "ping" in body
