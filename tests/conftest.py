"""Shared test fixtures.

``fake_openai`` replaces the ``OpenAI`` class that ``app.character``
uses for live model calls (``MetaSparkClient``, and ``BasetenClient``
through inheritance) with a recorder. No test makes a network call.
"""

from types import SimpleNamespace

import pytest


class OpenAIRecorder:
    """What the fake saw: one entry per constructed client and per call."""

    def __init__(self):
        self.reply = "mocked model reply"
        self.clients = []  # kwargs passed to OpenAI(...)
        self.calls = []  # kwargs passed to chat.completions.create(...)


@pytest.fixture
def fake_openai(monkeypatch):
    recorder = OpenAIRecorder()

    class FakeOpenAI:
        def __init__(self, **kwargs):
            recorder.clients.append(kwargs)
            self.chat = SimpleNamespace(
                completions=SimpleNamespace(create=self._create)
            )

        def _create(self, **kwargs):
            recorder.calls.append(kwargs)
            message = SimpleNamespace(content=recorder.reply)
            return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    monkeypatch.setattr("app.character.OpenAI", FakeOpenAI)
    return recorder
