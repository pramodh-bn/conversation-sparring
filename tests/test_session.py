"""Session tests: the two proof numbers plus state-machine invariants.

Loads the real scenario via app.graph.load_scenario with a path
resolved relative to the project root (parent of this tests/ dir).

Proof numbers (frozen in the task):
- Closed-only script -> final score 2/7.
- Good-question script -> final score 7/7.

No network, no API keys, no LLM.
"""

from pathlib import Path

import pytest

from app.graph import load_scenario
from app.judge import score as judge_score
from app.session import Session

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCENARIO_PATH = PROJECT_ROOT / "scenarios" / "teammate.json"

CLOSED_ONLY_SCRIPT = [
    "Did you miss the deadline again?",
    "Is the report finished yet?",
    "You're behind, right?",
    "Did you tell your manager?",
    "Is it going to be late again?",
]

GOOD_SCRIPT = [
    "Did you miss the deadline again?",
    "What's on your plate right now?",
    "How has this week actually been for you?",
    "What worries you most about falling behind?",
    "What are you afraid of here?",
    "What matters most to you in this job?",
    "What would it mean to you to get help re-prioritizing?",
]


def _load_session():
    return Session(load_scenario(str(SCENARIO_PATH)))


def _run_script(script):
    session = _load_session()
    for text in script:
        session.add_turn(text)
    return session


def test_closed_only_script_scores_2_of_7():
    session = _run_script(CLOSED_ONLY_SCRIPT)
    assert session.score_count == 2
    assert session.score_total == 7
    assert session.score == pytest.approx(2 / 7)
    assert judge_score(session) == {
        "revealed": 2,
        "total": 7,
        "fraction": pytest.approx(2 / 7),
    }


def test_good_script_scores_7_of_7():
    session = _run_script(GOOD_SCRIPT)
    assert session.score_count == 7
    assert session.score_total == 7
    assert session.score == pytest.approx(1.0)


def test_turns_record_question_type_and_newly_revealed():
    session = _run_script(GOOD_SCRIPT)
    assert len(session.turns) == len(GOOD_SCRIPT)
    for turn, text in zip(session.turns, GOOD_SCRIPT):
        assert turn["user_text"] == text
        assert turn["question_type"] in ("closed", "open", "meaning")
        assert isinstance(turn["newly_revealed"], list)
        # Gate rule: at most one node revealed per turn.
        assert len(turn["newly_revealed"]) <= 1
    # The good script reveals exactly one node per turn.
    assert all(len(t["newly_revealed"]) == 1 for t in session.turns)


def test_exactly_four_decision_records_per_turn():
    session = _run_script(GOOD_SCRIPT)
    assert len(session.decisions) == 4 * len(GOOD_SCRIPT)
    for i, turn in enumerate(session.turns):
        records = session.decisions[4 * i: 4 * i + 4]
        assert [r["kind"] for r in records] == [
            "classify",
            "gate_check",
            "reveal",
            "score",
        ]
        assert all(r["turn_index"] == i for r in records)
        assert records[0]["input"] == turn["user_text"]
        assert records[0]["output"] == turn["question_type"]
        assert records[2]["output"] == turn["newly_revealed"]
        # The score record must reflect the cumulative revealed count
        # after this turn, not just the final total.
        expected_revealed = sum(
            len(t["newly_revealed"]) for t in session.turns[: i + 1]
        )
        assert records[3]["output"] == {
            "revealed": expected_revealed,
            "total": 7,
        }


def test_revealed_set_only_grows():
    session = _load_session()
    previous = set()
    for text in GOOD_SCRIPT:
        session.add_turn(text)
        assert previous <= session.revealed
        assert len(session.revealed) >= len(previous)
        previous = set(session.revealed)


def test_second_session_on_same_script_gives_same_score():
    first = _run_script(GOOD_SCRIPT)
    second = _run_script(GOOD_SCRIPT)
    assert first.score == second.score
    assert first.score_count == second.score_count
    assert first.revealed == second.revealed
    assert [t["question_type"] for t in first.turns] == [
        t["question_type"] for t in second.turns
    ]
    assert [t["newly_revealed"] for t in first.turns] == [
        t["newly_revealed"] for t in second.turns
    ]


def test_session_view_never_includes_unrevealed_node_text():
    session = _run_script(CLOSED_ONLY_SCRIPT)
    view = session.session_view()
    assert view["turn_count"] == len(CLOSED_ONLY_SCRIPT)
    assert view["character"] == session.scenario["character"]
    revealed_ids = {node["id"] for node in view["revealed"]}
    assert revealed_ids == session.revealed
    unrevealed = [
        node for node in session.scenario["nodes"]
        if node["id"] not in session.revealed
    ]
    assert unrevealed, "closed script must leave some nodes unrevealed"
    for node in unrevealed:
        assert node["text"] not in str(view["revealed"])
        assert node["id"] not in revealed_ids
