"""Branch/rewind tests for app.session (CS-3).

- Branch "main" preserves Day 1/2 behavior (proof numbers unchanged).
- Fork from turn N keeps turns [0..N-1]; revealed recomputed as the
  union of newly_revealed across copied turns; decisions copied for
  those turns only.
- Branches score independently; the source branch is unchanged by a
  fork and by later turns on the new branch.
- Labels: "Main", "Branch B (from turn N)". Ids: main, B, C, ...

No network, no API keys, no LLM.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from app.graph import load_scenario
from app.session import Session

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCENARIO_PATH = PROJECT_ROOT / "scenarios" / "teammate.json"

# Same frozen scripts as test_session.py (duplicated like demo_run.py).
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

OPEN_RUN = [
    "What's on your plate right now?",
    "How has this week actually been for you?",
    "What worries you most about falling behind?",
    "What are you afraid of here?",
    "What matters most to you in this job?",
    "What would it mean to you to get help re-prioritizing?",
]


def _load_session():
    return Session(load_scenario(str(SCENARIO_PATH)))


def test_main_branch_preserves_day_1_2_proof_numbers():
    closed = _load_session()
    for text in CLOSED_ONLY_SCRIPT:
        closed.add_turn(text)
    assert closed.active_branch_id == "main"
    assert closed.score_count == 2
    assert closed.score_total == 7

    good = _load_session()
    for text in GOOD_SCRIPT:
        good.add_turn(text)
    assert good.score_count == 7


def test_fresh_session_has_only_main_branch():
    session = _load_session()
    assert session.active_branch_id == "main"
    assert list(session.branches) == ["main"]
    main = session.branches["main"]
    assert main.parent_branch_id is None
    assert main.fork_turn_index == 0
    assert main.label == "Main"


def test_fork_keeps_turns_0_to_n_minus_1():
    session = _load_session()
    for text in CLOSED_ONLY_SCRIPT:
        session.add_turn(text)
    before = list(session.branches["main"].turns)

    branch_id = session.create_branch(from_turn=3)
    assert branch_id == "B"
    assert session.active_branch_id == "B"
    branch = session.branches["B"]
    assert branch.parent_branch_id == "main"
    assert branch.fork_turn_index == 3
    assert branch.label == "Branch B (from turn 3)"
    assert branch.turns == before[0:3]
    # Revealed recomputed as the union of newly_revealed on copied turns.
    expected = set()
    for turn in before[0:3]:
        expected.update(turn["newly_revealed"])
    assert branch.revealed == expected
    # Decisions copied for turns [0..2] only.
    assert {r["turn_index"] for r in branch.decisions} == {0, 1, 2}
    assert len(branch.decisions) == len(
        [r for r in session.branches["main"].decisions if r["turn_index"] < 3]
    )


def test_fork_does_not_change_source_branch():
    session = _load_session()
    for text in CLOSED_ONLY_SCRIPT:
        session.add_turn(text)
    main_turns = list(session.branches["main"].turns)
    main_revealed = set(session.branches["main"].revealed)
    main_score = session.branches["main"].score_count

    session.create_branch(from_turn=2)
    assert session.branches["main"].turns == main_turns
    assert session.branches["main"].revealed == main_revealed
    assert session.branches["main"].score_count == main_score
    assert main_score == 2


def test_branches_score_independently():
    session = _load_session()
    for text in CLOSED_ONLY_SCRIPT:
        session.add_turn(text)
    assert session.branches["main"].score_count == 2

    session.create_branch(from_turn=2)
    for text in OPEN_RUN:
        session.add_turn(text)
    assert session.branches["B"].score_count >= 6
    # The original branch is untouched by the new branch's turns.
    assert session.branches["main"].score_count == 2
    assert len(session.branches["main"].turns) == len(CLOSED_ONLY_SCRIPT)


def test_fork_from_turn_zero_gives_empty_branch():
    session = _load_session()
    for text in CLOSED_ONLY_SCRIPT:
        session.add_turn(text)
    session.create_branch(from_turn=0)
    branch = session.branches["B"]
    assert branch.turns == []
    assert branch.revealed == set()
    assert branch.decisions == []
    assert branch.score_count == 0


def test_fork_from_end_copies_everything():
    session = _load_session()
    for text in CLOSED_ONLY_SCRIPT:
        session.add_turn(text)
    session.create_branch(from_turn=len(CLOSED_ONLY_SCRIPT))
    branch = session.branches["B"]
    main = session.branches["main"]
    assert branch.turns == main.turns
    assert branch.revealed == main.revealed
    assert branch.score_count == main.score_count


def test_fork_rejects_out_of_range_turn():
    session = _load_session()
    session.add_turn("Did you miss the deadline again?")
    with pytest.raises(ValueError):
        session.create_branch(from_turn=2)
    with pytest.raises(ValueError):
        session.create_branch(from_turn=-1)


def test_unknown_branch_references_raise_key_error():
    session = _load_session()
    with pytest.raises(KeyError):
        session.set_active_branch("zzz")
    with pytest.raises(KeyError):
        session.create_branch(from_turn=0, from_branch_id="zzz")


def test_branch_ids_sequence_and_labels():
    session = _load_session()
    assert session.create_branch(from_turn=0) == "B"
    session.set_active_branch("main")
    assert session.create_branch(from_turn=0) == "C"
    assert session.branches["C"].label == "Branch C (from turn 0)"
    assert session.branches["C"].parent_branch_id == "main"


def test_switching_active_branch_changes_session_view():
    session = _load_session()
    for text in CLOSED_ONLY_SCRIPT:
        session.add_turn(text)
    session.create_branch(from_turn=2)
    for text in OPEN_RUN:
        session.add_turn(text)
    assert session.score_count >= 6
    session.set_active_branch("main")
    assert session.score_count == 2
    assert len(session.turns) == len(CLOSED_ONLY_SCRIPT)
