---
description: "Work package task list for hermetic legacy-charter Git identity fixtures"
---

# Work Packages: Hermetic legacy-charter Git identity fixtures

**Inputs**: `kitty-specs/legacy-charter-git-identity-01M6TZ9E/spec.md` and `plan.md`
**Prerequisites**: plan.md, spec.md; the completed #7061 investigation is cited by plan.md
**Tests**: Red-first evidence and focused validation are explicitly required by the operator.

## Work Package WP01: Hermetic Git identity fixtures (Priority: P0) 🎯 MVP

**Goal**: Make all three remaining #7061 nodes exercise their intended assertions without ambient Git identity.
**Independent Test**: The exact three nodes move from red to green and the complete four-case matrix passes.
**Prompt**: `/tasks/WP01-hermetic-git-identity.md`
**Requirement Refs**: FR-001, FR-002, NFR-001, C-001, C-002, SC-001, SC-002, SC-003

### Included Subtasks

T001 Reproduce the three issue-reported nodes through the existing pytest entry point and capture the identity failures
T002 Add repository-local `user.name=t` and `user.email=t@t` immediately after `git init` in both affected setups in `tests/specify_cli/migration/test_legacy_charter_gate.py`
T003 Prove the three nodes and four-case matrix green, run the owning file plus targeted lint/format, and add the internal changelog fragment

### Implementation Notes

- Do not change `safe_commit`, production code, global CI identity, or existing assertions.
- Keep the `[True]` early-schema-refusal sibling and all legacy-primary/cache assertions intact.
- Local green is draft-PR evidence only; the merged commit still needs the relevant nightly verification.

### Parallel Opportunities

- None; the WP is intentionally sequential to preserve red-first evidence.

### Dependencies

- None.

### Risks & Mitigations

- Accidental scope growth → inspect the final diff for exactly one test file, Mission artifacts, and one changelog fragment.
- False recovery claim → report the nightly as pending until it runs green on the merged commit.

---

## Dependency & Execution Summary

- **Sequence**: WP01 only.
- **Parallelization**: None.
- **MVP Scope**: WP01 is the complete Mission.

---

## Requirements Coverage Summary

| Requirement ID | Covered By Work Package(s) |
|----------------|----------------------------|
| FR-001 | WP01 |
| FR-002 | WP01 |
| NFR-001 | WP01 |
| C-001 | WP01 |
| C-002 | WP01 |
| SC-001 | WP01 |
| SC-002 | WP01 |
| SC-003 | WP01 |

---

## Subtask Index (Reference)

| Subtask ID | Summary | Work Package | Priority | Parallel? |
|------------|---------|--------------|----------|-----------|
| T001 | Capture exact three-node red evidence | WP01 | P0 | No |
| T002 | Persist repository-local identity in two setups | WP01 | P0 | No |
| T003 | Run focused green validation and changelog | WP01 | P0 | No |
