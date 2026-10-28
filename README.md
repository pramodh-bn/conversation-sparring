# Conversation Sparring — Day 1–4 build

Meta Global AI Developer Hackathon 2026, Indie track. Working core loop,
text mode, ONE scenario. Coach + rewind are built (Day 3/4); no voice,
no images —
those are Days 5+ work.

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

Expected: **134 passed**. (One harmless Starlette deprecation warning
about `httpx` in `TestClient` may appear; it is not a failure.)

## Run the scripted demo (no API key needed)

```bash
cd ~/workspace/hackathon-conversation-sparring
.venv/bin/python scripts/demo_run.py
```

It runs three scripted conversations and prints every turn (question,
question type, newly revealed nodes, running score) plus final scores.
It exits 0 printing `DEMO OK` only if the closed-only run scores ≤ 3/7
and the good run scores ≥ 6/7, and the rewind run's new branch scores
≥ 6/7 with the original branch still 2/7. Verified results:

- Closed-only run (5 closed questions): **2/7** — reveals "Behind on
  the report" and "Three projects at once", then stalls; the character
  deflects.
- Good run (closed → open → open → 4× meaning): **7/7** — one new node
  per turn, ending on "Wants help re-prioritizing".
- Rewind run: bad branch (5 closed questions) stalls at **2/7** with a
  coach whisper on the stalled turns; rewind to turn 2 forks branch B,
  which reaches **7/7** on good questions while main stays **2/7**.

## Run the web UI

```bash
cd ~/workspace/hackathon-conversation-sparring
.venv/bin/python -m uvicorn app.server:app --port 8000
```

Then open http://127.0.0.1:8000/ — a single-page chat (no build step,
no network assets). On a desktop the conversation is the main column
and stays put (the transcript scrolls inside it, the question box is
always visible); a sidebar keeps the live score "x/7" with seven
progress marks, the branch list with per-branch scores, the portrait
stub, and the list of uncovered needs. A coach whisper appears as its
own card under the stalled reply with "Try again from here", which
forks a branch; every one of your questions also has a small
"Retry from here" link. After a rewind the transcript marks the fork
and the score card shows Main and the retry branch side by side. At
7/7 a scorecard (final score, branches tried, before → after) replaces
the question box. On a phone the score strip stays pinned at the top,
the question box at the bottom, and the sidebar collapses.
"New session" asks for a second click when there is something to lose.
The page follows the OS light/dark setting and reduced-motion setting.
The score counts revealed scenario needs only; it is not a measure of
real-world skill. Sessions are in-memory only; restarting the server
clears them. `tests/test_ui_page.py` pins the page structure (ids,
labels, roles, honest stub caption, no hidden scenario text); layout
and behaviour were verified in a real browser run recorded on CS-18.

API:

- `POST /sessions` → new session id, character opening line, score 0/7.
- `POST /sessions/{id}/messages` with `{"text": "..."}` → reply,
  question type, newly revealed titles, coach whisper (string or
  null), score, branch id. Optional `{"branch_id": ...}` posts to (and
  activates) that branch.
- `GET /sessions/{id}` → full state: turns, revealed titles, and the
  typed decision log (4 records per turn: classify, gate_check,
  reveal, score, plus coach_whisper on stalled turns with a coach),
  branch summaries, and the active branch id.
- `POST /sessions/{id}/branches` with `{"from_turn": N,
  "from_branch_id?": ...}` → forks a new branch from the state before
  turn N (becomes active).
- `GET /sessions/{id}/branches` → branch tree: id, label, parent, fork
  point, score, turn count per branch.
- `GET /sessions/{id}/portrait` → portrait payload: expression
  (guarded/softening/open from score thirds), stub flag, and the
  portrait image as a data URL. Optional `?branch_id=` scores that
  branch instead of the server-active one. 404 for unknown sessions
  or branches.

## Run with the live model (CS-6)

The server speaks to Muse Spark instead of the scripted
character/coach when BOTH variables are set (any other combination
stays scripted):

```bash
cd ~/workspace/hackathon-conversation-sparring
META_MODEL_API_KEY=<key> META_MODEL_API_BASE=<official base URL> \
  .venv/bin/python -m uvicorn app.server:app --port 8000
```

Optional: `META_MODEL_API_MODEL` (default `muse-spark-1.3`). The base
URL has no default — take it from Meta's official docs. Prefer a
gitignored `.env` file over inline env vars so the key never lands in
shell history. Scoring stays deterministic (the judge never calls the
model); only the character's voice and the coach's whispers change.

## Portrait (CS-7, stub — not a live render)

