"""Coach tests for app.coach.

- RuleCoach (DEFAULT): silent on revealing turns; closed stalled turns
  get an open rewrite (spec examples pinned); open stalled turns get a
  meaning whisper from the fixed bank (rotation pinned); complete
  sessions stay silent; whispers never contain unrevealed node text.
- SparkCoach: inert without a key (RuntimeError, no network); with a
  mocked OpenAI client it returns the model's whisper. No live calls.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from app.coach import CoachAgent, RuleCoach, SparkCoach
from app.graph import load_scenario
from app.session import Session


# Distinct node texts so a leak of any one is detectable.
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


def _coach_view(
    user_text="Did you miss the deadline again?",
    question_type="closed",
    revealed_anything=False,
    revealed=0,
    total=7,
    revealed_titles=(),
):
    return {
        "user_text": user_text,
        "question_type": question_type,
        "revealed_anything": revealed_anything,
        "score": {"revealed": revealed, "total": total},
        "revealed_titles": list(revealed_titles),
    }


def test_rule_coach_is_a_coach_agent():
    assert isinstance(RuleCoach(), CoachAgent)


def test_rule_coach_silent_on_revealing_turn():
    coach = RuleCoach()
    assert (
        coach.suggest(
            _coach_view(
                user_text="What worries you most about falling behind?",
                question_type="meaning",
                revealed_anything=True,
                revealed=4,
                revealed_titles=["Behind on the report"],
            )
        )
        is None
    )


def test_rule_coach_silent_on_revealing_closed_turn():
    coach = RuleCoach()
    assert (
        coach.suggest(
            _coach_view(revealed_anything=True, revealed=1)
        )
        is None
    )


def test_rule_coach_closed_to_open_spec_examples():
    coach = RuleCoach()
    assert (
        coach.suggest(_coach_view("Did you miss the deadline again?"))
        == "What happened with the deadline?"
    )
    assert (
        coach.suggest(_coach_view("Is the report finished yet?"))
        == "What's going on with the report?"
    )


def test_rule_coach_closed_falls_back_when_no_template_matches():
    coach = RuleCoach()
    assert (
        coach.suggest(_coach_view("You're behind, right?"))
        == "What would you say is going on here?"
    )


def test_rule_coach_open_stalled_gets_meaning_whisper():
    coach = RuleCoach()
    assert (
        coach.suggest(
            _coach_view(
                user_text="What color is the status report?",
                question_type="open",
            )
        )
        == "How did that feel?"
    )


def test_rule_coach_meaning_bank_rotates_deterministically():
    coach = RuleCoach()
    view = _coach_view(
        user_text="What color is the status report?", question_type="open"
    )
    assert coach.suggest(dict(view)) == "How did that feel?"
    assert coach.suggest(dict(view)) == "What worries you most about this?"
    assert coach.suggest(dict(view)) == "What matters most to you here?"


def test_rule_coach_silent_when_session_complete():
    coach = RuleCoach()
    assert (
        coach.suggest(
            _coach_view(
                user_text="Anything else?",
                question_type="closed",
                revealed_anything=False,
                revealed=7,
            )
        )
        is None
    )


def test_rule_coach_whisper_never_contains_unrevealed_node_text():
    # Probe: stalled views across starters and types; the whisper must
    # never contain any scenario node text (titles or hidden text).
    coach = RuleCoach()
    stalled_texts = [
        ("Did you miss the deadline again?", "closed"),
        ("Is the report finished yet?", "closed"),
        ("You're behind, right?", "closed"),
        ("What color is the status report?", "open"),
        ("Why did the deadline slip?", "open"),
    ]
    for text, question_type in stalled_texts:
        whisper = coach.suggest(_coach_view(text, question_type))
        assert whisper, "stalled turn must produce a whisper"
        for node in NODES:
            assert node["text"] not in whisper
            assert node["title"] not in whisper


def test_spark_coach_is_a_coach_agent():
    assert isinstance(SparkCoach(), CoachAgent)


def test_spark_coach_silent_on_revealing_turn_without_key(monkeypatch):
    monkeypatch.delenv("META_MODEL_API_KEY", raising=False)
    coach = SparkCoach()
    assert coach.suggest(_coach_view(revealed_anything=True)) is None


def test_spark_coach_raises_without_key_before_network(monkeypatch):
    monkeypatch.delenv("META_MODEL_API_KEY", raising=False)
    coach = SparkCoach()
    with pytest.raises(RuntimeError, match="META_MODEL_API_KEY"):
        coach.suggest(_coach_view())


@pytest.mark.parametrize("revealed", [7, 8])
def test_spark_coach_silent_when_complete_without_calling_client(revealed):
    class UnexpectedClient:
        def respond(self, *args):
            pytest.fail("Completed sessions must not call the live model")

    coach = SparkCoach(client=UnexpectedClient())
    assert coach.suggest(_coach_view(revealed=revealed)) is None


def test_spark_coach_returns_model_whisper_with_mocked_client(
    monkeypatch, fake_openai
):
    monkeypatch.setenv("META_MODEL_API_KEY", "test-key")
    monkeypatch.setenv("META_MODEL_API_BASE", "https://model.test")
    fake_openai.reply = "Try asking how it felt."
    coach = SparkCoach()
    whisper = coach.suggest(_coach_view("Did you miss the deadline again?"))
    assert whisper == "Try asking how it felt."
    (init,) = fake_openai.clients
    assert init["base_url"] == "https://model.test"
    (call,) = fake_openai.calls
    # The coach prompt carries the stalled question for context.
    assert "Did you miss the deadline again?" in str(call["messages"])


# --- Wiring: Session consults the coach (CS-2) ---


def _wired_session():
    root = Path(__file__).resolve().parents[1]
    return Session(load_scenario(str(root / "scenarios" / "teammate.json")))


def test_session_stalled_turn_gets_whisper_and_fifth_record():
    session = _wired_session()
    coach = RuleCoach()
    session.add_turn("Did you miss the deadline again?", coach=coach)
    session.add_turn("Is the report finished yet?", coach=coach)
    turn = session.add_turn("Is it going to be late again?", coach=coach)
    assert turn["newly_revealed"] == []
    assert turn["coach_whisper"] == "What would you say is going on here?"
    records = [r for r in session.decisions if r["turn_index"] == 2]
    assert [r["kind"] for r in records] == [
        "classify",
        "gate_check",
        "reveal",
        "score",
        "coach_whisper",
    ]
    assert records[4]["input"] == 2
    assert records[4]["output"] == turn["coach_whisper"]


def test_session_revealing_turn_with_coach_stays_silent():
    session = _wired_session()
    turn = session.add_turn(
        "Did you miss the deadline again?", coach=RuleCoach()
    )
    assert turn["newly_revealed"] != []
    assert turn["coach_whisper"] is None
    records = [r for r in session.decisions if r["turn_index"] == 0]
    assert [r["kind"] for r in records] == [
        "classify",
        "gate_check",
        "reveal",
        "score",
    ]


def test_session_open_stalled_turn_gets_meaning_whisper():
    session = _wired_session()
    coach = RuleCoach()
    session.add_turn("Did you miss the deadline again?", coach=coach)
    session.add_turn("Is the report finished yet?", coach=coach)
    session.add_turn("What's on your plate right now?", coach=coach)
    session.add_turn(
        "How has this week actually been for you?", coach=coach
    )
    turn = session.add_turn(
        "What color is the status report?", coach=coach
    )
    assert turn["newly_revealed"] == []
    assert turn["coach_whisper"] == "How did that feel?"
