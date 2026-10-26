# Tasks: Terminality gate judges every issue-matrix row

**Mission**: `issue-matrix-terminality-all-rows-01M5X1ZJ` · **Spec**: [spec.md](spec.md) · **Plan**: [plan.md](plan.md)
**Planning/base branch**: `issue-6653-terminality-all-rows` · **Merge target**: `issue-6653-terminality-all-rows`

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Red-first reader tests: absent at a valid ref → NOT_AUTHORED; probe failures keep their codes | WP01 | |
| T002 | Add `ISSUE_MATRIX_NOT_AUTHORED` and the object-presence leg to `read_issue_matrix_ref_content` | WP01 | |
| T003 | Document the new code (reader docstring, review `ERROR_CODES.md`) and audit code-branching callers | WP01 | [P] |
| T004 | Red-first blocker tests at `done`: uncited row, zero refs with a matrix, approved control | WP02 | |
| T005 | `_issue_matrix_in_mission_rows` over all rows; blocker judges a present matrix with zero refs at `done` | WP02 | |
| T006 | Red-first gate tests: uncited, zero-ref, one-digit, coord post-consolidation present/absent, probe error, PASS text | WP02 | |
| T007 | Terminality gate: zero-ref partition read, NOT_AUTHORED → PASS, judged-row-count PASS detail | WP02 | |
| T008 | `move-task --to done` refusal test with an uncited row, plus `--to approved` control | WP02 | [P] |
| T009 | ADR, reference-doc "What `done` enforces" section, changelog entry | WP02 | [P] |

## Phase 1 — Foundational

### WP01 — Typed "not authored" leg on the coordination ref reader

**Prompt**: [tasks/WP01-reader-not-authored-code.md](tasks/WP01-reader-not-authored-code.md)
**Goal**: `read_issue_matrix_ref_content` tells "the matrix file is absent at a valid ref" apart from every probe failure.
**Priority**: P1 · **Requirements**: FR-003, FR-004, NFR-001, NFR-002, C-004
**Independent test**: `tests/mission_runtime/test_issue_matrix_ref_read.py`, with a valid coordination ref holding no matrix → code `ISSUE_MATRIX_NOT_AUTHORED`.

T001 Red-first reader tests (WP01)
T002 NOT_AUTHORED leg in the reader (WP01)
T003 Docs for the code and caller audit (WP01)

**Dependencies**: none
**Risks**: the presence check must not turn a timeout or an unreadable object into "absent".

## Phase 2 — User stories 1–4

### WP02 — `done` judges every row; the gate reports what it judged

**Prompt**: [tasks/WP02-done-judges-every-row.md](tasks/WP02-done-judges-every-row.md)
**Goal**: at `done`, every `in-mission` row and row diagnostic of a present matrix fails the check, cited or not. A Mission with no matrix still passes. The PASS text names the judged row count. Docs record the rule.
**Priority**: P1 · **Requirements**: FR-001, FR-002, FR-003, FR-005, FR-006, FR-007, C-001, C-002, C-003, C-005, NFR-003
**Independent test**: `tests/policy/test_merge_gates_issue_matrix.py`. The three #6653 variants FAIL in block mode, and the zero-ref no-matrix cases PASS.

T004 Red-first blocker tests (WP02)
T005 Blocker judges every row at done (WP02)
T006 Red-first gate tests (WP02)
T007 Terminality gate reads with zero refs; PASS detail (WP02)
T008 move-task done/approved tests (WP02)
T009 ADR + reference doc + changelog (WP02)

**Dependencies**: WP01
**Risks**: the blocker also serves `approved`, which must not change (C-001). #5222 F1: a fresh coordination Mission with no matrix must PASS.

## MVP

WP01 and WP02 together. WP02 alone closes the `move-task` path and the coord-less gate paths; WP01 is what lets the post-consolidation coordination path stay fail-closed without breaking #5222 F1.
