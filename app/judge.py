"""Deterministic scoring from session state. No LLM anywhere.

``score(session)`` returns::

    {'revealed': int, 'total': int, 'fraction': float}

It is pure and deterministic: the same session state always gives the
same result, and scoring never mutates the session.

To avoid an import cycle, this module does NOT import ``app.session``.
It accepts any object with ``.revealed`` and either ``.score_total``
or ``.scenario`` (a dict with a ``nodes`` list). ``.revealed`` may be
a set of node ids or a list of node dicts / ids.
"""

from __future__ import annotations


def _revealed_count(session) -> int:
    revealed = getattr(session, "revealed", None)
    if revealed is None:
        return 0
    try:
        return len(revealed)
    except TypeError:
        return 0


def _total(session) -> int:
    total = getattr(session, "score_total", None)
    if isinstance(total, int) and total >= 0:
        return total
    scenario = getattr(session, "scenario", None)
    if isinstance(scenario, dict):
        nodes = scenario.get("nodes")
        if isinstance(nodes, list):
            return len(nodes)
    # Fall back to a plain ``total`` attribute, if present.
    total = getattr(session, "total", None)
    if isinstance(total, int) and total >= 0:
        return total
    return 0


def score(session) -> dict:
    """Score a session (or any session-like object) deterministically."""
    revealed = _revealed_count(session)
    total = _total(session)
    fraction = (revealed / total) if total else 0.0
    return {"revealed": revealed, "total": total, "fraction": fraction}