`GET /sessions/{id}/portrait` returns the character portrait for a
branch's score: `{"expression", "stub": true, "image"}` where `image`
is an SVG data URL. By default it scores the server-active branch;
`?branch_id=` scores the named branch instead (the UI passes its own
active branch so click-to-switch re-renders the portrait too).
Expression follows score thirds —
0–2/7 guarded, 3–4/7 softening, 5–7/7 open — so progress shows as a
face as well as a number. The UI shows it under the score with a
stub caption; servers without the endpoint simply hide the panel.

The generator is a deterministic labeled-SVG stub: no network, no
key, clearly marked in-image, in the UI caption, and here. Nothing
about it is presented as a real Muse Image render. Live swap notes
(for when the user confirms an image endpoint and key — none is
assumed, and the Meta chat key is NOT assumed to work for image):
model muse-image-1.0 via the Responses API per Meta's official
cookbook (meta-models/meta-model-cookbook 05_muse_image), refining
one base portrait per expression state with previous_response_id;
per-state instructions are reserved in app/portrait.py
(EXPRESSION_PROMPTS). Swap cost is one $0.01 verification call.

## What is stubbed (read before assuming more)

- **The character is scripted by default, live when configured.** `ScriptedCharacter`
  (in `app/character.py`) is the default: it voices newly revealed
  node text in Alex's voice and deflects otherwise. Everything works
  with no API key and no network. Set both META_MODEL_API_KEY and
  META_MODEL_API_BASE to switch the server to the live model (CS-6).
- **The live client activates only with env config.** `MetaSparkClient`
  (same file) is an OpenAI-compatible chat-completions client. The
  server selects it when configured; the demo and tests never use it live.
  It needs three env vars; the base URL has NO hardcoded default:
  - `META_MODEL_API_KEY` — required; without it, `respond()` raises a
    clear `RuntimeError` (import/construction never crash).
  - `META_MODEL_API_BASE` — required; no default is baked in because
    the base URL was not verified against Meta's docs during this
    build. Set it from Meta's official docs when wiring the live model.
  - `META_MODEL_API_MODEL` — default `muse-spark-1.3`.
  - The key lives in the gitignored `.env` (repo root) when present;
    never commit one.
- **The classifier is rule-based v1** (`app/classify.py`): meaning
  keywords checked first, then closed-question patterns (auxiliary
  starters, tag questions), then wh-word open questions, default open.
  Its heuristic and known limits are documented in its docstring. The
  Day 3/4 coach agent consumes its output (it was not replaced); the
  `classify(text)` interface
  stays identical.
- **One scenario only** (`scenarios/teammate.json`): the teammate who
  keeps missing deadlines, 7 nodes. Scenarios 2–3, coach, rewind/
  branches, voice, and portraits are explicitly out of
  scope for Days 1–2; coach and rewind/branches landed in Days 3–4.
  Scenarios 2–3 and voice are still not built; portrait plumbing
  landed in CS-7 with a labeled stub (live render pending endpoint
  and key confirmation).
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

## Day 3/4 build (coach + rewind)

The contract for this build is `SPEC-day3-4.md`. All Day 1/2 behavior
is preserved: the Day 1/2 suite passes unmodified in intent and the
proof numbers (closed-only 2/7, good run 7/7) are unchanged.

- **Coach** (`app/coach.py`): `RuleCoach` (default, no key, no
  network) rewrites stalled closed questions as open ones and answers
  stalled open questions with a rotating meaning framing; `SparkCoach`
  calls Muse Spark through the `MetaSparkClient` pattern and is inert
  without a key. The coach whispers AFTER a stalled turn only, stays
  silent on reveals (no pre-send intercept, no affirmations — the spec
  OPEN questions were resolved to the recommended defaults), and never
  receives unrevealed text or gate info. Stalled turns append a 5th
  decision record (`coach_whisper`).
- **Branches** (`app/session.py`, `app/server.py`): a session holds
  branches plus an active id; Day 1/2 is branch `"main"`. Rewind
  copies turns/decisions `[0..N-1]`, recomputes revealed as the union
  of `newly_revealed`, and scores each branch independently. Labels
  are derived ("Main", "Branch B (from turn N)").
- **UI** (same page): whisper panel with a rewind button on stalled
  turns, branch tree with per-branch scores and click-to-switch, score
  and revealed list following the active branch. Switching renders
  from a client-side branch cache, so it needs no new endpoint; when
  the branch endpoints are absent the page behaves as the Day 1/2 UI.
- **Verified:** 108 pytest passed; demo prints `DEMO OK` (rewind run:
  bad branch 2/7 with whisper, branch B 7/7, main still 2/7); a
  headless full playthrough against the live server passed with zero
  page errors (Day 1/2 fallback path code-reviewed only; no
  real-browser visual pass yet).
- **Still stubbed:** voice, live portrait renders (stub in place), scenarios 2–3,
  session persistence to disk, live LLM calls in tests.
