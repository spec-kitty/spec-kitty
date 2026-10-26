---
description: "Work package task list for the #6454 reach-only fail-closed fix"
---

# Work Packages: Reach-only membership fails closed (#6454)

**Inputs**: Design documents from `kitty-specs/reach-only-fail-closed-01M5WZFY/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md

**Tests**: Required (ATDD red-first, charter C-011).

**Organization**: One work package: the fix is one source module plus its tests; splitting
tests and fix into two lanes would only add a merge for a ~60-line change.

## Subtask Format: `[Txxx] [P?] Description`

- Subtasks are **reference rows**, not checkboxes: record completion with
  `spec-kitty agent tasks mark-status <Txxx> --status done`.

## Path Conventions

- **Single project**: `src/`, `tests/`

---

## Work Package WP01: Reach-only membership falls back, then fails closed (Priority: P1) 🎯 MVP

**Goal**: an unreadable synthesis manifest never re-roots a synthesized tactic or styleguide.
**Independent Test**: the new tests in the two reach-only test modules go red on the base and
green after the fix.
**Prompt**: `tasks/WP01-reach-only-fail-closed.md`
**Requirement Refs**: FR-001, FR-002, FR-003, FR-004, FR-005, FR-006, NFR-001, NFR-002, C-001, C-002, C-003

### Included Subtasks

T001 Red-first tactic tests through `reach_only_ids` and `_load_action_governance_bundle` (WP01)
T002 [P] Red-first styleguide tests through `compiler._direct_root_urns` (WP01)
T003 Commit the failing tests as their own commit (WP01)
T004 Implement manifest → record → fail-closed membership with a WARNING in `reach_only.py` (WP01)
T005 Changelog `[Unreleased]` entry and quality gates (ruff, format, mypy, targeted + blast-radius tests) (WP01)

### Implementation Notes

- Tests first (T001-T003), then the fix (T004), then gates (T005).

### Parallel Opportunities

- T001 and T002 touch different test files.

### Dependencies

- None (starting package).

### Risks & Mitigations

- Warning noise: only read membership when a synthesis-shaped edge of the kind exists (NFR-001).
- Append path drift: keep `_manifest_slugs` lenient (C-002); add a strict reader beside it.

---

## Dependency & Execution Summary

- **Sequence**: WP01 only.
- **MVP Scope**: WP01.

---

## Requirements Coverage Summary

| Requirement ID | Covered By Work Package(s) |
|----------------|----------------------------|
| FR-001 | WP01 |
| FR-002 | WP01 |
| FR-003 | WP01 |
| FR-004 | WP01 |
| FR-005 | WP01 |
| FR-006 | WP01 |
| NFR-001 | WP01 |
| NFR-002 | WP01 |
| C-001 | WP01 |
| C-002 | WP01 |
| C-003 | WP01 |

---

## Subtask Index (Reference)

| Subtask ID | Summary | Work Package | Priority | Parallel? |
|------------|---------|--------------|----------|-----------|
| T001 | Tactic red-first tests | WP01 | P1 | Yes |
| T002 | Styleguide red-first tests | WP01 | P1 | Yes |
| T003 | Commit failing tests | WP01 | P1 | No |
| T004 | Membership fallback + fail-closed + warning | WP01 | P1 | No |
| T005 | Changelog and gates | WP01 | P1 | No |
