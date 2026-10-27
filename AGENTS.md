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

## Finding these rules

`AGENTS.md` is the shared source of truth. `CLAUDE.md` points here for Claude.
When starting Muse or another tool that does not automatically read `AGENTS.md`,
include an instruction in its initial task prompt to read this file first.
