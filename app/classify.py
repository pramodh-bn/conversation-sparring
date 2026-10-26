"""v1 rule-based question classifier.

``classify(text)`` returns ``'closed'`` | ``'open'`` | ``'meaning'``.

Heuristic, applied in exactly this order:

1. MEANING check first. The lowercased text is scanned for any of these
   substring keywords::

       "feel", "feeling", "felt", "afraid", "fear", "worried",
       "worries", "worry", "matters most", "matters to you",
       "mean to you", "meaning", "care about", "important to you"

   If any matches, the question is ``'meaning'`` -- even if it is also a
   wh-question (e.g. "What worries you most about falling behind?" is
   meaning, not open, because the worry keyword is checked first).

2. CLOSED. If the stripped text starts with a yes/no auxiliary as its
   first word -- do / does / did / is / are / was / were / can / could /
   will / would / should / have / has / had -- OR ends with a tag
   question (", right?", ", isn't it?", ", don't you?", ", doesn't it?",
   ", aren't you?"), it is ``'closed'``.

3. OPEN. If the first word is a wh-word -- what / how / why / when /
   where / who / which -- it is ``'open'``.

4. Default. Anything else (statements, imperatives, fragments, empty
   input) is ``'open'``.

Known limits of this v1 heuristic (the Day 3/4 coach agent will replace
it; the ``classify`` interface must stay identical):

- Substring matching is blunt: "feel" also matches "feeling" (intended)
  but would match any word containing those letters, and a feeling word
  used incidentally ("I don't feel like a yes/no question") still forces
  'meaning'.
- Only the listed tag-question endings count as closed; other tags
  ("...isn't it though?", "...right.") are missed.
- Only the first word is inspected, so a yes/no question buried after a
  preamble ("So, tell me, did you...?") falls through to the default.
- Contractions are handled by reading the first alphabetic token only,
  so "What's ..." counts as "what" and "You're ..." does not count as a
  closed starter (it is still caught by the tag-question rule).
- There is no semantic understanding: a factual wh-question that happens
  to contain "important to you" is classified as meaning, and a genuine
  values question phrased without any listed keyword is missed.
"""

import re

_MEANING_KEYWORDS = (
    "feel",
    "feeling",
    "felt",
    "afraid",
    "fear",
    "worried",
    "worries",
    "worry",
    "matters most",
    "matters to you",
    "mean to you",
    "meaning",
    "care about",
    "important to you",
)

_CLOSED_STARTERS = {
    "do",
    "does",
    "did",
    "is",
    "are",
    "was",
    "were",
    "can",
    "could",
    "will",
    "would",
    "should",
    "have",
    "has",
    "had",
}

_TAG_QUESTIONS = (
    ", right?",
    ", isn't it?",
    ", don't you?",
    ", doesn't it?",
    ", aren't you?",
)

_OPEN_STARTERS = {
    "what",
    "how",
    "why",
    "when",
    "where",
    "who",
    "which",
}

_FIRST_WORD_RE = re.compile(r"[a-z]+")


def _first_word(lowered_stripped: str) -> str:
    """First alphabetic token, so "what's" reads as "what"."""
    match = _FIRST_WORD_RE.match(lowered_stripped)
    return match.group(0) if match else ""


def classify(text: str) -> str:
    """Classify one user utterance as 'closed', 'open', or 'meaning'.

    Rules are applied in the fixed order: meaning keywords, then closed
    starters / tag questions, then wh-word openers, then default 'open'.
    """
    lowered = text.lower()
    stripped = lowered.strip()

    # 1. MEANING check first, via substring keywords.
    for keyword in _MEANING_KEYWORDS:
        if keyword in lowered:
            return "meaning"

    # 2. CLOSED: yes/no starter, or a tag-question ending.
    if _first_word(stripped) in _CLOSED_STARTERS:
        return "closed"
    if any(stripped.endswith(tag) for tag in _TAG_QUESTIONS):
        return "closed"

    # 3. OPEN: wh-word starter.
    if _first_word(stripped) in _OPEN_STARTERS:
        return "open"

    # 4. Default.
    return "open"
