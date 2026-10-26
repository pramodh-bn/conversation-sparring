"""Scenario graph schema, loading, and validation.

Frozen interface (see SPEC.md): other modules build to this.

- ``load_scenario(path)`` reads a scenario JSON file, validates it,
  and returns the dict.
- ``validate_scenario(scenario)`` raises ``ValueError`` with a clear
  message on ANY violation; it returns ``None`` on success.

Stdlib only. No network, no API keys.
"""

import json

VALID_GATES = ("any", "open", "meaning")
VALID_LEVELS = ("surface", "concern", "value")

# Rank used to enforce non-decreasing level order:
# surface (0) < concern (1) < value (2).
_LEVEL_RANK = {"surface": 0, "concern": 1, "value": 2}

_REQUIRED_SCENARIO_KEYS = ("scenario_id", "title", "character", "nodes")
_REQUIRED_CHARACTER_KEYS = ("name", "role", "persona", "opening_line")
_REQUIRED_NODE_KEYS = ("id", "level", "text", "gate", "hint")

EXPECTED_NODE_COUNT = 7
MIN_MEANING_GATED_NODES = 2


def validate_scenario(scenario: dict) -> None:
    """Validate a scenario dict; raise ValueError on any violation."""
    if not isinstance(scenario, dict):
        raise ValueError("scenario must be a JSON object (dict)")

    for key in _REQUIRED_SCENARIO_KEYS:
        if key not in scenario:
            raise ValueError(f"scenario is missing required key: {key!r}")

    character = scenario["character"]
    if not isinstance(character, dict):
        raise ValueError("scenario 'character' must be an object")
    for key in _REQUIRED_CHARACTER_KEYS:
        if key not in character:
            raise ValueError(f"character is missing required key: {key!r}")

    nodes = scenario["nodes"]
    if not isinstance(nodes, list):
        raise ValueError("scenario 'nodes' must be a list")

    if len(nodes) != EXPECTED_NODE_COUNT:
        raise ValueError(
            f"scenario must have exactly {EXPECTED_NODE_COUNT} nodes, "
            f"got {len(nodes)}"
        )

    seen_ids = set()
    previous_rank = -1
    meaning_gated = 0
    for index, node in enumerate(nodes):
        if not isinstance(node, dict):
            raise ValueError(f"node at index {index} must be an object")
        for key in _REQUIRED_NODE_KEYS:
            if key not in node:
                raise ValueError(
                    f"node at index {index} is missing required key: {key!r}"
                )

        node_id = node["id"]
        if node_id in seen_ids:
            raise ValueError(f"duplicate node id: {node_id!r}")
        seen_ids.add(node_id)

        gate = node["gate"]
        if gate not in VALID_GATES:
            raise ValueError(
                f"node {node_id!r} has invalid gate {gate!r}; "
                f"must be one of {sorted(VALID_GATES)}"
            )
        if gate == "meaning":
            meaning_gated += 1

        level = node["level"]
        if level not in VALID_LEVELS:
            raise ValueError(
                f"node {node_id!r} has invalid level {level!r}; "
                f"must be one of {sorted(VALID_LEVELS)}"
            )
        rank = _LEVEL_RANK[level]
        if rank < previous_rank:
            raise ValueError(
                "node levels must be in non-decreasing order "
                f"(surface < concern < value); node {node_id!r} at index "
                f"{index} has level {level!r} after a deeper level"
            )
        previous_rank = rank

    if meaning_gated < MIN_MEANING_GATED_NODES:
        raise ValueError(
            f"scenario must have at least {MIN_MEANING_GATED_NODES} "
            f"meaning-gated nodes, got {meaning_gated}"
        )


def load_scenario(path: str) -> dict:
    """Read a scenario JSON file, validate it, and return the dict."""
    with open(path, "r", encoding="utf-8") as f:
        scenario = json.load(f)
    validate_scenario(scenario)
    return scenario
