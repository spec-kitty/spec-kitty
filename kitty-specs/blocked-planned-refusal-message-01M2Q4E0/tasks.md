# Tasks: Source-aware unblock refusal message

**Mission**: blocked-planned-refusal-message-01M2Q4E0 (F-51 / issue #3937)
**Branch**: `issue-3937-blocked-planned-refusal-message`

Single work package: the message edit and its force-proof regression battery are
tightly coupled (splitting them would let a vacuous test slice merge — the exact
failure that cut the prior attempt), so they live in one WP, one lane.

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | RED-first regression matrix in `test_tasks_transition_core.py` (reachability × force, no-rewind-event, positive control, fabricated-feedback) | WP01 | |
| T002 | Source-aware message in `_guard_planned_rollback` (reachability via `allowed_targets()`); guard stays unconditional/force-proof | WP01 | |
| T003 | Prove the matrix green; run blast-radius set + terminology guard + ruff/mypy/format | WP01 | |

## Work Packages

### WP01 — Source-aware `move-task --to planned` refusal (F-51)

**Goal**: Make the refusal source-aware (blocked/canceled/done → legal-targets;
review-family → existing text) without weakening the force-proof gate.

**Priority**: P0 (MVP). **Requirements**: FR-001, FR-002, FR-003, FR-004;
NFR-001, NFR-002, NFR-003, NFR-004.

**Independent test**: `pytest tests/specify_cli/cli/commands/agent/test_tasks_transition_core.py`
— the reachability × force matrix refuses every case with the lane unchanged,
`blocked` names `--to in_progress`, the flagless `done → planned` emits no
forced-rewind event, and the `in_review` + valid-feedback positive control still
succeeds.

**Included subtasks**: T001, T002, T003 (tracked via `spec-kitty agent tasks mark-status`).

**Implementation sketch**:
1. T001 — write the RED matrix first; confirm it fails against today's
   source-agnostic guard (the blocked/canceled/done message assertions fail).
2. T002 — add the reachability branch to `_guard_planned_rollback`; keep the
   four feedback checks and `_GUARDS` order byte-unchanged.
3. T003 — matrix green; run the blast-radius suite, terminology guard, and
   `ruff`/`mypy`/`ruff format`.

**Dependencies**: none. **Risks**: re-opening the `done → planned` resurrection
hole (mitigated by the RED `done`-flagless + `*-with-force` rows and the
no-rewind-event assertion); disturbing the review-family pin (mitigated — the
pin uses `old_lane="in_review"`, a reachable lane, so its text is unchanged).

**Estimated prompt size**: ~320 lines.

**Prompt**: [tasks/WP01-source-aware-refusal.md](tasks/WP01-source-aware-refusal.md)
