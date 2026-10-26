# Conversation Sparring — Day 1/2 build

Meta Global AI Developer Hackathon 2026, Indie track. Working core loop,
text mode, ONE scenario. No coach, no rewind, no voice, no images —
those are Days 3+ work.

The contract this build implements is `SPEC.md` in this directory.

## What it is

Talk to a character with a hidden need; ask meaning-level questions to
uncover it. The character ("Alex", a teammate who keeps missing
deadlines) carries a 7-node hidden-need graph: surface position →
workload facts → feelings → real concern → core value. Deeper nodes
open only to meaning-level questions, so closed-question-only runs
score low and good-question runs score high. Scoring is deterministic
(revealed / 7) — no LLM anywhere in scoring.

## Setup

A virtualenv already exists in this directory (`.venv`) with everything
installed. To recreate it from scratch:

```bash
cd ~/workspace/hackathon-conversation-sparring
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Pinned deps (`requirements.txt`): fastapi==0.162.0, uvicorn==0.54.0,
pytest==9.1.1, httpx==0.28.1. Python 3.12 used here; 3.11+ per SPEC.

## Run the tests

```bash
cd ~/workspace/hackathon-conversation-sparring
.venv/bin/python -m pytest
```

Expected: **70 passed**. (One harmless Starlette deprecation warning
about `httpx` in `TestClient` may appear; it is not a failure.)

## Run the scripted demo (no API key needed)

```bash
cd ~/workspace/hackathon-conversation-sparring
.venv/bin/python scripts/demo_run.py
```

It runs two scripted conversations and prints every turn (question,
question type, newly revealed nodes, running score) plus final scores.
It exits 0 printing `DEMO OK` only if the closed-only run scores ≤ 3/7
and the good run scores ≥ 6/7. Verified results:

- Closed-only run (5 closed questions): **2/7** — reveals "Behind on
  the report" and "Three projects at once", then stalls; the character
  deflects.
- Good run (closed → open → open → 4× meaning): **7/7** — one new node
  per turn, ending on "Wants help re-prioritizing".

## Run the web UI

```bash
cd ~/workspace/hackathon-conversation-sparring
.venv/bin/python -m uvicorn app.server:app --port 8000
```

Then open http://127.0.0.1:8000/ — a single-page chat: type a
question, see Alex's reply, see the score "x/7" and the list of
revealed node titles. "New session" starts over. Sessions are
in-memory only; restarting the server clears them.

API:

- `POST /sessions` → new session id, character opening line, score 0/7.
- `POST /sessions/{id}/messages` with `{"text": "..."}` → reply,
  question type, newly revealed titles, score.
- `GET /sessions/{id}` → full state: turns, revealed titles, and the
  typed decision log (4 records per turn: classify, gate_check,
  reveal, score).

## What is stubbed (read before assuming more)

- **The character is scripted, not a live model.** `ScriptedCharacter`
  (in `app/character.py`) is the default: it voices newly revealed
  node text in Alex's voice and deflects otherwise. Everything works
  with no API key and no network.
- **The real Muse Spark client exists but is inert.** `MetaSparkClient`
  (same file) is an OpenAI-compatible chat-completions client. It is
  NOT used by the server, the demo, or any test. It needs three env
  vars, and there is deliberately NO hardcoded base URL:
  - `META_MODEL_API_KEY` — required; without it, `respond()` raises a
    clear `RuntimeError` (import/construction never crash).
  - `META_MODEL_API_BASE` — required; no default is baked in because
    the base URL was not verified against Meta's docs during this
    build. Set it from Meta's official docs when wiring the live model.
  - `META_MODEL_API_MODEL` — default `muse-spark-1.3`.
  - No key has been provided by the user, and none is stored anywhere
    in this repo. Do not commit one.
- **The classifier is rule-based v1** (`app/classify.py`): meaning
  keywords checked first, then closed-question patterns (auxiliary
  starters, tag questions), then wh-word open questions, default open.
  Its heuristic and known limits are documented in its docstring. The
  Day 3/4 coach agent will replace it; the `classify(text)` interface
  stays identical.
- **One scenario only** (`scenarios/teammate.json`): the teammate who
  keeps missing deadlines, 7 nodes. Scenarios 2–3, coach, rewind/
  branches, voice, and Muse Image portraits are explicitly out of
  scope for Days 1–2 and are not built.
- **No persistence:** sessions live in server memory; the decision log
  is returned by `GET /sessions/{id}` but is not written to disk.

## Design interpretations (smallest deviations, all documented)

These were judgment calls inside SPEC.md's latitude, not spec changes:

1. **One node per turn.** SPEC says "check gates of unrevealed nodes
   in order → reveal newly opened nodes". Implemented as: reveal at
   most the FIRST unrevealed node (in graph order) whose gate is
   satisfied. Gate satisfaction: `any` ← any type; `open` ← open or
   meaning; `meaning` ← meaning only. This is what makes disclosure
   progressive and the proof numbers meaningful.
2. **Per-node `title` field.** Nodes carry a short human-readable
   title (e.g. "Behind on the report") shown in the UI only AFTER the
   node is revealed. The validator does not require it, so it is an
   optional extension, not a schema change. Full hidden text is never
   shown for unrevealed nodes.
3. **`gate_check` decision record form.** Each turn appends exactly 4
   records (classify, gate_check, reveal, score). The `gate_check`
   record's output is the revealed node id, or `None` if nothing was
   revealed — the simpler of the two forms SPEC allowed.
4. **Character voicing polish (coordinator fix).** Node 1's text opens
   with "Yeah, "; the scripted reply lead-in is "Yeah, alright...
   look, ". The voicing strips a leading "Yeah, " from node text so
   the demo does not read "Yeah, alright... look, Yeah, I missed...".
   No node text or test expectation changed; suite still 70/70.

## Morning review — check these by hand

1. **Play the UI like a bad questioner:** only closed questions
   ("Did you miss the deadline again?", "Is it done yet?"). Confirm
   the score stalls at 2/7 and Alex deflects. Then play a good run
   (open, then meaning-level questions) and confirm deeper nodes open
   one per turn up to 7/7.
2. **No-leak check:** in the UI, confirm you only ever see TITLES of
   revealed nodes — never the hidden text of unrevealed ones. The
   character structurally cannot leak: it only ever receives revealed
   node text (see the `test_scripted_character_never_leaks...` test).
3. **Decision log:** `GET /sessions/{id}` after a few turns should
   show exactly 4 records per turn with kinds classify, gate_check,
   reveal, score.
4. **No-key operation:** confirm the demo and the server both work
   with `META_MODEL_API_KEY` unset (they were verified that way).
   `MetaSparkClient` raising `RuntimeError` without a key is the
   intended behavior, not a bug.
5. **Known v1 limits to keep in mind for Days 3/4:** the classifier
   is keyword-based and will misclassify edge phrasings; the scripted
   character repeats a fixed deflection rotation; the judge counts
   revealed nodes only (it does not rate question quality beyond the
   gate system).
