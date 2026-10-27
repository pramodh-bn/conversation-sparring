"""Coach agent for Conversation Sparring (Day 3/4).

The coach whispers a better follow-up question AFTER a stalled turn (a
turn that revealed nothing), paired with the rewind button. It stays
silent on revealing turns and on completed sessions.

``coach_view`` shape (built by ``Session.add_turn``)::

    {
        'user_text': str,            # the stalled question, verbatim
        'question_type': str,        # 'closed' | 'open' | 'meaning'
        'revealed_anything': bool,   # False on stalled turns
        'score': {'revealed': int, 'total': int},
        'revealed_titles': [str],    # revealed node titles ONLY, graph order
    }

Safety invariant (by construction, same as the character): the coach
only ever receives the stalled question, its type, the score, and
already-revealed titles. It never receives unrevealed node text,
unrevealed titles, hints, or gate information, and ``RuleCoach``'s
rewrites are generic templates, so a whisper cannot leak the answer.

``RuleCoach`` is the DEFAULT: deterministic template rewrites, no API
key, no network. ``SparkCoach`` calls Muse Spark through the existing
``MetaSparkClient`` pattern; it is inert without a key and is NOT used
by default.
"""

from __future__ import annotations

import re

from app.character import MetaSparkClient

# Fallback when no closed->open template matches. Generic by
# construction: it names no scenario content.
FALLBACK_OPEN_QUESTION = "What would you say is going on here?"

# Generic meaning framings for open-but-stalled turns. Fixed bank,
# rotated deterministically (see RuleCoach).
MEANING_BANK = (
    "How did that feel?",
    "What worries you most about this?",
    "What matters most to you here?",
)

# "Did you <verb> <object>?" -> "What happened with <object>?"
_DID_YOU_RE = re.compile(
    r"^(did|do|does)\s+you\s+(\w+)\s+(.+?)\s*[?.!]*$", re.IGNORECASE
)

# "Is <subject> <participle> yet?" -> "What's going on with <subject>?"
_IS_SUBJECT_DONE_RE = re.compile(
    r"^(is|are|was|were)\s+(.+?)\s+"
    r"(finished|done|ready|complete|completed|started|late|behind)"
    r"(?:\s+(yet|still|already|again))?\s*[?.!]*$",
    re.IGNORECASE,
)

# Trailing adverbs stripped from an extracted object phrase.
_TRAILING_FILLER_RE = re.compile(
    r"\s+(again|still|yet|already)\s*$", re.IGNORECASE
)

# If an extracted subject still contains one of these, it is a clause
# rather than a noun phrase ("it going to be"), so the template does
# not apply and the fallback is used instead.
_VERBISH_TOKENS = frozenset(
    "going go be been being do does did doing have has had "
    "will would can could should".split()
)

_MAX_PHRASE_WORDS = 6


class CoachAgent:
    """Base interface: suggest a better follow-up question, or None."""

    def suggest(self, coach_view: dict) -> str | None:
        """Return a whisper for a stalled turn, or None to stay silent."""
        raise NotImplementedError


class RuleCoach(CoachAgent):
    """Template coach (DEFAULT). No API key, no network.

    - Revealing turn (``revealed_anything`` True) -> None.
    - Completed session (score revealed >= total) -> None.
    - Stalled ``closed`` question -> open rewrite of the question, or
      the generic fallback when no template matches.
    - Stalled ``open``/``meaning`` question -> next meaning framing
      from ``MEANING_BANK``, rotating per instance (a fresh coach
      starts at the first framing, so tests are deterministic).
    """

    def __init__(self):
        self._meaning_index = 0

    def suggest(self, coach_view: dict) -> str | None:
        if coach_view.get("revealed_anything"):
            return None
        score = coach_view.get("score") or {}
        total = score.get("total", 0) or 0
        revealed = score.get("revealed", 0) or 0
        if total and revealed >= total:
            return None
        if coach_view.get("question_type") == "closed":
            return self._open_rewrite(coach_view.get("user_text", ""))
        whisper = MEANING_BANK[self._meaning_index % len(MEANING_BANK)]
        self._meaning_index += 1
        return whisper

    def _open_rewrite(self, user_text: str) -> str:
        """Rewrite a closed question as an open one (templates)."""
        text = (user_text or "").strip()

        match = _DID_YOU_RE.match(text)
        if match:
            object_phrase = _TRAILING_FILLER_RE.sub("", match.group(3)).strip()
            if object_phrase and len(object_phrase.split()) <= _MAX_PHRASE_WORDS:
                return f"What happened with {object_phrase.lower()}?"
            return FALLBACK_OPEN_QUESTION

        match = _IS_SUBJECT_DONE_RE.match(text)
        if match:
            subject = match.group(2).strip()
            words = subject.lower().split()
            if (
                subject
                and len(words) <= _MAX_PHRASE_WORDS
                and not (_VERBISH_TOKENS & set(words))
            ):
                return f"What's going on with {subject.lower()}?"
            return FALLBACK_OPEN_QUESTION

        return FALLBACK_OPEN_QUESTION


_COACH_PERSONA = (
    "You are a conversation coach helping someone practice asking "
    "better questions. The user's latest question went nowhere: the "
    "other person deflected. Suggest exactly one better follow-up "
    "question the user could ask instead. Reply with ONLY the "
    "suggested question, nothing else."
)


class SparkCoach(CoachAgent):
    """Muse Spark coach. Inert without a key; NOT used by default.

    Configuration is env-only via ``MetaSparkClient`` (same pattern as
    the Day 1/2 character): ``META_MODEL_API_KEY`` (required),
    ``META_MODEL_API_BASE`` (required, no hardcoded default),
    ``META_MODEL_API_MODEL`` (default ``'muse-spark-1.3'``). Without a
    key, ``suggest()`` on a stalled turn raises ``RuntimeError`` before
    any network call; revealing turns still return None silently.
    """

    def __init__(self, client=None):
        self.client = client if client is not None else MetaSparkClient()

    def suggest(self, coach_view: dict) -> str | None:
        if coach_view.get("revealed_anything"):
            return None
        score = coach_view.get("score") or {}
        total = score.get("total", 0) or 0
        revealed = score.get("revealed", 0) or 0
        if total and revealed >= total:
            return None
        user_text = coach_view.get("user_text", "")
        view = {
            "character": {"persona": _COACH_PERSONA},
            "revealed": [],
            "turn_count": 0,
        }
        prompt = (
            "The user asked a question that went nowhere: "
            f"{user_text!r} Suggest one better follow-up question."
        )
        return self.client.respond(view, prompt, [])
