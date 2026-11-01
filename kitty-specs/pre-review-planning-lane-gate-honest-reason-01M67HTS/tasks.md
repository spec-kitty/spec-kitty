# Work Packages: An honest pre-review gate reason for a planning-lane WP

**Inputs**: Design documents from `kitty-specs/pre-review-planning-lane-gate-honest-reason-01M67HTS/`
**Prerequisites**: plan.md (required), spec.md (user stories), research.md, reasons-canvas.md

**Tests**: Required. This is a defect fix: the reproduction test must fail through the
real `move-task --to for_review` entry point before the production edit (charter,
ATDD-First Discipline).

**Organization**: Two work packages. WP01 carries the red-first reproduction, the
production fix and the same-fixture control. WP02 carries the operator-facing record
(changelog + review-gates how-to).

**Prompt Files**: `kitty-specs/pre-review-planning-lane-gate-honest-reason-01M67HTS/tasks/`

## Subtask Format: `[Txxx] [P?] Description`

- **[P]** indicates the subtask can proceed in parallel (different files/components).
- Subtasks are **reference rows**, not checkboxes: record completion with
  `spec-kitty agent tasks mark-status <Txxx> --status done`.

## Path Conventions

- Single project: `src/specify_cli/`, `tests/`.

---

## Work Package WP01: The record tells the truth for a planning-lane WP (Priority: P1) 🎯 MVP

**Goal**: A planning-lane WP that committed on the target branch records a `no_coverage`
verdict whose reason names the planning lane and states the committed diff was not
inspected — with no dispatch, no test run and no block — while a code-change WP with an
empty diff keeps today's wording.
**Independent Test**: The new test module drives the production `move-task --to for_review`
on a real git fixture whose HEAD is the target branch; the planning arm asserts the new
reason, the control arm asserts the old one, and a dispatch spy asserts the cheap skip.
**Prompt**: `tasks/WP01-planning-lane-gate-reason.md`
**Requirement Refs**: FR-001, FR-002, FR-003, FR-004, NFR-001, NFR-002, NFR-003, C-001, C-002

### Included Subtasks

T001 Survey the empty-diff arm and every planning-lane authority; record campsite notes and the exact call graph the fix will touch
T002 [P] Write the failing reproduction in `tests/specify_cli/cli/commands/agent/test_tasks_move_task_pre_review_planning_lane_reason.py` and run it RED on the pre-fix code
T003 [P] Add the same-fixture code-change control arm and the no-dispatch assertions to the same module
T004 Implement `_mt_pre_review_planning_lane_wp` and `_mt_empty_changed_files_reason` in `src/specify_cli/cli/commands/agent/tasks_move_task_gates.py` and wire the empty-diff arm
T005 Run the new module plus the two neighbouring pre-review gate modules and record the counts
T006 Run the project's lint/type checks on the two touched Python files

### Implementation Notes

- The classification asks the declared `execution_mode` first, then `lanes.json` lane
  membership through `is_planning_lane`; a corrupt/absent `lanes.json` degrades to today's
  wording (research.md D-6).
- The empty-diff arm keeps its existing position and its existing verdict construction;
  only the reason string is selected by the new helper.
- Do not touch binding resolution, scope selection, dispatch or aggregation.

### Parallel Opportunities

- T002 and T003 are files-disjoint from nothing (same new test file) — write them in one
  pass; T006 can run while the reviewer reads the diff.

### Dependencies

- None.

### Risks & Mitigations

- A mocked changed-file helper would not reproduce the bug → use a real git repo.
- Lane-membership-only classification would mislabel a `single_branch` code WP →
  declared `execution_mode` wins.

---

## Work Package WP02: The operator-facing record explains the new wording (Priority: P2)

**Goal**: The changelog and the review-gates how-to state what the gate now records for a
planning-lane WP, extending (not contradicting) the inherited-limitation note.
**Independent Test**: `docs/changelog/CHANGELOG.md` carries an `[Unreleased]` entry with the
`(#6792)` reference and before/after, and `review-gates.md` describes the planning-lane
reason next to the existing inherited-limitation note.
**Prompt**: `tasks/WP02-docs-and-changelog.md`
**Requirement Refs**: FR-001, NFR-003

### Included Subtasks

T007 Add the `[Unreleased]` changelog entry under `docs/changelog/CHANGELOG.md`
T008 Extend the pre-review gate section of `docs/development/how-to/review-gates.md` with the planning-lane reason
T009 Run the docs freshness check and the terminology gate over the touched docs

### Implementation Notes

- Changelog shape: bold impact-first lead ending with `(#6792)`, then before/after, under
  1,200 characters.
- The how-to section already says the working-tree-diff limitation is inherited and
  unfixed; the new text says the *reason* for a planning-lane WP is now honest, and must
  not claim the gate inspects the committed diff.

### Parallel Opportunities

- T007 and T008 touch different files.

### Dependencies

- Depends on WP01 (the wording it documents).

### Risks & Mitigations

- Documentation drift → quote the shipped reason string verbatim from the code.

---

## Dependency & Execution Summary

- **Sequence**: WP01 → WP02.
- **Parallelization**: none worth splitting; the mission is deliberately two packages.
- **MVP Scope**: WP01 alone delivers the fix; WP02 completes the operator-facing record.

---

## Requirements Coverage Summary

| Requirement ID | Covered By Work Package(s) |
|----------------|----------------------------|
| FR-001 | WP01, WP02 |
| FR-002 | WP01 |
| FR-003 | WP01 |
| FR-004 | WP01 |
| NFR-001 | WP01 |
| NFR-002 | WP01 |
| NFR-003 | WP01, WP02 |
| C-001 | WP01 |
| C-002 | WP01 |
| SC-001 | WP01 |
| SC-002 | WP01 |
| SC-003 | WP01 |
| SC-004 | WP01 |

---

## Subtask Index (Reference)

| Subtask ID | Summary | Work Package | Priority | Parallel? |
|------------|---------|--------------|----------|-----------|
| T001 | Survey the empty-diff arm and planning-lane authorities | WP01 | P1 | No |
| T002 | Failing reproduction test through `move-task --to for_review` | WP01 | P1 | Yes |
| T003 | Code-change control arm and no-dispatch assertions | WP01 | P1 | Yes |
| T004 | Implement the classification and reason selection | WP01 | P1 | No |
| T005 | Target module test run | WP01 | P1 | No |
| T006 | Lint/type check the touched files | WP01 | P1 | Yes |
| T007 | Changelog `[Unreleased]` entry | WP02 | P2 | Yes |
| T008 | `review-gates.md` planning-lane paragraph | WP02 | P2 | Yes |
| T009 | Docs freshness + terminology checks | WP02 | P2 | No |
