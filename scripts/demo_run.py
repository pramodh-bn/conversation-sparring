"""Scripted demo for Conversation Sparring (Days 1-4).

Runs three conversations against the scripted character (no API key):
a closed-question-only run (expected to score low) and a good-question
run (expected to score high). Prints every turn plus a final score
line per run, then asserts closed <= 3, good >= 6, and the rewind
proofs (bad branch 2/7 with a whisper, new branch >= 6/7, main still 2/7).

Runnable from the project root AND from anywhere:
    python scripts/demo_run.py
"""

import sys
from pathlib import Path

# Prepend the project root (parent of scripts/) so `from app...`
# imports work regardless of the current working directory.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.character import ScriptedCharacter  # noqa: E402
from app.coach import RuleCoach  # noqa: E402
from app.graph import load_scenario  # noqa: E402
from app.session import Session  # noqa: E402

CLOSED_ONLY = [
    "Did you miss the deadline again?",
    "Is the report finished yet?",
    "You're behind, right?",
    "Did you tell your manager?",
    "Is it going to be late again?",
]

GOOD_RUN = [
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


def run_conversation(label, questions, scenario):
    """Run one scripted conversation; return (score_count, score_total)."""
    print(f"=== {label} ===")
    session = Session(scenario)
    character = ScriptedCharacter()
    nodes_by_id = {node["id"]: node for node in scenario["nodes"]}
    for question in questions:
        turn = session.add_turn(question)
        # Build newly-revealed node dicts from the scenario nodes
        # matching the turn's ids; never pass unrevealed text.
        newly_revealed = [
            nodes_by_id[node_id]
            for node_id in turn["newly_revealed"]
            if node_id in nodes_by_id
        ]
        reply = character.respond(session.session_view(), question, newly_revealed)
        titles = [node["title"] for node in newly_revealed]
        print(f"Q: {question}")
        print(f"  type: {turn['question_type']}")
        print(f"  newly revealed: {titles}")
        print(f"  score: {session.score_count}/{session.score_total}")
        print(f"  reply: {reply}")
    print(f"FINAL SCORE ({label}): {session.score_count}/{session.score_total}")
    print()
    return session.score_count, session.score_total


def _play_turn(session, coach, character, nodes_by_id, question):
    """Play one turn on the active branch; print it; return the turn."""
    turn = session.add_turn(question, coach=coach)
    newly_revealed = [
        nodes_by_id[node_id]
        for node_id in turn["newly_revealed"]
        if node_id in nodes_by_id
    ]
    reply = character.respond(session.session_view(), question, newly_revealed)
    titles = [node["title"] for node in newly_revealed]
    print(f"Q: {question}")
    print(f"  type: {turn['question_type']}")
    print(f"  newly revealed: {titles}")
    print(f"  score: {session.score_count}/{session.score_total}")
    if turn["coach_whisper"]:
        print(f"  whisper: {turn['coach_whisper']}")
    print(f"  reply: {reply}")
    return turn


def run_rewind_demo(scenario):
    """Bad branch stalls, coach whispers, rewind forks a good branch.

    Returns (main_score, new_branch_score, whisper_seen).
    """
    print("=== rewind run (main branch goes bad) ===")
    session = Session(scenario)
    coach = RuleCoach()
    character = ScriptedCharacter()
    nodes_by_id = {node["id"]: node for node in scenario["nodes"]}
    for question in CLOSED_ONLY:
        _play_turn(session, coach, character, nodes_by_id, question)
    print(f"FINAL SCORE (main, bad branch): {session.score_count}/{session.score_total}")

    stalled = [
        turn for turn in session.branches["main"].turns
        if not turn["newly_revealed"]
    ]
    whisper_seen = any(turn["coach_whisper"] for turn in stalled)
    print(f"whisper on stalled turn: {whisper_seen}")

    print("--- rewind to turn 2, ask good questions on branch B ---")
    session.create_branch(from_turn=2)
    for question in OPEN_RUN:
        _play_turn(session, coach, character, nodes_by_id, question)
    new_branch_score = session.score_count
    main_score = session.branches["main"].score_count
    print(f"FINAL SCORE (branch B): {new_branch_score}/{session.score_total}")
    print(f"FINAL SCORE (main, unchanged): {main_score}/{session.score_total}")
    print()
    return (main_score, new_branch_score, whisper_seen)


def main():
    scenario = load_scenario(PROJECT_ROOT / "scenarios" / "teammate.json")
    closed_count, _ = run_conversation("closed-only run", CLOSED_ONLY, scenario)
    good_count, _ = run_conversation("good run", GOOD_RUN, scenario)
    main_kept, new_branch, whisper_seen = run_rewind_demo(scenario)

    failures = []
    if closed_count > 3:
        failures.append(
            f"closed-only run scored {closed_count}/7, expected <= 3"
        )
    if good_count < 6:
        failures.append(f"good run scored {good_count}/7, expected >= 6")
    if main_kept != 2:
        failures.append(
            f"rewind run main branch scored {main_kept}/7, expected 2"
        )
    if new_branch < 6:
        failures.append(
            f"rewind run new branch scored {new_branch}/7, expected >= 6"
        )
    if not whisper_seen:
        failures.append("rewind run saw no coach whisper on stalled turns")
    if failures:
        for failure in failures:
            print(f"DEMO FAILED: {failure}", file=sys.stderr)
        return 1
    print("DEMO OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
