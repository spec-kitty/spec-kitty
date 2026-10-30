---
description: "Work package task list for mission grep-absence-binary-evidence-01M66F4Y"
---

# Work Packages: grep_absence must judge tracked text and record named evidence

**Inputs**: Design documents from `kitty-specs/grep-absence-binary-evidence-01M66F4Y/` (spec.md, plan.md)
**Prerequisites**: plan.md (required), spec.md (user stories)

**Tests**: The mission is a defect fix; the red-first regression tests are in scope (C-002).

**Organization**: Fine-grained subtasks (`Txxx`) roll up into work packages (`WPxx`).

**Prompt Files**: Each work package references a matching prompt file in `tasks/` under this mission directory.

## Subtask Format: `[Txxx] [P?] Description`

- **[P]** indicates the subtask can proceed in parallel (different files/components).
- Subtasks are **reference rows**, not checkboxes: record completion with `spec-kitty agent tasks mark-status <Txxx> --status done`. The reduced event-log snapshot is the sole subtask-completion authority.

## Path Conventions

- **Single project**: `src/`, `tests/`

---

## Work Package WP01: Binary-safe grep_absence verdict and named evidence (Priority: P1) 🎯 MVP

**Goal**: `_check_grep_absence` skips binary files (`grep -I`) and never records an empty match list on a non-absent verdict (stderr fallback), proven red-first through the real `acceptance-verdict --execute` entry point.
**Independent Test**: With every tracked file free of the pattern and a stale `.pyc` under `__pycache__` containing it, executing the invariant records `confirmed_absent`; a tracked text match still records `still_present` with named evidence.
**Prompt**: `/tasks/WP01-binary-safe-grep-absence.md`
**Requirement Refs**: FR-001, FR-002, FR-003, NFR-001, NFR-002, C-002

### Included Subtasks

T001 Red-first regression test: stale `.pyc` under `__pycache__/` holding the pattern while tracked text is clean must verify `confirmed_absent` through the `acceptance-verdict --negative-invariant --execute` entry point (fails on current `main`)
T002 Same-fixture positive control: a tracked text file containing the pattern still verifies `still_present` with evidence naming the matching file
T003 Evidence fallback test: grep exit 0 with empty stdout and non-empty stderr records evidence including that stderr content
T004 Fix `src/specify_cli/acceptance/matrix.py::_check_grep_absence`: add `-I` to the grep invocation; on exit 0 with empty stdout, fall back to stderr for the evidence
T005 Run the affected acceptance test modules plus lint/type checks; record subtask completion in the event log

### Implementation Notes

- Red-first discipline (DIRECTIVE_034): land T001–T003 as failing tests, run them to prove red, then T004 turns them green. Commit the red tests and the fix per the clean-history rules.
- The test fixture must build the stale-`.pyc` state for real: write a `.py` containing the pattern, `compileall` it (or `py_compile`) so `__pycache__/*.pyc` holds the token, then rewrite the `.py` clean. Assert on GNU grep ≥ 3.5 semantics the way the fixture repo tests in `tests/specify_cli/acceptance/test_negative_invariant_authoring.py` already drive the CLI (`_init_flat_mission`, `acceptance_verdict(...)`).
- Keep the existing evidence truncation discipline: first 5 match lines on stdout matches; 500-char cap on error details.

### Parallel Opportunities

- None: single-file fix; tests and fix are sequential by red-first discipline.

### Dependencies

- None (starting package).

### Risks & Mitigations

- `-I` must not weaken the text search — guarded by T002 (positive control on the same fixture).
- BSD/macOS grep compatibility: `-I` is POSIX-portable across both; CI runs GNU grep.
- Compound-fix vacuity — T001 proves the binary-skip half; T003 proves the stderr-fallback half; reverting either half must turn its test red.

---

## Dependency & Execution Summary

- **Sequence**: WP01 only.
- **Parallelization**: none.
- **MVP Scope**: WP01 is the whole mission.

---

## Requirements Coverage Summary

| Requirement ID | Covered By Work Package(s) |
|----------------|----------------------------|
| FR-001 | WP01 |
| FR-002 | WP01 |
| FR-003 | WP01 |
| NFR-001 | WP01 |
| NFR-002 | WP01 |
| C-001 | WP01 (scope guard, no code) |
| C-002 | WP01 |

---

## Subtask Index (Reference)

| Subtask ID | Summary | Work Package | Priority | Parallel? |
|------------|---------|--------------|----------|-----------|
| T001 | Red-first stale-`.pyc` regression test (`confirmed_absent`) | WP01 | P1 | No |
| T002 | Positive control: tracked text match stays `still_present` with named evidence | WP01 | P1 | No |
| T003 | Evidence fallback test (stderr into evidence on empty stdout) | WP01 | P1 | No |
| T004 | Fix `_check_grep_absence`: `grep -I` + stderr fallback | WP01 | P1 | No |
| T005 | Run affected tests + lint/type checks; record completion | WP01 | P1 | No |
