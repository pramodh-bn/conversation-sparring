"""Character tests for app.character.

- ScriptedCharacter voices newly revealed node text.
- ScriptedCharacter with nothing newly revealed deflects and leaks NONE
  of the scenario's node texts (probe across several turn_counts, since
  deflections rotate on turn_count).
- MetaSparkClient raises RuntimeError when META_MODEL_API_KEY is absent
  and does not crash at import. No network calls in any test: the
  no-key path raises before any HTTP request is made.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from app.character import CharacterAgent, MetaSparkClient, ScriptedCharacter


# A small fake scenario: distinct node texts so a leak of any one is
# detectable. These stand in for the teammate.json nodes.
NODES = [
    {
        "id": "n1",
        "title": "Workload",
        "text": "I've got three deadlines landing in the same week.",
    },
    {
        "id": "n2",
        "title": "Worry",
        "text": "Honestly I'm scared I'll let the whole team down.",
    },
    {
        "id": "n3",
        "title": "Value",
        "text": "Doing good work that people can rely on matters most to me.",
    },
]


def _session_view(revealed=None, turn_count=0):
    return {
        "character": {
            "name": "Alex",
            "role": "teammate",
            "persona": "A plain-spoken, tired teammate.",
            "opening_line": "Hey. Yeah, I'm here.",
        },
        "revealed": revealed if revealed is not None else [],
        "turn_count": turn_count,
    }


def test_scripted_character_is_a_character_agent():
    assert isinstance(ScriptedCharacter(), CharacterAgent)


def test_scripted_character_voices_newly_revealed_node_text():
    character = ScriptedCharacter()
    reply = character.respond(_session_view(turn_count=1), "What is going on?", [NODES[0]])
    assert NODES[0]["text"] in reply


def test_scripted_character_voices_each_newly_revealed_node():
    character = ScriptedCharacter()
    reply = character.respond(
        _session_view(turn_count=2), "How is it really going?", [NODES[0], NODES[1]]
    )
    assert NODES[0]["text"] in reply
    assert NODES[1]["text"] in reply


def test_scripted_character_deflects_with_nothing_new():
    character = ScriptedCharacter()
    reply = character.respond(_session_view(turn_count=0), "Tell me more.", [])
    assert reply.strip() != ""


def test_scripted_character_deflections_rotate():
    character = ScriptedCharacter()
    replies = {
        character.respond(_session_view(turn_count=t), "Tell me more.", [])
        for t in range(6)
    }
    # At least 3 distinct deflections across turn_counts.
    assert len(replies) >= 3


def test_scripted_character_never_leaks_unrevealed_node_text():
    # Probe: revealed=[] and newly_revealed=[] (the character receives
    # no node text at all), then check every node text against the
    # reply, across turn_counts covering the full deflection rotation.
    character = ScriptedCharacter()
    for turn_count in range(6):
        reply = character.respond(
            _session_view(revealed=[], turn_count=turn_count),
            "Tell me everything.",
            [],
        )
        for node in NODES:
            assert node["text"] not in reply


def test_metaspark_client_import_does_not_crash_without_key(monkeypatch):
    # Import already happened at module top with no key set in this
    # process; constructing must also not raise.
    monkeypatch.delenv("META_MODEL_API_KEY", raising=False)
    client = MetaSparkClient()
    assert client is not None


def test_metaspark_client_raises_without_key(monkeypatch):
    monkeypatch.delenv("META_MODEL_API_KEY", raising=False)
    client = MetaSparkClient()
    with pytest.raises(RuntimeError, match="META_MODEL_API_KEY"):
        # Raises before any HTTP request, so no network is touched.
        client.respond(_session_view(), "Hello?", [])


def test_metaspark_client_default_model(monkeypatch):
    monkeypatch.delenv("META_MODEL_API_KEY", raising=False)
    monkeypatch.delenv("META_MODEL_API_MODEL", raising=False)
    assert MetaSparkClient().model == "muse-spark-1.3"
