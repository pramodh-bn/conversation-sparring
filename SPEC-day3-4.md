# Conversation Sparring — Day 3/4 build spec (coach + rewind)

Goal: add the coach agent and the branch/rewind UI to the Day 1/2 core
loop, same stack, same scenario (teammate only), text mode only.
This spec was produced by a grill-me deep dive: every decision below
was either resolved from the write-up / codebase (cited) or is flagged
OPEN for Pramodh. Nothing here is guessed silently.

Parent spec: `SPEC.md` (Day 1/2). Write-up:
`~/workspace/your_files/meta-hackathon-conversation-sparring-writeup.md`.

## Deliverable (must all be true when the build lands)

- `python -m pytest` green, including the Day 1/2 proof numbers
  unchanged (closed-only run ≤3/7, good run ≥6/7, on the main branch).
- A scripted rewind demo runs end to end: bad branch stalls at 2/7,
  coach whispers, rewind forks a new branch from the stalled turn, good
  questions on the new branch reach ≥6/7, original branch still 2/7.
- Web UI: coach whisper panel + rewind button on stalled turns,
  branch tree with per-branch scores, branch switching.
- Works with NO API key (rule-based coach v1 default; LLM coach inert
  without a key, same pattern as the Day 1/2 character).

## Decisions resolved from evidence (grill-me, codebase-first)

### 1. Coach timing: whisper AFTER a stalled turn, paired with rewind
- Evidence: the write-up's demo script is "bad run → rewind to the turn
  where it went wrong → better run". A pre-send intercept would kill
  the rewind money shot and complicate the UI.
- Rule: after each turn, if the turn revealed nothing, the coach may
  whisper. If the turn revealed a node, the coach stays silent (the
  user is already on track; silence keeps the demo tight).
- OPEN (Pramodh): confirm post-turn whisper, or pre-send intercept?

### 2. When the coach speaks: stalled turns only
- Evidence: coaching value lives in the failure mode (closed questions
  that deflect). Whispering on every turn is noise.
- Rule: whisper only when `newly_revealed` is empty. Direction depends
  on question type: closed → open rewrite; open-but-blocked (next node
  is meaning-gated) → meaning rewrite. The coach does NOT know which
  node is next; the meaning rewrite is generic (see §4).

### 3. Coach implementation: two layers, one interface
- Evidence: no Meta Model API key exists yet (Day 1/2 README), but
  eligibility requires meaningful Meta API use by submission, and the
  Day 1/2 character already uses the scripted-default / model-inert
  pattern.
- Interface: `CoachAgent.suggest(coach_view) -> str | None`, where
  `coach_view` = {user_text, question_type, revealed_anything: bool,
  score, revealed_titles}.
- `RuleCoach` (DEFAULT, no key, no network): template rewrites.
  `SparkCoach`: Muse Spark via the existing `MetaSparkClient` pattern,
  same env config; inert without a key; tested with mocked HTTP only.
- The `classify(text)` interface from Day 1/2 is unchanged; the coach
  consumes its output, it does not replace it.

### 4. Rule-based rewrites (v1, template banks, no graph access)
- Closed → open: transform the yes/no question into a wh-question.
  Examples: "Did you miss the deadline again?" → "What happened with
  the deadline?"; "Is the report finished yet?" → "What's going on
  with the report?". Fallback when no template matches: "What would
  you say is going on here?"
- Open-but-blocked → meaning: generic meaning framing, fixed bank:
  "How did that feel?", "What worries you most about this?",
  "What matters most to you here?" (rotate or pick first; deterministic
  for tests).
- NO-LEAK INVARIANT (same as the character): the coach never receives
  unrevealed node text, node titles beyond revealed ones, or gate
  information. Its rewrites are generic by construction, so they cannot
  leak the answer. Test this with a probe: whisper text must not
  contain any unrevealed node text.

