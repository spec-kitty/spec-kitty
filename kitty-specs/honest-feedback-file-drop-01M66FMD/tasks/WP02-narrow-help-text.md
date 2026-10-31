---
work_package_id: WP02
title: Narrow the --review-feedback-file help contract
dependencies:
- WP01
requirement_refs:
- FR-004
- C-003
planning_base_branch: issue-6699-honest-feedback-file-drop
merge_target_branch: issue-6699-honest-feedback-file-drop
branch_strategy: Planning artifacts for this mission were generated on issue-6699-honest-feedback-file-drop. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6699-honest-feedback-file-drop unless the human explicitly redirects the landing branch.
subtasks:
- T007
- T008
phase: Phase 2 - Documented contract
history:
- at: '2026-10-30T14:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/agent/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/cli/commands/agent/tasks.py
- tests/specify_cli/cli/commands/agent/fixtures/tasks_cli/help/move-task.help
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Narrow the `--review-feedback-file` help contract

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match.

## ⚠️ IMPORTANT: Review Feedback

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`). Address all feedback before complete; record changes with `spec-kitty agent tasks add-history WP02 --note "..."`.

## Review Feedback

*(If this WP was returned from review, the reviewer feedback reference appears in the status event log.)*

## Markdown Formatting

Wrap HTML/XML tags in backticks: `<div>`, `<script>`
Use language identifiers in code blocks: `python`, `bash`

## Objectives & Success Criteria

The `--review-feedback-file` help text in `move-task --help` states that the flag is refused on edges that write no review cycle, so the documented contract matches the behaviour WP01 enforces (FR-004). The golden `--help` fixture matches the rendered help (C-003).

## Context & Constraints

- The help lives in the Typer option annotation for `review_feedback_file` in `src/specify_cli/cli/commands/agent/tasks.py` (the registration shim owns the byte-frozen `--help` surface).
- Current text ends: "On --to approved/done its content is recorded when the move writes a new approval review-cycle record; otherwise a warning on stderr says it was not recorded (JSON stdout is unchanged)." — keep that, append one sentence naming the refusal, e.g. "On every other edge the move is refused: no review cycle is written there, so the file would be validated and then dropped."
- The golden fixture `tests/specify_cli/cli/commands/agent/fixtures/tasks_cli/help/move-task.help` pins the rendered help; regenerate it the way its test does (find the fixture test with `grep -rn "move-task.help" tests/` and follow its update mechanism — do not hand-edit blindly; the file must equal the rendered `--help` exactly).
- No other doc restates the old claim (verified during planning: `docs/api/agent-subcommands.md`, `docs/architecture/kanban-workflow.md`, `docs/guides/how-to/missions/review-work-package.md`, `docs/development/how-to/review-gates.md` show rejection-edge usage only). The changelog entry is authored at mission wrap-up, not here.

## Branch Strategy

- **Strategy**: single lane, sequential after WP01
- **Planning base branch**: `issue-6699-honest-feedback-file-drop`
- **Merge target branch**: `main`

> Populated by `spec-kitty agent mission finalize-tasks`. Do not change manually.

## Subtasks & Detailed Guidance

### Subtask T007 – Narrow the help paragraph

- **Purpose**: FR-004.
- **Steps**: edit the `help=(...)` string of the `review_feedback_file` option in `src/specify_cli/cli/commands/agent/tasks.py`; append the refusal sentence naming the recording edge families.
- **Files**: `src/specify_cli/cli/commands/agent/tasks.py`.
- **Parallel?**: No.

### Subtask T008 – Update the golden fixture

- **Purpose**: C-003 — the fixture must equal the rendered help.
- **Steps**: regenerate `tests/specify_cli/cli/commands/agent/fixtures/tasks_cli/help/move-task.help` from the real `--help` output (follow the fixture test's mechanism); both changes land in one commit.
- **Files**: `tests/specify_cli/cli/commands/agent/fixtures/tasks_cli/help/move-task.help`.
- **Parallel?**: No.

## Test Strategy

- `uv run pytest` on the help-fixture test (find it via `grep -rn "move-task.help" tests/specify_cli/cli/commands/agent/`) — green.
- Render `uv run spec-kitty agent tasks move-task --help` and eyeball the new sentence.

## Risks & Mitigations

- Fixture/source drift → both files change in one commit; the fixture test fails on any drift.

## Review Guidance

- The help names: required on review-rejection edges; recorded-or-warned on approval edges; refused elsewhere.

## Progress & Status

- **Record a progress note**: `spec-kitty agent tasks add-history WP02 --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task WP02 --to <status>`
- **View history and status**: `spec-kitty agent tasks status`
