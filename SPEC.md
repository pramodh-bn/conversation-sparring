# Conversation Sparring — Day 1/2 build spec

Goal: working core loop, text mode, ONE scenario, end to end. No coach,
no rewind, no voice, no images. This is Days 1–2 of the 10-day plan in
`~/workspace/your_files/meta-hackathon-conversation-sparring-writeup.md`.

## Deliverable (must all be true by morning)

- `python -m pytest` green.
- A scripted demo conversation runs end to end: user asks questions,
  character responds in character, score updates, final score computed.
- A local web UI serves a text chat: type a question, see the character
  reply, see score x/7 and revealed nodes.
- Works with NO API key (scripted character default). Real-model client
  present but inert without a key.

## Stack

- Python 3.11+, FastAPI + uvicorn for the server, pytest for tests.
- No database (in-memory + JSON files). Minimal deps, pinned in
  `requirements.txt`.

## Directory layout

```
hackathon-conversation-sparring/
  SPEC.md (this file)
  README.md (how to run, how to test, what is stubbed)
  requirements.txt
  app/
    __init__.py
    graph.py        # scenario graph schema + loading + validation
    classify.py     # v1 rule-based question classifier
    session.py      # state machine: turns, revealed nodes, score
    judge.py        # deterministic scoring from graph + transcript
    decisions.py    # typed decision log (Decision Ledger spine)
    character.py    # CharacterAgent interface + ScriptedCharacter + MetaSparkClient
    server.py       # FastAPI app: chat endpoint, session endpoints, static UI
    static/index.html  # single-page chat UI
  scenarios/
    teammate.json   # the one scenario, 7 nodes
  tests/
    test_graph.py, test_session.py, test_judge.py, test_classify.py,
    test_character.py, test_api.py
  scripts/
    demo_run.py     # scripted conversation printing turns + score
```

## Scenario graph schema (frozen — all workers build to this)

`teammate.json`:

- `scenario_id`, `title`, `character` (`name`, `role`, `persona`,
  `opening_line`).
- `nodes[]`: `id`, `level` (`surface` | `concern` | `value`), `text`
  (what the character reveals when the node opens), `gate` (`any` |
  `open` | `meaning`), `hint` (internal, never shown to the user).
- Exactly 7 nodes. Design the teammate-who-keeps-missing-deadlines arc:
  surface position → workload facts → feelings → real concern → core
  value. Gates: surface nodes open on `any`/`open`; deeper nodes
  require `meaning`. At least 2 nodes must require `meaning`, so
  closed-question-only runs score low.
- Validation rules: ids unique, gates only from the enum, levels in
  order surface → concern → value.

## Question classifier v1 (rule-based, documented as v1)

`classify(text)` returns `closed` | `open` | `meaning`:

- `closed`: yes/no questions, confirmatory/tag questions ("...right?",
  "is it...?", "did you...?").
- `open`: wh-questions (what/how/why/when/where/who) that ask for facts.
- `meaning`: questions about feelings, values, impact, meaning ("how did
  that feel", "what matters most", "what does X mean to you", "what are
  you afraid of", "what would ... mean").
- Document the heuristic and its known limits in `classify.py`'s
  docstring. The coach agent (Day 3/4) will replace this; the interface
  must stay identical.

## State machine + judge (deterministic, no LLM)

- Session: `scenario_id`, `turns[]` (`user_text`, `question_type`,
  `newly_revealed[]`), revealed set.
- On each user turn: classify → check gates of unrevealed nodes in
  order → reveal newly opened nodes → append turn → append typed
  decision records → recompute score.
- Judge: score = revealed_count / 7. No LLM anywhere in scoring. The
  character must never see the score, and the scripted character may
  read revealed state only to voice newly opened nodes — it must never
  leak unrevealed node content.

## Decision log (typed, replayable)

Every turn appends records: `turn_index`, `kind` (`classify` |
`gate_check` | `reveal` | `score`), `input`, `output`. Persist per
session to JSON (a `sessions/` dir or an export endpoint). This is the
Decision Ledger spine; keep the format stable.

## Character

- Interface: `CharacterAgent.respond(session_view, user_text,
  newly_revealed) -> str`.
- `ScriptedCharacter` (DEFAULT): responds in the teammate's voice;
  weaves newly revealed node text into a natural reply; otherwise
  deflects/stays in character without revealing anything new. Must never
  utter unrevealed node content.
- `MetaSparkClient`: OpenAI-compatible chat completions client for the
  Meta Model API. Base URL and model come from env
  (`META_MODEL_API_BASE`, `META_MODEL_API_MODEL` default
  `muse-spark-1.3`). Do NOT hardcode a base URL you cannot verify
  against Meta's docs; if unverifiable, leave base URL env-only with a
  clear README note. Key from env `META_MODEL_API_KEY` only; if absent,
  using it fails with a clear message, never a crash at import. It is
  NOT used by default and NOT needed for tests.

## Web UI

- Single page: chat transcript, input box, score display "x/7", list of
  revealed node titles (not full hidden text), New session button.
- Endpoints: `POST /sessions`, `POST /sessions/{id}/messages {text}`,
  `GET /sessions/{id}`. Serve the static UI from the same app.

## Tests (must pass)

- Graph validation: 7 nodes, unique ids, valid gates/levels, at least 2
  meaning-gated nodes.
- Classifier spot checks: at least 3 examples per class, including the
  demo's key questions.
- Session: a closed-question-only scripted run scores LOW (≤3/7); a
  good-question run scores HIGH (≥6/7). These two runs are the demo's
  proof numbers — assert them.
- Judge determinism: same transcript → same score, twice.
- Character: scripted character never leaks unrevealed node text
  (test with a probe).
- API: chat endpoint round-trip works with no API key set.

## Out of scope (do NOT build tonight)

Coach agent, rewind/branches, voice, Muse Image portraits, scenarios
2–3, deployment, GitHub repo creation, any external network calls in
tests.

## Constraints

- Local files only. Do NOT create GitHub repos, push, or post anything
  anywhere.
- Do NOT ask the user for anything (no API key, no decisions). Build so
  everything works without a key.
- If a design choice in this spec is genuinely unworkable, pick the
  smallest deviation, document it in README.md, and keep going.
- Final report must list: files created, test results, how to run the
  server + demo script, what is stubbed, and what the morning review
  should check.