### 5. Branch / rewind model
- Evidence: write-up says "Rewind copies the transcript up to turn N
  and forks a new branch; the branch tree is visible in the UI."
- `Branch` = {id, parent_branch_id, fork_turn_index, turns[],
  revealed set, decisions[]}. A `Session` holds `branches: dict` plus
  an `active_branch_id`. The Day 1/2 single-branch behavior becomes
  branch `"main"`.
- Rewind = copy turns + decisions up to turn N from the source branch
  (turns are 0-indexed; copying up to N means keeping turns [0..N-1],
  i.e. the state BEFORE turn N), recompute revealed as the union of
  `newly_revealed` across copied turns (reveal is deterministic from
  turns, so no replay through the classifier is needed). The new
  branch's score comes from its own revealed set.
- Branch labels: "Main", "Branch B (from turn N)", etc. — human labels
  derived from fork point, no user-supplied names in v1.

### 6. API (additive — Day 1/2 endpoints keep working)
- `POST /sessions/{id}/messages` gains optional `{branch_id}` (default
  = active branch). Response gains `coach_whisper` (string or null)
  and `branch_id`.
- `POST /sessions/{id}/branches {from_turn, from_branch_id?}` → new
  branch (becomes active). `from_branch_id` defaults to active.
- `GET /sessions/{id}/branches` → branch tree: each branch's id,
  parent, fork point, score, turn count.
- `GET /sessions/{id}` gains a `branches` summary. Decision records
  gain a new kind, `coach_whisper` (input: turn index, output:
  whisper or null), appended after `score` on stalled turns only —
  so non-stalled turns keep exactly 4 records, stalled turns have 5.

### 7. UI (same single page, no framework change)
- Coach whisper panel under the character reply, shown only when a
  whisper exists, with a "Rewind to this turn" button that forks a
  branch from that turn and switches to it.
- Branch tree panel: list of branches with per-branch scores; click
  to switch the active branch; the chat view follows the active
  branch.
- Score display follows the active branch.

### 8. Demo script update
- Extend `scripts/demo_run.py` with a third run: bad branch (closed
  questions) stalls at 2/7 with a coach whisper on a stalled turn;
  rewind to that turn; good questions on the new branch reach ≥6/7;
  assert the original branch is still 2/7. Exit non-zero if any
  assertion fails.

### 9. Tests (must pass)
- Coach unit tests: closed stalled turn → whisper; revealing turn →
  None; open stalled turn → meaning whisper; whisper never contains
  unrevealed node text (probe).
- Branch tests: fork copies the prefix (turns, decisions, revealed);
  branches score independently; forking from turn N keeps turns
  [0..N-1]; main branch proof numbers unchanged.
- API tests: rewind endpoint, branch listing, branch switching,
  message response carries `coach_whisper`.
- All Day 1/2 tests keep passing unmodified in intent (update only
  where the additive response fields require it).

## Out of scope (do NOT build in Day 3/4)
Scenarios 2–3, Muse Image portraits, voice, session persistence to
disk, live LLM coach calls in tests, deployment, GitHub repo work
(the 5 PM push job covers the repo separately).

## Constraints (same as Day 1/2)
- Local files only. Do NOT create GitHub repos, push, or post
  anything anywhere.
- Do NOT ask the user for anything during the build (no API key, no
  decisions). Build so everything works without a key.
- If a spec choice is genuinely unworkable, take the smallest
  deviation, document it in README.md, and keep going.
- Final report must list: files changed/created, test results, demo
  run scores (bad branch, new branch), how to run server + demo,
  what is stubbed, and what the morning review should check.

## OPEN decisions for Pramodh (the grill questions evidence could not answer)
1. Coach timing: post-turn whisper (recommended, per the demo script)
   vs pre-send intercept (coach suggests before the message goes out)?
2. Coach voice: silent on revealing turns (recommended) vs a short
   affirmation ("Good question — that opened something") on reveals?
3. Build authorization: start the Day 3/4 build on this spec?
