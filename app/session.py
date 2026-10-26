"""Session state machine: turns, revealed nodes, score.

Gate rule (frozen, implemented exactly as specified):

On each user turn, reveal AT MOST the first unrevealed node (in graph
order) whose gate is satisfied by the question type:

- gate 'any'     is satisfied by any type
- gate 'open'    is satisfied by 'open' or 'meaning'
- gate 'meaning' is satisfied only by 'meaning'

So a closed-question-only run can only open 'any'-gated nodes, while
open/meaning questions progressively open deeper nodes.

Every turn appends exactly 4 decision records via ``app.decisions``:
'classify', 'gate_check', 'reveal', 'score' (see ``add_turn``).

No LLM anywhere. No network, no API keys.
"""

from __future__ import annotations

from app.classify import classify
from app.decisions import record


def _gate_satisfied(gate: str, question_type: str) -> bool:
    if gate == "any":
        return True
    if gate == "open":
        return question_type in ("open", "meaning")
    if gate == "meaning":
        return question_type == "meaning"
    # Unknown gates never open a node (graph validation rejects them
    # for loaded scenarios; this is a defensive default).
    return False


class Session:
    """One play-through of a scenario."""

    def __init__(self, scenario: dict):
        self.scenario = scenario
        self.scenario_id = scenario["scenario_id"]
        # Each turn dict: user_text, question_type, newly_revealed.
        self.turns = []
        # Set of revealed node ids.
        self.revealed = set()
        # List of decision records (see app.decisions).
        self.decisions = []

    def add_turn(self, user_text: str) -> dict:
        """Classify, gate-check, reveal at most one node, log, score."""
        turn_index = len(self.turns)
        question_type = classify(user_text)

        # Gate-check unrevealed nodes in graph order; reveal at most
        # the first whose gate is satisfied by this question type.
        newly_revealed = []
        revealed_id = None
        for node in self.scenario["nodes"]:
            node_id = node["id"]
            if node_id in self.revealed:
                continue
            if _gate_satisfied(node["gate"], question_type):
                newly_revealed = [node_id]
                revealed_id = node_id
                self.revealed.add(node_id)
                break

        turn = {
            "user_text": user_text,
            "question_type": question_type,
            "newly_revealed": list(newly_revealed),
        }
        self.turns.append(turn)

        # Exactly 4 decision records per turn, in fixed order.
        record(self.decisions, turn_index, "classify",
               input=user_text, output=question_type)
        record(self.decisions, turn_index, "gate_check",
               input=question_type, output=revealed_id)
        record(self.decisions, turn_index, "reveal",
               input=question_type, output=list(newly_revealed))
        record(self.decisions, turn_index, "score",
               input=list(newly_revealed),
               output={"revealed": self.score_count,
                       "total": self.score_total})

        return turn

    @property
    def score_count(self) -> int:
        return len(self.revealed)

    @property
    def score_total(self) -> int:
        return len(self.scenario["nodes"])

    @property
    def score(self) -> float:
        total = self.score_total
        return (self.score_count / total) if total else 0.0

    def session_view(self) -> dict:
        """Public view for the character: revealed nodes ONLY.

        Never includes unrevealed node text (or any unrevealed node
        content). Revealed nodes are returned as copies, in graph
        order, so callers cannot mutate session state through the view.
        """
        revealed_nodes = [
            dict(node)
            for node in self.scenario["nodes"]
            if node["id"] in self.revealed
        ]
        return {
            "character": self.scenario["character"],
            "revealed": revealed_nodes,
            "turn_count": len(self.turns),
        }
