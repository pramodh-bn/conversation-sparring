"""Structure pins for the single-page UI (CS-18).

These read the served HTML only. Behaviour (layout, scrolling, focus,
the scorecard, rewind markers) is verified in a real browser run recorded
on the CS-18 task; pytest cannot see it. What is pinned here is what the
other code depends on and what must never regress:

- the element ids that tests, browser scripts and the CS-17 score work use,
- the accessibility hooks (label, log/status roles),
- the honest portrait-stub caption,
- the page contains no hidden scenario text (no-leak at the page level),
- the page loads nothing from the network.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

from app import server

client = TestClient(server.app)

# Ids that CS-4 / CS-7 / CS-17 and browser scripts rely on.
PRESERVED_IDS = [
    "score-line", "score", "score-branch", "transcript", "question", "send",
    "new-session", "rewind", "whisper-panel", "whisper-text", "branches",
    "branch-panel", "portrait", "portrait-panel", "portrait-caption",
    "revealed", "completion-summary", "completion-title", "completion-result",
    "summary-new-session",
]


def _html():
    res = client.get("/")
    assert res.status_code == 200
    return res.text


def test_page_keeps_the_ids_other_code_depends_on():
    html = _html()
    missing = [i for i in PRESERVED_IDS if f'id="{i}"' not in html]
    assert not missing, missing


def test_question_input_has_a_real_label():
    html = _html()
    assert '<label for="question"' in html
    assert 'id="question"' in html


def test_live_regions_and_roles_for_assistive_tech():
    html = _html()
    assert 'id="transcript" role="log"' in html
    assert 'class="score-live" role="status"' in html
    assert 'id="whisper-panel" role="status"' in html
    assert 'aria-current' in html  # current branch is announced, not just bold


def test_progress_has_a_text_alternative_and_seven_marks_are_data_driven():
    html = _html()
    assert 'id="progress" role="img" aria-label=' in html
    # Marks are created from the server's total, never hard-coded as nodes.
    assert "renderMarks(" in html


def test_coach_action_is_labelled_for_the_retry_flow():
    assert "Try again from here" in _html()


def test_portrait_stub_stays_honestly_labelled():
    html = _html()
    assert "not a live" in html
    assert "stub" in html.lower()


def test_page_declares_dark_mode_and_reduced_motion():
    html = _html()
    assert "prefers-color-scheme: dark" in html
    assert "prefers-reduced-motion" in html


def test_page_never_contains_hidden_scenario_text():
    # No-leak at the page level: node titles and texts come from the API
    # only after a reveal, so the static page must not carry any of them.
    html = _html()
    for node in server.get_scenario()["nodes"]:
        for field in ("title", "text"):
            value = node.get(field)
            if value:
                assert value not in html, f"{node['id']} {field} appears in the page"


def test_page_loads_nothing_from_the_network():
    html = _html()
    for needle in ('src="http', "src='http", 'href="http', "href='http", "@import", "<link rel=\"stylesheet\""):
        assert needle not in html, needle
