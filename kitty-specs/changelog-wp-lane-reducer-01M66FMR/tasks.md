---
description: "Work package task list for changelog-wp-lane-reducer-01M66FMR"
---

# Work Packages: Changelog WP acceptance reads the canonical lane

**Inputs**: Design documents from `kitty-specs/changelog-wp-lane-reducer-01M66FMR/`
**Prerequisites**: plan.md (required), spec.md, research.md

**Tests**: Red-first regression tests are in scope (the defect is a misclassification; DIRECTIVE_034 test-first bug fixing).

**Organization**: Fine-grained subtasks (`Txxx`) roll up into work packages (`WPxx`). Subtasks are reference rows; completion is recorded with `spec-kitty agent tasks mark-status <Txxx> --status done`.

## Subtask Format: `[Txxx] [P?] Description`

- **[P]** indicates the subtask can proceed in parallel (different files/components).
- Subtasks are **reference rows**, not checkboxes.

## Path Conventions

- Single project: `src/specify_cli/`, `tests/`

---

## Work Package WP01: Route the changelog lane read through the canonical authority (Priority: P1) 🎯 MVP

**Goal**: `release/changelog.py` decides WP acceptance from the reduced lane over the resolved status surface, failing loudly on corrupt logs, with red-first tests.
**Independent Test**: `uv run pytest tests/release/test_release_prep.py` — new ordering/coordination/corrupt-log tests pass, all pre-existing tests unchanged.
**Prompt**: `/tasks/WP01-canonical-lane-read.md`
**Requirement Refs**: FR-001, FR-002, FR-003, FR-004, NFR-001, NFR-002, C-001, C-002

### Included Subtasks

T001 Red test: out-of-order log — file order disagrees with reducer order; changelog must follow the reducer
T002 Red test: coordination topology — authoritative log on the coord surface beats the stale primary copy
T003 Red test: corrupt log line — `build_changelog_block` raises the canonical store error
T004 Implement the fix: resolve the status surface through `placement_seam(...).read_dir(STATUS_STATE)` and read the lane via `get_wp_lane`, with the failure policy from plan.md D-2
T005 Verify: full `tests/release/` suite, the status/lane-reader tests that share the seams, ruff and mypy on changed files

### Implementation Notes

- Red-first: T001–T003 are written and shown failing on the pre-fix tree before T004.
- The private helpers change signature (`repo_root` threaded in); no external importers exist (verified in research.md).
- Failure policy arms (plan.md D-2): no canonical surface / unmaterialized coord worktree → legacy fallback (never the stale primary copy); no event log or WP absent from snapshot → frontmatter fallback; `StoreError` and `CoordinationBranchDeleted` propagate.

### Parallel Opportunities

- T001 and T003 touch only the test file and can be authored together; T002 needs its git fixture.

### Dependencies

- None (starting package).

### Risks & Mitigations

- Regression on legacy missions → T005 keeps every pre-existing `tests/release/` test unchanged (SC-004).
- Read-side bypass gate (`tests/architectural/test_no_read_side_bypass.py`) → route only through the sanctioned seams; run the gate.

---

## Work Package WP02: Changelog entry and G-13 doc update (Priority: P2)

**Goal**: The user-facing change is recorded in `docs/changelog/CHANGELOG.md` under `[Unreleased]`, and gap G-13 in the event-ledger doc reflects the closed changelog item.
**Independent Test**: `docs/changelog/CHANGELOG.md` carries a bold impact-first lead with `(#6612)`; the G-13 row no longer lists `release/changelog.py` as an open raw reader.
**Prompt**: `/tasks/WP02-changelog-and-docs.md`
**Requirement Refs**: FR-001, FR-002, FR-003

### Included Subtasks

T006 [P] Author the `[Unreleased]` changelog entry (bold impact-first lead with `(#6612)`, before/after, under 1,200 characters)
T007 [P] Update the G-13 row and the readers table in `docs/architecture/event-ledger-writers-and-readers.md`

### Implementation Notes

- The changelog entry documents the behavior change (corrupt logs now fail the changelog build loudly).
- The readers table's "changelog acceptance" row moves from "raw `json.loads` loop … last `to_lane` in file order" to the reducer column.

### Parallel Opportunities

- T006 and T007 are independent files.

### Dependencies

- Depends on WP01 (the entry describes the landed behavior).

### Risks & Mitigations

- Docs drift → run the docs freshness checks if any index-visible page changes (none expected; both files are already indexed).

---

## Dependency & Execution Summary

- **Sequence**: WP01 → WP02.
- **Parallelization**: Within WP01, T001–T003 test authoring; within WP02, T006 ∥ T007.
- **MVP Scope**: WP01 alone fixes the defect; WP02 records it.

---

## Requirements Coverage Summary

| Requirement ID | Covered By Work Package(s) |
|----------------|----------------------------|
| FR-001 | WP01 |
| FR-002 | WP01 |
| FR-003 | WP01 |
| FR-004 | WP01 |
| NFR-001 | WP01 |
| NFR-002 | WP01 |
| C-001 | WP01, WP02 |
| C-002 | WP01 |

---

## Subtask Index (Reference)

| Subtask ID | Summary | Work Package | Priority | Parallel? |
|------------|---------|--------------|----------|-----------|
| T001 | Red test: reducer order beats file order | WP01 | P1 | Yes |
| T002 | Red test: coordination surface beats stale primary copy | WP01 | P1 | No |
| T003 | Red test: corrupt log fails loudly | WP01 | P1 | Yes |
| T004 | Implement canonical lane read | WP01 | P1 | No |
| T005 | Verify suites, ruff, mypy | WP01 | P1 | No |
| T006 | Changelog entry | WP02 | P2 | Yes |
| T007 | G-13 doc row update | WP02 | P2 | Yes |
