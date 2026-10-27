"""Baseten-hosted Muse Spark Open backend (CS-10).

A second OpenAI-compatible live backend alongside ``MetaSparkClient``.
It reuses that client's request/response handling and differs only in
configuration, which is env-only:

- ``BASETEN_API_KEY``: required. Distinct from ``META_MODEL_API_KEY``;
  this client never reads the Meta key and ``MetaSparkClient`` never
  reads this one.
- ``BASETEN_API_BASE``: default ``https://inference.baseten.co/v1``.
- ``BASETEN_MODEL``: default ``meta-models/muse-spark-open-1026``. The
  hackathon key works only with this model name; Baseten's docs show a
  shorter ``meta-models/muse-spark-open``, which is wrong here.

Without a key the client is inert: construction never crashes and
``respond()`` raises ``RuntimeError`` before any network call. It is
NOT wired in by default; pass it wherever a ``CharacterAgent`` is
accepted, or to ``SparkCoach(client=BasetenClient())``.
"""

from __future__ import annotations

import os

from app.character import MetaSparkClient

DEFAULT_BASE_URL = "https://inference.baseten.co/v1"
DEFAULT_MODEL = "meta-models/muse-spark-open-1026"


class BasetenClient(MetaSparkClient):
    def __init__(self, base_url=None, model=None, api_key=None):
        super().__init__(
            base_url=(
                base_url
                if base_url is not None
                else os.environ.get("BASETEN_API_BASE", DEFAULT_BASE_URL)
            ),
            model=(
                model
                if model is not None
                else os.environ.get("BASETEN_MODEL", DEFAULT_MODEL)
            ),
            # Passing "" (not None) stops the parent from falling back
            # to META_MODEL_API_KEY when no Baseten key is set.
            api_key=(
                api_key
                if api_key is not None
                else os.environ.get("BASETEN_API_KEY", "")
            ),
        )

    def respond(self, session_view, user_text, newly_revealed):
        if not self.api_key:
            raise RuntimeError(
                "BasetenClient needs BASETEN_API_KEY to be set; no key "
                "is configured, so no request was made."
            )
        return super().respond(session_view, user_text, newly_revealed)
