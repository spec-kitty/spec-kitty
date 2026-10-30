---
work_package_id: WP01
title: Refuse --review-feedback-file on non-recordable edges
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- NFR-001
- NFR-002
- C-002
planning_base_branch: issue-6699-honest-feedback-file-drop
merge_target_branch: issue-6699-honest-feedback-file-drop
branch_strategy: Planning artifacts for this mission were generated on issue-6699-honest-feedback-file-drop. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6699-honest-feedback-file-drop unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
phase: Phase 1 - Defect fix
history:
- at: '2026-10-30T14:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/agent/
create_intent:
- tests/specify_cli/cli/commands/agent/test_issue_6699_feedback_file_edges.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/cli/commands/agent/tasks_transition_core.py
- tests/specify_cli/cli/commands/agent/test_issue_6699_feedback_file_edges.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Refuse `--review-feedback-file` on non-recordable edges

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`).
- **You must address all feedback** before your work is complete. Feedback items are your implementation TODO list.
- **Report progress**: As you address each feedback item, record what you changed with `spec-kitty agent tasks add-history WP01 --note "..."`.

## Review Feedback

*(If this WP was returned from review, the reviewer feedback reference appears in the status event log.)*

## Markdown Formatting

Wrap HTML/XML tags in backticks: `<div>`, `<script>`
Use language identifiers in code blocks: `python`, `bash`

## Objectives & Success Criteria

`move-task` must refuse `--review-feedback-file` (exit 1, clear message) on every FSM edge where the flag can never be recorded — neither a review-rejection edge (`is_review_rejection_edge`: any `* → planned`, plus `in_review → in_progress`) nor an approval edge (target `approved`/`done`). On the recordable edge families the behaviour is byte-unchanged. The arbiter-override-into-`approved`/`done` drop of the file keeps its #6652 stderr warning and gains an end-to-end pin.

Success criteria: SC-001..SC-004 of `kitty-specs/honest-feedback-file-drop-01M66FMD/spec.md`; the #6652 tests in `tests/specify_cli/cli/commands/agent/test_tasks_move_task_seam.py` pass unmodified.

## Context & Constraints

- Issue: spec-kitty/spec-kitty#6699. Grounding and the per-edge decision: `kitty-specs/honest-feedback-file-drop-01M66FMD/research.md` (D-1..D-3).
- The two consumers of the resolved file are `persist_rejected_review_cycle_for_rollback` (rejection edges) and `_persist_approved_review_cycle` (approval edges) — both in `tasks_verdict_persistence.py`, NOT owned by this WP (read-only context).
- **C-002 (binding)**: do not add a guard slot to `_GUARDS` and do not reorder it. The new arm is a LEADING arm inside `_guard_feedback_file`. `arbiter_persist_signal`'s prefix slice includes `_guard_feedback_file`; the arm must be inert whenever the target lane is `approved`/`done` (it is, by construction: those are approval lanes).
- **Frozen surfaces**: `is_review_rejection_edge` (#4899 contract), `_planned_rollback_message` texts, the `ReviewOverride` four-field shape, `_mt_resolve_feedback`. None of these change.
- Refusal must fire in pass-1 `decide_transition`, before any lane hop and before any durable write (NFR-001). The OLD-timing persists (`override_persist_signal`, `arbiter_persist_signal`) only arm on approval edges, so a non-recordable-edge refusal writes nothing.
- No new dependencies; Python 3.11; follow CLAUDE.md code rules.

## Branch Strategy

- **Strategy**: single lane, sequential
- **Planning base branch**: `issue-6699-honest-feedback-file-drop`
- **Merge target branch**: `main`

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Subtasks & Detailed Guidance

### Subtask T001 – Red-first e2e: `in_progress → for_review` with the flag refuses

- **Purpose**: the issue's named defect edge; must fail on the pre-fix tree.
- **Steps**: in a new file `tests/specify_cli/cli/commands/agent/test_issue_6699_feedback_file_edges.py`, build a mission with `tests/specify_cli/cli/commands/agent/_rework_loop_harness.py` (`build_mission`, then `move` WP01 to `claimed`, `in_progress`). Write a feedback file. Invoke `move(m, WP, "for_review", IMPLEMENTER, "--review-feedback-file", str(feedback))`.
- **Assertions (all must hold after the fix; all fail before it)**: `result.exit_code == 1`; the output names the `in_progress -> for_review` edge and says the flag is not recorded on it; the WP is still at `in_progress` (no lane hop in `events(m)`); `review_cycle_files(m) == []`.
- **Files**: `tests/specify_cli/cli/commands/agent/test_issue_6699_feedback_file_edges.py` (new).
- **Parallel?**: Yes (with T002–T004).
- **Notes**: run `uv run pytest tests/specify_cli/cli/commands/agent/test_issue_6699_feedback_file_edges.py -q` and confirm it FAILS on the pre-fix tree (exit 0 + no warning today). Keep the red run's output as the red-first proof.

### Subtask T002 – Red-first e2e: `for_review → in_review` with the flag refuses

- **Purpose**: the second named defect edge (reviewer claim edge).
- **Steps**: same fixture via `drive_to_for_review(m)`; invoke `move(m, WP, "in_review", REVIEWER, "--review-feedback-file", str(feedback))`.
- **Assertions**: exit 1; edge named; WP still at `for_review`; no review cycle.
- **Files**: same new test file.
- **Parallel?**: Yes.
- **Notes**: must also fail on the pre-fix tree.

### Subtask T003 – Positive controls on the same fixtures

- **Purpose**: non-vacuity (tactic `acceptance-criteria-non-vacuity`): the same moves without the flag must still succeed.
- **Steps**: in the same tests (same fixture), run the identical moves WITHOUT `--review-feedback-file`; assert exit 0 and the hop happened. Add a control that a rejection edge (`for_review → planned`) still REQUIRES the file (exit 1 without it, success with it) and that an approval edge still records-or-warns (existing #6652 behaviour).
- **Files**: same new test file.
- **Parallel?**: Yes.

### Subtask T004 – E2e pin: arbiter override with the flag

- **Purpose**: FR-003 — pin the arbiter-override drop end-to-end through the real CLI (today only pinned at writer level).
- **Steps**: `build_mission` → `drive_to_for_review` → `reject(m, "for_review_to_planned")`; then `move(m, WP, "approved", REVIEWER, "--force", "--note", "superseded", "--review-feedback-file", str(feedback))`.
- **Assertions**: exit 0; the stderr/output carries `was not recorded`; the event log's `ReviewOverride` delta carries the note-derived reason (`[custom] superseded` shape); `review_cycle_files(m)` shows only the rejection cycle (no fabricated approval cycle); a no-flag control run produces no warning.
- **Files**: same new test file.
- **Parallel?**: Yes.
- **Notes**: this test PASSES on the pre-fix tree (it pins existing behaviour — a ratchet); that is expected and must be stated in the test docstring.

### Subtask T005 – Implement the guard arm + message helper

- **Purpose**: the fix itself.
- **Steps**: in `src/specify_cli/cli/commands/agent/tasks_transition_core.py`, add a pure helper `_feedback_file_no_effect_message(task_id, old_lane, target_lane)` plus the edge predicate (reuse `is_review_rejection_edge` and `_APPROVAL_LANES`; no second source of truth). In `_guard_feedback_file`, BEFORE the exists/is-file checks, refuse when `req.feedback_provided` and the edge is not recordable. The message must: name the WP and the actual `old -> new` edge (alias-resolved), state that no review cycle is written on this edge so the file would be validated and then dropped, name the recording edge families, and suggest removing the flag or using `--note` (NFR-002).
- **Files**: `src/specify_cli/cli/commands/agent/tasks_transition_core.py`.
- **Parallel?**: No (follows T001–T004).
- **Notes**: keep the missing-file and not-a-file messages byte-identical for recordable edges. Update the module's `__all__` only if the repo convention requires exporting the new helper (check the `__all__` Declaration Convention in the charter; helpers consumed only in-module stay private).

### Subtask T006 – Unit tests on the pure guard

- **Purpose**: pin the guard's decision matrix at unit level, cheaply.
- **Steps**: extend the new test file (or the existing pure-core test module that covers `decide_transition` guards — find it with `grep -rn "_guard_feedback_file" tests/`) with a parametrized matrix: rejection edges (refusal does NOT fire), approval edges (does NOT fire), non-review edges (`planned→claimed`, `in_progress→for_review`, `for_review→in_review`, `→blocked`; refusal fires), and the missing-file message still exact on a recordable edge.
- **Files**: `tests/specify_cli/cli/commands/agent/test_issue_6699_feedback_file_edges.py` (unit section) — stay inside `owned_files`.
- **Parallel?**: pairs with T005.
- **Notes**: build `MoveTaskRequest` fixtures the way existing guard tests do.

## Test Strategy

- Mandatory: `uv run pytest tests/specify_cli/cli/commands/agent/test_issue_6699_feedback_file_edges.py -q` green after T005; red before (T001/T002 only).
- Regression: `uv run pytest tests/specify_cli/cli/commands/agent/test_tasks_move_task_seam.py -q` (the #6652 warning tests) green unmodified.
- OLD-timing pins: run the existing arbiter/override partial-write tests that mention `arbiter_persist_signal`/`override_persist_signal` (`grep -rn "arbiter_persist_signal" tests/` → run those files).
- Typed sources changed → run the project's configured typecheck (mypy) on the touched module, matching CI.
- Never run a full heavy suite (NO_FULL_HEAVY_SUITES_IN_MISSION).

## Risks & Mitigations

- Guard-order regression → C-002 discipline + existing OLD-timing tests + T004.
- Message drift from the frozen rejection-edge texts → the new message is a NEW string; never edit `_planned_rollback_message` or the missing-file texts.

## Review Guidance

- Verify the red-first proof (T001/T002 failing pre-fix) is recorded in the WP history.
- Verify the guard arm ordering: edge check before exists/is-file; inert on approval lanes.
- Verify no `_GUARDS` slot was added and no frozen surface changed (`git diff` on `tasks_transition_core.py` should show one helper + one arm + docstring).

## Progress & Status

Progress, history, and status all live in the status event log (`status.events.jsonl`) — never in this prompt file.

- **Record a progress note**: `spec-kitty agent tasks add-history WP01 --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task WP01 --to <status>`
- **View history and status**: `spec-kitty agent tasks status`
