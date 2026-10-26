"""Tests for app/graph.py (scenario graph loading + validation).

The scenario path is resolved relative to the project root, not the
current working directory, so these tests pass from any cwd.
"""

import copy
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.graph import load_scenario, validate_scenario

SCENARIO_PATH = PROJECT_ROOT / "scenarios" / "teammate.json"

VALID_GATES = {"any", "open", "meaning"}
VALID_LEVELS = {"surface", "concern", "value"}
_LEVEL_RANK = {"surface": 0, "concern": 1, "value": 2}


@pytest.fixture
def scenario():
    return load_scenario(str(SCENARIO_PATH))


def test_load_scenario_loads_teammate_json():
    scenario = load_scenario(str(SCENARIO_PATH))
    assert scenario["scenario_id"] == "teammate-deadlines"
    assert scenario["title"] == "The teammate who keeps missing deadlines"
    assert scenario["character"]["name"] == "Alex"
    assert len(scenario["nodes"]) == 7


def test_scenario_has_seven_nodes(scenario):
    assert len(scenario["nodes"]) == 7


def test_node_ids_unique(scenario):
    ids = [node["id"] for node in scenario["nodes"]]
    assert len(ids) == len(set(ids))


def test_gates_and_levels_valid(scenario):
    for node in scenario["nodes"]:
        assert node["gate"] in VALID_GATES
        assert node["level"] in VALID_LEVELS


def test_levels_in_non_decreasing_order(scenario):
    ranks = [_LEVEL_RANK[node["level"]] for node in scenario["nodes"]]
    assert ranks == sorted(ranks)


def test_at_least_two_meaning_gated_nodes(scenario):
    meaning_gated = [n for n in scenario["nodes"] if n["gate"] == "meaning"]
    assert len(meaning_gated) >= 2


def test_validation_accepts_loaded_scenario(scenario):
    # load_scenario already validates, but the public validator
    # must also accept the shipped scenario on its own.
    validate_scenario(scenario)


def test_validation_rejects_duplicate_id(scenario):
    bad = copy.deepcopy(scenario)
    bad["nodes"][1]["id"] = bad["nodes"][0]["id"]
    with pytest.raises(ValueError):
        validate_scenario(bad)


def test_validation_rejects_bad_gate(scenario):
    bad = copy.deepcopy(scenario)
    bad["nodes"][0]["gate"] = "deep"
    with pytest.raises(ValueError):
        validate_scenario(bad)


def test_validation_rejects_wrong_node_count(scenario):
    bad = copy.deepcopy(scenario)
    bad["nodes"] = bad["nodes"][:6]
    with pytest.raises(ValueError):
        validate_scenario(bad)


def test_validation_rejects_bad_level(scenario):
    bad = copy.deepcopy(scenario)
    bad["nodes"][0]["level"] = "hidden"
    with pytest.raises(ValueError):
        validate_scenario(bad)


def test_validation_rejects_out_of_order_levels(scenario):
    bad = copy.deepcopy(scenario)
    # Swap a surface node to after a value node: levels decrease.
    bad["nodes"][0], bad["nodes"][-1] = bad["nodes"][-1], bad["nodes"][0]
    with pytest.raises(ValueError):
        validate_scenario(bad)


def test_validation_rejects_too_few_meaning_gated_nodes(scenario):
    bad = copy.deepcopy(scenario)
    for node in bad["nodes"]:
        if node["gate"] == "meaning":
            node["gate"] = "open"
    with pytest.raises(ValueError):
        validate_scenario(bad)


def test_validation_rejects_missing_required_keys(scenario):
    bad = copy.deepcopy(scenario)
    del bad["title"]
    with pytest.raises(ValueError):
        validate_scenario(bad)

    bad = copy.deepcopy(scenario)
    del bad["character"]["persona"]
    with pytest.raises(ValueError):
        validate_scenario(bad)

    bad = copy.deepcopy(scenario)
    del bad["nodes"][0]["hint"]
    with pytest.raises(ValueError):
        validate_scenario(bad)
