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
'classify', 'gate_check', 'reveal', 'score' (see ``add_turn``). When a
coach is passed to ``add_turn`` and the turn is stalled (nothing
revealed), a 5th record ('coach_whisper') is appended after 'score'.

Branches (Day 3/4, CS-3): a Session holds ``branches`` (id -> Branch)
plus an ``active_branch_id``. A Branch carries its own turns, revealed
set, and decisions, so branches score independently. The Day 1/2
single-branch behavior is branch ``"main"``; ``turns`` / ``revealed``
/ ``decisions`` / scoring on Session are live views of the active
branch, so Day 1/2 callers keep working unchanged.

No LLM anywhere. No network, no API keys.
"""

from __future__ import annotations

import copy

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


class Branch:
    """One timeline of a session: turns, revealed set, decisions."""

    def __init__(self, branch_id, parent_branch_id=None, fork_turn_index=0):
        self.id = branch_id
        self.parent_branch_id = parent_branch_id
        self.fork_turn_index = fork_turn_index
        # Each turn dict: user_text, question_type, newly_revealed.
        self.turns = []
        # Set of revealed node ids.
        self.revealed = set()
        # List of decision records (see app.decisions).
        self.decisions = []

    @property
    def label(self) -> str:
        """Human label derived from the fork point (no user names)."""
        if self.id == "main":
            return "Main"
        return f"Branch {self.id} (from turn {self.fork_turn_index})"

    @property
    def score_count(self) -> int:
        return len(self.revealed)

    def summary(self, total: int) -> dict:
        """Branch tree entry: id, parent, fork point, score, turn count."""
        return {
            "id": self.id,
            "label": self.label,
            "parent_branch_id": self.parent_branch_id,
            "fork_turn_index": self.fork_turn_index,
            "turn_count": len(self.turns),
            "score": {"revealed": self.score_count, "total": total},
        }


class Session:
    """One play-through of a scenario, possibly with many branches."""

    def __init__(self, scenario: dict):
        self.scenario = scenario
        self.scenario_id = scenario["scenario_id"]
        self.branches = {"main": Branch("main")}
        self.active_branch_id = "main"

    @property
    def _active(self) -> Branch:
        return self.branches[self.active_branch_id]

    # Day 1/2 compatibility: live views of the active branch.
    @property
    def turns(self) -> list:
        return self._active.turns

    @property
    def revealed(self) -> set:
        return self._active.revealed

    @property
    def decisions(self) -> list:
        return self._active.decisions

    def add_turn(self, user_text: str, coach=None) -> dict:
        """Classify, gate-check, reveal at most one node, log, score.

        Operates on the active branch. When ``coach`` (a
        ``CoachAgent``) is given and the turn is stalled
        (``newly_revealed`` empty), the coach is consulted and a
        'coach_whisper' record is appended after 'score'. The turn
        dict always carries ``coach_whisper`` (None unless the coach
        whispered on this turn).
        """
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

        whisper = None
        if coach is not None and not newly_revealed:
            whisper = coach.suggest({
                "user_text": user_text,
                "question_type": question_type,
                "revealed_anything": False,
                "score": {"revealed": self.score_count,
                          "total": self.score_total},
                "revealed_titles": [
                    node.get("title", node["id"])
                    for node in self.scenario["nodes"]
                    if node["id"] in self.revealed
                ],
            })
            record(self.decisions, turn_index, "coach_whisper",
                   input=turn_index, output=whisper)

        turn["coach_whisper"] = whisper
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

    def set_active_branch(self, branch_id: str) -> None:
        """Make ``branch_id`` the active branch.

        Raises ``KeyError`` for an unknown branch id.
        """
        if branch_id not in self.branches:
            raise KeyError(f"unknown branch: {branch_id!r}")
        self.active_branch_id = branch_id

    def _next_branch_id(self) -> str:
        for code in range(ord("B"), ord("Z") + 1):
            candidate = chr(code)
            if candidate not in self.branches:
                return candidate
        counter = 2
        while f"B{counter}" in self.branches:
            counter += 1
        return f"B{counter}"

    def create_branch(self, from_turn: int, from_branch_id=None) -> str:
        """Fork a new branch from the state BEFORE ``from_turn``.

        Copies turns [0..from_turn-1] plus the decision records of
        those turns from the source branch (the active branch unless
        ``from_branch_id`` names another). Revealed is recomputed as
        the union of ``newly_revealed`` across the copied turns, so no
        replay through the classifier is needed. The new branch
        becomes active and its id is returned.

        Raises ``KeyError`` for an unknown source branch and
        ``ValueError`` for an out-of-range ``from_turn``.
        """
        source_id = (
            from_branch_id if from_branch_id is not None
            else self.active_branch_id
        )
        if source_id not in self.branches:
            raise KeyError(f"unknown branch: {source_id!r}")
        source = self.branches[source_id]
        if (
            not isinstance(from_turn, int)
            or isinstance(from_turn, bool)
            or from_turn < 0
            or from_turn > len(source.turns)
        ):
            raise ValueError(
                f"from_turn {from_turn!r} out of range for "
                f"{len(source.turns)} turns"
            )
        branch_id = self._next_branch_id()
        branch = Branch(
            branch_id,
            parent_branch_id=source_id,
            fork_turn_index=from_turn,
        )
        branch.turns = copy.deepcopy(source.turns[:from_turn])
        branch.decisions = copy.deepcopy([
            record for record in source.decisions
            if record["turn_index"] < from_turn
        ])
        revealed = set()
        for turn in branch.turns:
            revealed.update(turn["newly_revealed"])
        branch.revealed = revealed
        self.branches[branch_id] = branch
        self.active_branch_id = branch_id
        return branch_id

    def branch_summaries(self) -> list:
        """Branch tree entries in creation order (main first)."""
        return [
            branch.summary(self.score_total)
            for branch in self.branches.values()
        ]
