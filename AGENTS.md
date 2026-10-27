# Shared rules for Codex, Claude, Muse, and other coding agents

Read this file before working in this repository. These rules apply to all
agents, regardless of the tool used. Explicit user instructions take precedence.

## Isolate each agent's work

- Use a separate Git worktree and task branch for each agent. Separate branches
  in a shared working directory do not isolate files.
- Do not edit on `main`, switch another agent's working directory to a different
  branch, or reset, clean, stash, overwrite, or discard another agent's changes.
- Suggested sibling worktrees are `../codex`, `../claude`, and `../muse`, with
  branches named `codex/<task>`, `claude/<task>`, and `muse/<task>`.
- Before editing, check the current branch, working tree, and `git worktree list`.
  If the directory is shared with an active agent, create an isolated worktree
  from the agreed integration commit before proceeding.
- Each worktree uses its own local Python environment and configuration. Keep
  `.env` ignored; never put credentials in commits, logs, chat, or Megillah.

## Coordinate ownership in Megillah

- Read the task's full record and recent comments before taking up work.
- Claim the task with a comment naming your agent, branch, worktree, intended
  scope, and files likely to change. Check for an existing owner first.
- Do not take over active work without an explicit handoff or user direction.
- Keep task boundaries narrow. If two tasks need the same file, coordinate who
  owns integration or sequence the edits before modifying it.
- Do not expand into another agent's task without coordinating the handoff.

## Commit and integrate carefully

- Review the diff and stage explicit paths or hunks belonging to your task.
  Avoid blanket staging such as `git add .` or `git add -A`.
- Do not include unrelated changes from another agent in your commit.
- Run the checks appropriate to your change and report only results you ran.
- Use a pull request for integration. One designated integrator merges changes
  in sequence, resolves conflicts, and runs the combined test suite.
- Do not push directly to `main` or merge your own work unless authorized.
- Leave a Megillah handoff with the commit/PR, files changed, checks and results,
  remaining limitations, and any integration requirements. Attach test evidence
  when the task requires it. Never include secrets.

## Attribute changes and follow up on issues

- Use the stable agent names `Codex`, `Claude`, and `Muse` consistently. Name
  the agent that actually made each change; the human Git author alone is not
  sufficient attribution. Keep the user's configured Git author identity.
- Every new agent-created commit must include an `Agent: <name>` trailer and a
  `Megillah-Task: <task-id>` trailer in its commit message. For shared repository
  maintenance without a task, use `Megillah-Task: none (repository maintenance)`.
  Example:

  ```text
  Fix coach session isolation

  Agent: Codex
  Megillah-Task: CS-2
  ```

- PR descriptions and Megillah change summaries must identify the implementing
  agent, task, branch, commits, and affected files. If multiple agents contributed,
  map each agent to their actual changes; do not claim another agent's work.
- Preserve attribution when merging, squashing, or cherry-picking. A combined
  commit must list each contributing agent and explain their respective scope.
- When reporting a defect, use `[Agent: Codex]`, `[Agent: Claude]`, or
  `[Agent: Muse]` in the issue title or Megillah comment, and include the relevant
  task, commit, reproduction steps, expected/actual behavior, and evidence. Base
  attribution on the change history; if uncertain, use `[Agent: Unconfirmed]`
  rather than guessing. Distinguish the implementing agent from the reporter.
- At the start of each work session, check the relevant Megillah task and linked
  issues for your agent tag. A tagged issue is a request to investigate: acknowledge
  it, reproduce or assess it, and record the fix or findings with verification.
  Coordinate with the current task owner before editing their active work.

## Keep Megillah synchronized with changes

- Update the relevant Megillah task after each meaningful change or commit and
  before handing work off, ending a work session, or marking the task delivered.
- Each update must include `Agent: <name>`, a concise change summary and purpose,
  affected files, branch and commit/PR references (or explicitly `uncommitted`),
  checks actually run and their results, and remaining issues or blockers.
- For fixes, link the original issue/comment and state whether it was reproduced
  and how the fix was verified. Attach test output when the task requires it.
- Describe partial work honestly; do not mark a task delivered until its acceptance
  criteria are met. Do not expose credentials in summaries or attachments.
- If Megillah cannot be updated, retain the handoff locally and tell the user the
  task record is out of date; synchronize it when access is restored.

## Agent work journals

- Codex, Claude, and Muse must each keep their own journals in
  `D:\Workspace\meta-hackathon` (the workspace root, outside individual
  repositories/worktrees), using these exact naming patterns:
  - Codex: `codex-journal-YYYY-MM-DD.md`
  - Claude: `claude-journal-YYYY-MM-DD.md`
  - Muse: `muse-journal-YYYY-MM-DD.md`
- Use the user's local date and append entries throughout the day; do not
  overwrite prior history or write entries on another agent's behalf.
- Read your own latest journal when resuming, plus relevant handoffs from other
  agents when coordinating work. Record work performed, decisions,
  affected files, branch and commits, verification results, and outstanding work
  before ending a session. Label retrospective entries and distinguish your
  implementation from changes made by other agents.
- Never record secrets. Journals supplement, rather than replace, required
  Megillah updates. Keep the journal current with each meaningful work increment.

## Finding these rules

`AGENTS.md` is the shared source of truth. `CLAUDE.md` points here for Claude.
When starting Muse or another tool that does not automatically read `AGENTS.md`,
include an instruction in its initial task prompt to read this file first.
