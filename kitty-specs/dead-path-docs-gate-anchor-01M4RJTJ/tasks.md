---
description: "Work package task list for mission dead-path-docs-gate-anchor"
---

# Work Packages: Anchor Gate D's dead-path docs regex

**Inputs**: Design documents from `/kitty-specs/dead-path-docs-gate-anchor-01M4RJTJ/`
**Prerequisites**: plan.md (required), spec.md (user stories), research/diagnosis-6096.md

**Tests**: Required — this is a gate-correctness fix; the deliverable is a red-first, self-mutation-proven regression test plus the anchor.

**Organization**: One work package (`WP01`). Fine-grained subtasks (`Txxx`) roll up into it.

## Subtask Format: `[Txxx] [P?] Description`

- **[P]** indicates the subtask can proceed in parallel (different files/components).
- Subtasks are reference rows; record completion with `spec-kitty agent tasks mark-status <Txxx> --status done`.

## Path Conventions

- **Single project**: `src/`, `tests/`. This mission touches only `tests/architectural/`.

---

## Work Package WP01: Anchor Gate D's left boundary (Priority: P1) 🎯 MVP

**Goal**: Stop Gate D's `git grep` regex from matching a `…/src/charter/offering/<kind>/built-in` (or `…/*.graph.yaml`) tail of a longer path, while it still catches a genuine top-level reference — proven red-first and both-ways.
**Independent Test**: `.venv/bin/python -m pytest tests/architectural/test_dead_builtin_doc_paths.py` — the new regression test is RED on the base (over-match) and GREEN on the final commit; reverting the anchor re-reds it.
**Prompt**: `/tasks/WP01-anchor-gate-d-left-boundary.md`
**Requirement Refs**: FR-001, FR-002, FR-003, NFR-001, NFR-002, C-001, C-002, C-003, SC-001, SC-002, SC-003

### Included Subtasks

T001 Add the red-first ATDD regression test to `tests/architectural/test_dead_builtin_doc_paths.py`: build a throwaway git repo under `tmp_path`, plant a genuine top-level ref and a nested tail, run the real gate helper, assert the tail is NOT reported and the genuine ref IS. Witness it RED on the base (over-match direction). Commit FIRST.
T002 Anchor the left boundary: prepend `(^|[^A-Za-z0-9_./-])` (wrapping the existing alternation) to `_MOVED_BUILTIN_DOC_RE`, and extract a small shared `git grep` helper so the live gate and the regression test share one mechanism. Commit the GREEN fix.
T003 Prove non-vacuity (temporarily revert the anchor → show the regression test RED, record, do not commit the revert); run the targeted gate + sibling gates + scanner unit tests + `make test-fast`; `ruff check`, `ruff format --check --force-exclude`, mypy on changed files; confirm complexity ≤ 15.

### Implementation Notes

- The gate shells out to `git grep`; the regression test must `git add` its fixtures so the working-tree grep sees them.
- `(^|[^A-Za-z0-9_./-])` is plain POSIX ERE (no look-behind), so `git grep -E` supports it on every platform.
- Do NOT change `_GUARD_DOC_EXCLUSIONS` or the two forbidden path shapes.

### Parallel Opportunities

- None (single file, ordered red→green).

### Dependencies

- None (starting and only package).

### Risks & Mitigations

- ERE portability → leading alternation is POSIX-safe; verified via `git grep -E`.
- Test/gate divergence → share one helper so the test exercises exactly what CI runs.

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
| C-001 | WP01 |
| C-002 | WP01 |
| C-003 | WP01 |
| SC-001 | WP01 |
| SC-002 | WP01 |
| SC-003 | WP01 |

---

## Subtask Index (Reference)

| Subtask ID | Summary | Work Package | Priority | Parallel? |
|------------|---------|--------------|----------|-----------|
| T001 | Red-first ATDD regression test | WP01 | P1 | No |
| T002 | Left-boundary anchor + shared grep helper | WP01 | P1 | No |
| T003 | Non-vacuity proof + targeted tests + lint/type | WP01 | P1 | No |
