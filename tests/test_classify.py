"""Classifier spot checks for app.classify.classify.

Covers at least 3 examples per class, including ALL of the demo's proof
questions with their required classes (see SPEC.md / task contract).
No network calls.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from app.classify import classify


# --- Demo proof questions: required classes (other workers assert on these) ---

CLOSED_DEMO = [
    "Did you miss the deadline again?",
    "Is the report finished yet?",
    "You're behind, right?",
    "Did you tell your manager?",
    "Is it going to be late again?",
]

OPEN_DEMO = [
    "What's on your plate right now?",
    "How has this week actually been for you?",
]

MEANING_DEMO = [
    "What worries you most about falling behind?",
    "What are you afraid of here?",
    "What matters most to you in this job?",
    "What would it mean to you to get help re-prioritizing?",
]


@pytest.mark.parametrize("text", CLOSED_DEMO)
def test_demo_closed_questions(text):
    assert classify(text) == "closed"


@pytest.mark.parametrize("text", OPEN_DEMO)
def test_demo_open_questions(text):
    assert classify(text) == "open"


@pytest.mark.parametrize("text", MEANING_DEMO)
def test_demo_meaning_questions(text):
    assert classify(text) == "meaning"


# --- Additional examples: at least 3 per class overall (demos already
# exceed that for closed/meaning; open gets one extra here) ---


@pytest.mark.parametrize(
    "text",
    [
        "Are you going to make the deadline?",
        "Can you finish this by Friday?",
        "Should we move the review to next week?",
        "You haven't started yet, aren't you?",
        "The draft is ready, isn't it?",
    ],
)
def test_more_closed_questions(text):
    assert classify(text) == "closed"


@pytest.mark.parametrize(
    "text",
    [
        "Why did the deadline slip?",
        "Where are you stuck right now?",
        "When is the next milestone due?",
        "Who else is working on this with you?",
    ],
)
def test_more_open_questions(text):
    assert classify(text) == "open"


@pytest.mark.parametrize(
    "text",
    [
        "How did that feel when the deadline moved?",
        "What do you care about most on this team?",
        "What is important to you about this project?",
    ],
)
def test_more_meaning_questions(text):
    assert classify(text) == "meaning"


# --- Rule-ordering checks ---


def test_meaning_keyword_beats_wh_word():
    # "What worries you most..." is a wh-question, but the worry keyword
    # is checked first, so it must be meaning.
    assert classify("What worries you most about falling behind?") == "meaning"


def test_open_question_without_meaning_keyword_stays_open():
    # "How has this week actually been for you?" contains no meaning
    # keyword, so it must be open, not meaning.
    assert classify("How has this week actually been for you?") == "open"


def test_tag_question_beats_wh_word_absence():
    assert classify("You're behind, right?") == "closed"


def test_case_insensitive():
    assert classify("DID YOU MISS THE DEADLINE AGAIN?") == "closed"
    assert classify("WHAT WORRIES YOU MOST?") == "meaning"


def test_default_is_open():
    # Statements / fragments with no starter and no meaning keyword.
    assert classify("Tell me more.") == "open"
    assert classify("") == "open"
