"""Typed decision log (Decision Ledger spine).

Every turn appends records of the form::

    {'turn_index': int, 'kind': str, 'input': ..., 'output': ...}

where ``kind`` is one of 'classify' | 'gate_check' | 'reveal' | 'score'
| 'coach_whisper' (Day 3/4: appended after 'score' on stalled turns
only, when a coach is consulted).
Stdlib only. No network, no API keys, no LLM.
"""

import copy

VALID_KINDS = ("classify", "gate_check", "reveal", "score", "coach_whisper")


def record(decisions: list, turn_index: int, kind: str, input, output) -> dict:
    """Append a decision record to ``decisions`` and return it.

    The record is stored as given (no copying of ``input``/``output``
    beyond what the caller passes); ``export`` is the place that
    produces a detached, JSON-serializable copy.
    """
    rec = {
        "turn_index": turn_index,
        "kind": kind,
        "input": input,
        "output": output,
    }
    decisions.append(rec)
    return rec


def export(decisions) -> list:
    """Return a JSON-serializable deep copy of ``decisions``.

    The caller's list and its records are left untouched: mutating the
    exported copy must not affect the live log, and vice versa.
    """
    return copy.deepcopy(list(decisions))
