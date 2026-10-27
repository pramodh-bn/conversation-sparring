"""Character portraits (CS-7, stub-only).

Expression state is a pure function of score: thirds of progress map
to "guarded" / "softening" / "open", so progress is visible as well as
scored.

There is deliberately NO live image client here (user direction
2026-10-27, option 1: plumbing + stub). No image endpoint or key is
configured, so StubPortraitClient returns deterministic labeled-SVG
bytes clearly marked as not-live. The live swap seam is
portrait_payload(): it takes the score and returns the payload the
server serves; a future live client slots in behind it once the user
confirms an endpoint and key. Research for that swap (Meta official
cookbook, meta-models/meta-model-cookbook 05_muse_image): Responses
API, model muse-image-1.0, previous_response_id refinement to shift
one portrait's expression across turns. EXPRESSION_PROMPTS holds the
per-state refinement instructions for that day; the stub ignores them.
"""

from __future__ import annotations

import base64

EXPRESSIONS = ("guarded", "softening", "open")

# Refinement instructions per expression state, reserved for the live
# swap (unused by the stub). The base portrait is generated once and
# each state refines it with its instruction, keeping the same sitter.
EXPRESSION_PROMPTS = {
    "guarded": (
        "same man, guarded and closed: tense jaw, narrowed eyes, "
        "arms-crossed feel, dimmer cooler light"
    ),
    "softening": (
        "same man, softening: easing jaw, eyes opening, neutral "
        "warmer light"
    ),
    "open": (
        "same man, open and warm: relaxed face, gentle direct gaze, "
        "warm light"
    ),
}

_STUB_SIZE = 240


def expression_for_score(revealed: int, total: int) -> str:
    """Map (revealed, total) to an expression state (thirds)."""
    if total <= 0:
        return EXPRESSIONS[0]
    index = min(2, max(0, revealed) * 3 // total)
    return EXPRESSIONS[index]


class StubPortraitClient:
    """Deterministic labeled-SVG portraits. No network, never live."""

    def portrait(self, expression: str) -> bytes:
        """Return SVG bytes for an expression state (UTF-8)."""
        if expression not in EXPRESSIONS:
            raise ValueError(f"unknown expression: {expression!r}")
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" '
            f'width="{_STUB_SIZE}" height="{_STUB_SIZE}" role="img">'
            '<rect width="100%" height="100%" fill="#e8e4da"/>'
            '<rect x="8" y="8" width="224" height="224" fill="none" '
            'stroke="#6c3483" stroke-width="3"/>'
            '<text x="120" y="105" text-anchor="middle" '
            'font-family="sans-serif" font-size="26" fill="#222">'
            f"{expression}</text>"
            '<text x="120" y="140" text-anchor="middle" '
            'font-family="sans-serif" font-size="16" fill="#6c3483">'
            "STUB \u2014 not a live render</text>"
            "</svg>"
        )
        return svg.encode("utf-8")


_STUB = StubPortraitClient()


def portrait_payload(revealed: int, total: int) -> dict:
    """Portrait payload for a score: expression + stub image data URL."""
    expression = expression_for_score(revealed, total)
    raw = _STUB.portrait(expression)
    data_url = "data:image/svg+xml;base64," + base64.b64encode(raw).decode()
    return {"expression": expression, "stub": True, "image": data_url}
