---
work_package_id: WP04
title: move-task CLI ergonomics + docs
dependencies: []
requirement_refs:
- FR-005
- FR-008
- FR-009
- NFR-005
planning_base_branch: fix/move-task-approval-ergonomics
merge_target_branch: fix/move-task-approval-ergonomics
branch_strategy: Planning artifacts for this mission were generated on fix/move-task-approval-ergonomics. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/move-task-approval-ergonomics unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-move-task-approval-ergonomics-01M302R0
base_commit: 10ae3c96d70d788b64593857ece9e789567c9e99
created_at: '2026-09-20T19:39:29.115677+00:00'
subtasks:
- T015
- T016
- T017
phase: Phase 1 - Implementation
history:
- at: '2026-09-20T19:15:00Z'
  actor: system
  action: Prompt generated for move-task-approval-ergonomics mission
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/agent/
create_intent:
- tests/specify_cli/cli/commands/test_move_task_flag_aliases.py
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- src/specify_cli/cli/commands/agent/tasks.py
- tests/specify_cli/cli/commands/test_move_task_flag_aliases.py
role: implementer
tags: []
task_type: implement
tracker_refs:
- '3469'
---

# Work Package Prompt: WP04 – move-task CLI ergonomics + docs

## ⚡ Do This First: Load Agent Profile

Load the `python-pedro` profile (role: implementer) via the profile-load skill first. Then read
`spec.md`, `plan.md`, and `quickstart.md`. This WP is independent — it shares no files with the
issue-matrix spine and can start immediately.

## Objective

Remove the move-task flag friction: accept the natural `--actor`/`--reason` flags (the names the
sibling `issue-verdict` already uses), fix the stale `--assignee` help string, and point operators at
`mark-status` for subtask completion (the checkboxes are inert by design, #2816 — guidance only).

## Context (grounding — verify anchors; they may have drifted)

- `src/specify_cli/cli/commands/agent/tasks.py` (anchors VERIFIED) — `move-task` is defined HERE (not
  tasks_move_task.py): `@app.command(name="move-task")` L657, `def move_task(...)` L658, `--agent` L662,
  `--assignee` L675 (stale help confirmed verbatim: "Assignee name (sets assignee when moving to
  doing)"), `--note` L677. Flags feed the handler via `_MoveTaskArgs(agent=..., assignee=..., note=...)`
  at L781/785/787. (tasks_move_task.py holds only the `_do_move_task` orchestrator — leave it.)
- **Typer multi-name Option pattern to copy** (the one existing example in the codebase):
  `cli/commands/init.py:787` — `typer.Option(False, "--non-interactive", "--yes", help=...)`. Add
  `"--actor"` as a second name on the `--agent` Option and `"--reason"` on the `--note` Option.
- The sibling `issue-verdict` (`agent/issue_verdict.py`) uses `--actor`. Reconciliation is
  one-directional: add `--actor` (alias of `--agent`) and `--reason` (alias of `--note`) to
  `move-task`. `issue-verdict` has no `--note`/`--reason` concept — do NOT add one there.
- Subtask completion is event-sourced (`tasks_shared.py` ~L501–572, #2816). **Do NOT** touch that code
  path or re-read `tasks.md` checkboxes (C-001). The guidance is help-text/error-text only.

## Subtasks

### T015 — Red-first regression test (RED first)
`tests/specify_cli/cli/commands/test_move_task_flag_aliases.py`, `@pytest.mark.regression`, pinned
`#3469`. Assert (RED on current main): `move-task WP01 --to doing --actor claude --reason "x"`
succeeds and applies the same values as `--agent claude --note "x"`. Include a test that `--agent`/
`--note` still work (no regression).

### T016 — Add `--actor`/`--reason` aliases
Add `--actor` as an alias of `--agent` and `--reason` as an alias of `--note` on `move-task` (Typer:
add the alias names to the same `Option`, or add hidden secondary options that feed the same
parameter). Ensure exactly one value wins if both spellings are passed (document precedence; prefer
erroring on conflict, else last-wins with a note). Keep `--mission` as the canonical selector; do NOT
add any `--feature` flag (terminology canon, C-004).

### T017 — Fix `--assignee` help + inert-checkbox guidance
Correct the `--assignee` help string to describe the actual any-lane behavior. Add concise guidance
(in `move-task` help and/or the "unchecked subtasks" error path reachable from this command) stating
that `tasks.md` checkboxes are not the completion source of truth and pointing at
`spec-kitty agent tasks mark-status`. Guidance only — no behavior change to the gate.

## Branch Strategy

Planning base `fix/move-task-approval-ergonomics`; independent lane; merges back to the same branch
(then upstream `main` via PR). Worktree per computed lane from `lanes.json`.

## Test Strategy (ATDD / red-first — required)

T015 RED first through the `move-task` CLI entry point, pinned `#3469`, GREEN after aliases land.
Targeted: `PWHEADLESS=1 .venv/bin/python -m pytest tests/specify_cli/cli/commands/ -q -k "move_task"`.
**NFR-002 non-regression:** run the existing #2816 event-sourced subtask-completion guards as
blast-radius and confirm they stay green — the inert-checkbox guidance must not alter that path.

## Definition of Done

- `move-task --actor/--reason` work identically to `--agent`/`--note`; both spellings coexist.
- `--assignee` help matches actual behavior; inert-checkbox guidance points at `mark-status`.
- No change to the #2816 subtask-completion code path.
- T015 RED→GREEN; ruff + mypy --strict clean; complexity ≤15.

## Reviewer Guidance

Confirm no `--feature` introduced. Confirm the #2816 path is untouched (guidance only). Confirm both
flag spellings work and conflict handling is sane. Confirm `issue-verdict` was not given a spurious
`--reason`.
