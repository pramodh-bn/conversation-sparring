"""Character agents for Conversation Sparring.

The character is the teammate the user is practising on. It speaks in
the teammate's voice: plain, a bit tired, never corporate.

Safety invariant (by construction): the character only ever receives
node text that has already been revealed. ``session_view['revealed']``
holds node dicts revealed on earlier turns and ``newly_revealed`` holds
node dicts revealed on this turn; neither ever contains an unrevealed
node. The implementations below only ever read text from those two
inputs, so they cannot utter unrevealed node content -- there is simply
no path by which unrevealed text reaches them.

``session_view`` shape::

    {
        'character': {'name': ..., 'role': ..., 'persona': ...,
                      'opening_line': ...},
        'revealed': [node dicts ALREADY revealed only],
        'turn_count': int,
    }

Each node dict has ``id`` / ``title`` / ``text``.

``ScriptedCharacter`` is the DEFAULT: it works with no API key and no
network. ``MetaSparkClient`` is an OpenAI-compatible chat completions
client for the Meta Model API; it is inert without a key (see below)
and is NOT used by default.
"""

import os

import httpx

# Deflections used when nothing new was revealed this turn. They are
# fixed strings that contain no scenario content, so they can never
# leak a node. Rotation is keyed by turn_count so repeated deflections
# do not sound identical.
_DEFLECTIONS = (
    "I'd rather not get into that right now.",
    "Can we stick to the work for a minute?",
    "I'm not sure I want to talk about that part yet.",
)


class CharacterAgent:
    """Base interface: respond to one user turn in character."""

    def respond(
        self,
        session_view: dict,
        user_text: str,
        newly_revealed: list[dict],
    ) -> str:
        """Return the character's reply for this turn.

        ``session_view`` and ``newly_revealed`` contain only already
        revealed node text (see module docstring).
        """
        raise NotImplementedError


class ScriptedCharacter(CharacterAgent):
    """Scripted teammate (DEFAULT). No API key, no network.

    - If ``newly_revealed`` is non-empty, each newly revealed node's
      text is woven into a natural reply: the node text is quoted /
      paraphrased in the teammate's voice, never just dumped as a list.
    - If ``newly_revealed`` is empty, the character deflects in
      character without revealing anything new, rotating through
      :data:`_DEFLECTIONS` keyed by ``turn_count``.
    - It only ever uses text from ``newly_revealed`` (and, for context,
      ``session_view['revealed']``); it never receives unrevealed text,
      so it cannot leak it.
    """

    def respond(
        self,
        session_view: dict,
        user_text: str,
        newly_revealed: list[dict],
    ) -> str:
        if newly_revealed:
            return self._voice_newly_revealed(newly_revealed)
        turn_count = session_view.get("turn_count", 0)
        return _DEFLECTIONS[turn_count % len(_DEFLECTIONS)]

    def _voice_newly_revealed(self, newly_revealed: list[dict]) -> str:
        """Weave each newly revealed node's text into one reply."""
        texts = []
        for node in newly_revealed:
            text = node.get("text", "").strip()
            if not text:
                continue
            # Avoid doubling the lead-in ("Yeah, alright... look, Yeah, ...")
            # when a node text itself opens with "Yeah, ".
            if text.lower().startswith("yeah, "):
                text = text[6:].lstrip()
            texts.append(text)
        if not texts:
            return "Yeah... I'm not sure how to put it, honestly."
        if len(texts) == 1:
            return f"Yeah, alright... look, {texts[0]}"
        # Multiple nodes opened on one turn: voice them in order,
        # joined conversationally rather than dumped as a list.
        voiced = texts[0]
        for text in texts[1:]:
            voiced += f" And honestly, {text}"
        return f"Yeah, alright... look, {voiced}"


class MetaSparkClient(CharacterAgent):
    """OpenAI-compatible chat completions client for the Meta Model API.

    Configuration is env-only:

    - ``META_MODEL_API_BASE``: base URL. There is NO hardcoded default
      -- the base URL is not verified against Meta's docs here, so it
      must come from the environment. If it is absent, ``respond()``
      raises ``RuntimeError`` with a clear message.
    - ``META_MODEL_API_MODEL``: model name, default ``'muse-spark-1.3'``.
    - ``META_MODEL_API_KEY``: API key. There is no other source for the
      key. If it is absent, ``respond()`` raises ``RuntimeError`` with a
      clear message -- never a crash at import, and never a network
      call without a key.

    This client is NOT used by default and NOT needed for tests. When
    no key is set it is fully inert: constructing it does nothing, and
    only calling ``respond()`` raises.

    Each call POSTs to ``{base}/chat/completions`` with ``model`` and
    ``messages`` of ``[{role: system, content: persona},
    {role: user, content: user_text}]`` plus
    ``Authorization: Bearer <key>``, and returns the first choice's
    message content.
    """

    def __init__(self, base_url=None, model=None, api_key=None):
        # Explicit arguments (if a caller passes them) win; otherwise
        # env vars only. In particular the base URL has no hardcoded
        # fallback, and the key is read from the environment only.
        self.base_url = (
            base_url
            if base_url is not None
            else os.environ.get("META_MODEL_API_BASE")
        )
        self.model = (
            model
            if model is not None
            else os.environ.get("META_MODEL_API_MODEL", "muse-spark-1.3")
        )
        self.api_key = (
            api_key if api_key is not None else os.environ.get("META_MODEL_API_KEY")
        )

    def respond(
        self,
        session_view: dict,
        user_text: str,
        newly_revealed: list[dict],
    ) -> str:
        if not self.api_key:
            raise RuntimeError(
                "MetaSparkClient needs META_MODEL_API_KEY to be set; "
                "no key is configured, so the scripted character is "
                "the default. Set META_MODEL_API_KEY to use the live model."
            )
        if not self.base_url:
            raise RuntimeError(
                "MetaSparkClient needs META_MODEL_API_BASE to be set; "
                "no base URL is configured and none is hardcoded. "
                "Set META_MODEL_API_BASE to use the live model."
            )
        character = session_view.get("character", {}) or {}
        persona = character.get("persona", "") or ""
        url = self.base_url.rstrip("/") + "/chat/completions"
        response = httpx.post(
            url,
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": persona},
                    {"role": "user", "content": user_text},
                ],
            },
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=30.0,
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]
