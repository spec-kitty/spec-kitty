---
description: "Work package task list — DRG orphan residual live record (#6513)"
---

# Work Packages: DRG orphan residual — a live, non-frozen record

**Inputs**: Design documents from `/kitty-specs/drg-orphan-residual-live-record-01M68ZV0/`
**Prerequisites**: plan.md (required), spec.md (user stories)

**Tests**: The mission is a documentation-truth-up with one additive guard; the guard is written
first and proven red before the record exists (red-first, `DIRECTIVE_034`).

## Path Conventions

- **Single project**: `tests/`, `docs/` (no `src/` change)

## Work Package WP01: Live residual record + membership guard (Priority: P1)

**Goal**: The shipped-graph orphan residual has a live, non-frozen current-state record; the ceiling
gate's message and docstring point at it; and a guard makes the record load-bearing so a silent
ceiling raise or an unrecorded orphan fails a test.
**Independent Test**: `pytest tests/specify_cli/cli/commands/test_doctrine_regenerate_graph.py -q`
passes, including the new guard, with `DOCUMENTED_ORPHAN_RESIDUAL` unchanged at 25; temporarily
dropping or adding a URN in the record's current-state block makes the guard fail naming that URN.
**Prompt**: `/tasks/WP01-live-residual-record-and-guard.md`
**Requirement Refs**: FR-001, FR-002, FR-003, FR-004, FR-005, NFR-001, NFR-002, NFR-003, C-001, C-002, C-003

### Included Subtasks

T001 [P] Extract `_orphan_urns(graph)` in `tests/specify_cli/cli/commands/test_doctrine_regenerate_graph.py` and reduce `_count_orphans` to `len(_orphan_urns(...))` (no behaviour change)
T002 [P] Add `_documented_orphan_urns()` + `LIVE_RESIDUAL_RECORD` and the failing guard `test_documented_residual_matches_measured_shipped_orphans` (red: the record block does not exist yet)
T003 Author the live record section in `docs/architecture/charter-synthesis-drg.md`: method, the 25 URNs in the delimited current-state block grouped by disposition, per-group rationale, ceiling ledger 14 -> ... -> 25 with #6379/#6432 and #6513, pointers to `_INTENTIONAL_ORPHANS` / `_SHIPPED_ORPHANS`, and the frozen-archive note
T004 Retarget `DOCUMENTED_ORPHAN_RESIDUAL`'s docstring pointers and the ceiling assertion message to the live record (constant stays 25; frozen `kitty-specs/` file untouched)
T005 Prove the guard in both directions by temporary mutation (unrecorded orphan; stale recorded row), record the outputs, restore
T006 Add the `[Unreleased]` `### Fixed` changelog entry in `docs/changelog/CHANGELOG.md` with `(#6513)`
T007 Run the touched test module, `check_docs_freshness --ci`, markdownlint on touched docs, and `tests/architectural/test_archive_root_byte_identical.py`

### Implementation Notes

- Red first: T002 before T003. Record the failing output (it names the missing/extra URNs).
- The guard compares sets, not counts, so a shrink must be recorded too (edge case in spec.md).
- The current-state block uses `<!-- drg-orphan-residual:begin -->` / `<!-- drg-orphan-residual:end -->`
  so only that block's backticked URNs count; prose and historical sections cannot satisfy it.
- Do not change `DOCUMENTED_ORPHAN_RESIDUAL`, author a DRG edge, or edit anything under `kitty-specs/`
  other than this mission's own directory.

### Parallel Opportunities

- T001 and T002 are the same file; do them together. T003/T006 (docs) can proceed in parallel with
  T001/T002 once the URN list is recomputed.

### Dependencies

- None (single starting package).

### Risks & Mitigations

- Docs gates (inventory/ToC/spelling) → reuse the already-registered
  `docs/architecture/charter-synthesis-drg.md` page instead of adding a new page; bump `updated:`.
- Guard brittleness → parse one delimited fenced block of URN bullets, not prose or tables.
- Archive-freeze gate → `kitty-specs/` untouched except this mission's own directory; prove with
  `tests/architectural/test_archive_root_byte_identical.py`.
