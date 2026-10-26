"""Scripted demo for Conversation Sparring (Days 1-2).

Runs two conversations against the scripted character (no API key):
a closed-question-only run (expected to score low) and a good-question
run (expected to score high). Prints every turn plus a final score
line per run, then asserts closed <= 3 and good >= 6.

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


def main():
    scenario = load_scenario(PROJECT_ROOT / "scenarios" / "teammate.json")
    closed_count, _ = run_conversation("closed-only run", CLOSED_ONLY, scenario)
    good_count, _ = run_conversation("good run", GOOD_RUN, scenario)

    failures = []
    if closed_count > 3:
        failures.append(
            f"closed-only run scored {closed_count}/7, expected <= 3"
        )
    if good_count < 6:
        failures.append(f"good run scored {good_count}/7, expected >= 6")
    if failures:
        for failure in failures:
            print(f"DEMO FAILED: {failure}", file=sys.stderr)
        return 1
    print("DEMO OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
