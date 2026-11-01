---
description: "Work package task list for honest-feedback-file-drop-01M66FMD"
---

# Work Packages: honest feedback file drop

**Inputs**: Design documents from `kitty-specs/honest-feedback-file-drop-01M66FMD/`
**Prerequisites**: plan.md (required), spec.md, research.md, reasons-canvas.md

**Tests**: This mission is a defect fix; every WP is test-driven (red-first, DIRECTIVE_034 / ATDD-first).

**Organization**: Fine-grained subtasks (`Txxx`) roll up into work packages (`WPxx`). Each work package is independently deliverable and testable.

**Prompt Files**: Each work package references a matching prompt file in `kitty-specs/honest-feedback-file-drop-01M66FMD/tasks/`.

## Subtask Format: `[Txxx] [P?] Description`

- **[P]** indicates the subtask can proceed in parallel (different files/components).
- Subtasks are **reference rows**, not checkboxes: record completion with `spec-kitty agent tasks mark-status <Txxx> --status done`.

## Path Conventions

- Single project: `src/`, `tests/`

---

## Work Package WP01: Refuse `--review-feedback-file` on non-recordable edges (Priority: P1) 🎯 MVP

**Goal**: `move-task` exits 1 with an edge-naming refusal when `--review-feedback-file` is supplied on an edge that writes no review cycle (neither review-rejection nor approval); rejection/approval edge behaviour is unchanged; the arbiter-override warning is pinned end-to-end.
**Independent Test**: the red-first e2e tests in `tests/specify_cli/cli/commands/agent/test_issue_6699_feedback_file_edges.py` fail on `main` and pass after the guard arm lands; the #6652 tests pass unmodified.
**Prompt**: `kitty-specs/honest-feedback-file-drop-01M66FMD/tasks/WP01-refuse-feedback-file-non-recordable-edges.md`
**Requirement Refs**: FR-001, FR-002, FR-003, NFR-001, NFR-002, C-002

### Included Subtasks

T001 Red-first e2e: `in_progress → for_review` with the flag refuses (exit 1, message, no lane hop, no review cycle)
T002 Red-first e2e: `for_review → in_review` with the flag refuses (exit 1, message, no lane hop)
T003 Positive controls on the same fixtures: the moves succeed without the flag
T004 E2E pin: arbiter override `planned --force → approved` with the flag warns on stderr, records the note, fabricates no approval cycle; no-flag control is silent
T005 Implement the guard arm + message helper in `_guard_feedback_file` (`src/specify_cli/cli/commands/agent/tasks_transition_core.py`)
T006 Unit tests on the pure guard: edge-classification matrix (rejection/approval/non-review), message content, missing-file message unchanged on recordable edges

### Implementation Notes

- Red first: T001–T004 are written and shown failing on the pre-fix tree before T005.
- The guard arm is a LEADING arm inside `_guard_feedback_file`; it must not add a `_GUARDS` slot (C-002).
- Reuse `tests/specify_cli/cli/commands/agent/_rework_loop_harness.py` (do not modify it).

### Parallel Opportunities

- T001–T004 are parallel-safe (one new test file); T005 follows them; T006 pairs with T005.

### Dependencies

- None (starting package).

### Risks & Mitigations

- Guard-order regressions (`arbiter_persist_signal` prefix slice includes `_guard_feedback_file`) → the arm is inert on approval lanes; pinned by the existing OLD-timing tests plus T004.

---

## Work Package WP02: Narrow the `--help` contract (Priority: P2)

**Goal**: the `--review-feedback-file` help text states the refusal on non-recordable edges, and the golden `--help` fixture matches.
**Independent Test**: `uv run pytest` on the help-fixture test is green and the rendered help names the refusal.
**Prompt**: `kitty-specs/honest-feedback-file-drop-01M66FMD/tasks/WP02-narrow-help-text.md`
**Requirement Refs**: FR-004, C-003

### Included Subtasks

T007 Narrow the `--review-feedback-file` help paragraph in `src/specify_cli/cli/commands/agent/tasks.py`
T008 Update the golden fixture `tests/specify_cli/cli/commands/agent/fixtures/tasks_cli/help/move-task.help` in the same change

### Implementation Notes

- Keep the existing sentence structure; append the refusal sentence naming the edge families that record the file.
- No other doc restates the old claim (checked: `docs/api/agent-subcommands.md`, `docs/architecture/kanban-workflow.md`, `docs/guides/how-to/missions/review-work-package.md`, `docs/development/how-to/review-gates.md` all show rejection-edge usage only).

### Parallel Opportunities

- None (two-file, sequential edit + fixture).

### Dependencies

- Depends on WP01 (the text documents the refusal behaviour).

### Risks & Mitigations

- The `--help` surface is golden-fixture-pinned; a fixture-only update without the source change (or vice versa) fails the fixture test — both land in one commit.

---

## Dependency & Execution Summary

- **Sequence**: WP01 → WP02.
- **Parallelization**: WP01's test subtasks are parallel; WP02 follows WP01.
- **MVP Scope**: WP01 alone closes the defect; WP02 completes the documented contract.

---

## Requirements Coverage Summary

| Requirement ID | Covered By Work Package(s) |
|----------------|----------------------------|
| FR-001 | WP01 |
| FR-002 | WP01 |
| FR-003 | WP01 |
| FR-004 | WP02 |
| NFR-001 | WP01 |
| NFR-002 | WP01 |
| C-001 | deferred (follow-up issue; no code) |
| C-002 | WP01 |
| C-003 | WP02 |

---

## Subtask Index (Reference)

| Subtask ID | Summary | Work Package | Priority | Parallel? |
|------------|---------|--------------|----------|-----------|
| T001 | Red-first e2e refusal on `in_progress → for_review` | WP01 | P1 | Yes |
| T002 | Red-first e2e refusal on `for_review → in_review` | WP01 | P1 | Yes |
| T003 | Positive controls without the flag | WP01 | P1 | Yes |
| T004 | E2e arbiter-override warning pin | WP01 | P1 | Yes |
| T005 | Guard arm + message helper | WP01 | P1 | No |
| T006 | Pure-guard unit tests | WP01 | P1 | No |
| T007 | Help text narrowing | WP02 | P2 | No |
| T008 | Golden fixture update | WP02 | P2 | No |
