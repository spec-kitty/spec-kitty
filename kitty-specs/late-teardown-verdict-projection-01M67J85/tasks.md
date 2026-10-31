# Work Packages: Late teardown verdict projection

**Inputs**: Design documents from `/kitty-specs/late-teardown-verdict-projection-01M67J85/`
**Prerequisites**: plan.md (required), spec.md (user stories), research.md

**Tests**: Required — this is a defect fix. The reproduction runs red through the pre-existing
`consolidate` refusal/resume entry point before the fix exists (DIRECTIVE_034).

**Organization**: Fine-grained subtasks (`Txxx`) roll up into work packages (`WPxx`). Each work
package must be independently deliverable and testable.

**Prompt Files**: Each work package references a matching prompt file in `/tasks/`.

## Subtask Format: `[Txxx] [P?] Description`

- **[P]** indicates the subtask can proceed in parallel (different files/components).
- Subtasks are **reference rows**, not checkboxes: record completion with
  `spec-kitty agent tasks mark-status <Txxx> --status done`.

## Path Conventions

- **Single project**: `src/specify_cli/`, `tests/`

---

## Work Package WP01: Project the whole late coordination window (Priority: P1) 🎯 MVP

**Goal**: A `consolidate --resume` after a `COORD_TEARDOWN_KEPT_ONLY_COPY` refusal projects every
attributable coordination commit in the late window — gate matrices included — or refuses before
deleting the branch.
**Independent Test**: Build a coord-topology mission, force a real teardown refusal, commit a
review-cycle artifact and record a real `agent issue-verdict`, then `consolidate --resume` and read
`issue-matrix.json` from the target branch: the terminal verdict is there and the coordination
branch is gone.
**Prompt**: `/tasks/WP01-late-window-projection.md`
**Requirement Refs**: FR-001, FR-002, FR-003, FR-004, FR-005, NFR-001, NFR-002, NFR-003, C-001, C-002, SC-001, SC-002, SC-003, SC-004

### Included Subtasks

T001 Write the red-first reproduction in `tests/consolidation/test_issue_6791_late_verdict_projection.py` and prove it fails on the unfixed CLI
T002 Widen the late-window path selector with an opt-in `include_gate_matrices` widening (default off, so the mid-merge squash proof is untouched)
T003 Add `project_late_gate_matrix_commits` to `src/specify_cli/consolidation/bookkeeping_projection.py`
T004 Add the established-judgement preservation guard (terminal issue verdicts, `pass` criteria, terminal negative invariants) and the forward-only deletion refusal
T005 Add the whole-window completeness assertion and wire both new stages into `_land_late_coordination_commits`, wrapping a refusal as `CoordinationTeardownError` with the branch kept
T006 Add the guard and refusal tests (regression preserved, deletion refused, unprojectable record refused, idempotent no-op)
T007 Run the targeted suites, ruff and mypy on the touched packages

### Implementation Notes

- The failing test must exist and fail **before** any production edit: it is the red-first proof
  quoted in the PR.
- `_post_checkpoint_mission_paths` is shared with the mid-merge projection whose output feeds
  `projected_content_matches_target`; the new behaviour must be opt-in (C-001).
- Terminal verdict set comes from `IssueMatrixVerdict` (`in-mission` and `unknown` are the only
  non-terminal members, matching the gate's own pass detail) — never a second hardcoded list.
- The status pair is owned by the union/rematerialize stage that runs after this one; exclude it by
  its canonical filename constants, not by kind.
- Writes go through the existing `commit_merge_bookkeeping` seam; no new writer (NFR-003).

### Parallel Opportunities

- T002 and T004 touch different functions in the same module; T006 can be drafted alongside T005
  but lands after it.

### Dependencies

- None (starting package).

### Risks & Mitigations

- Over-refusal on shapes the fix did not anticipate → the assertion compares target working-tree
  bytes against the coordination tip, so a genuinely landed record never refuses; existing
  teardown tests (`tests/consolidation/test_teardown_refusal_resume.py`,
  `test_teardown_keeps_only_copy.py`, `tests/coordination/`) are the regression net.

---

## Work Package WP02: Changelog and recovery docs (Priority: P2)

**Goal**: The user-facing change is recorded under `[Unreleased]` with before/after, and the
`--resume` teardown recovery documentation states the widened projection and the refusal semantics.
**Independent Test**: `docs/changelog/CHANGELOG.md` has the `[Unreleased]` entry with the `(#6791)`
reference; the consolidation recovery doc describes what the resume now projects and when it
refuses. `uv run python -m scripts.docs.check_docs_freshness --ci` reports errors=0.
**Prompt**: `/tasks/WP02-changelog-and-docs.md`
**Requirement Refs**: SC-002, SC-003

### Included Subtasks

T008 Add the `[Unreleased]` changelog entry (impact-first lead, `(#6791)`, before/after, under 1,200 characters)
T009 Update the consolidation teardown/recovery documentation the behaviour touches
T010 Verify docs freshness and the terminology test

### Implementation Notes

- Root `CHANGELOG.md` is a symlink to `docs/changelog/CHANGELOG.md`; edit the file, never replace
  the symlink.
- Only touch the doc surface this behaviour changes (shared machine state: do not rebuild the whole
  CLI reference).

### Parallel Opportunities

- None meaningful; both subtasks touch adjacent prose.

### Dependencies

- Depends on WP01 (the changelog must describe the shipped behaviour).

### Risks & Mitigations

- Docs index drift → run `check_docs_freshness --ci` (expect errors=0) and
  `tests/architectural/test_no_legacy_terminology.py`.

---

## Dependency & Execution Summary

- **Sequence**: WP01 → WP02.
- **Parallelization**: none; WP02 documents what WP01 ships.
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
| NFR-001 | WP01 |
| NFR-002 | WP01 |
| NFR-003 | WP01 |
| C-001 | WP01 |
| C-002 | WP01 |
| SC-001 | WP01 |
| SC-002 | WP01, WP02 |
| SC-003 | WP01, WP02 |
| SC-004 | WP01 |

---

## Subtask Index (Reference)

| Subtask ID | Summary | Work Package | Priority | Parallel? |
|------------|---------|--------------|----------|-----------|
| T001 | Red-first reproduction through the real CLI | WP01 | P1 | No |
| T002 | Opt-in gate-matrix widening of the late window selector | WP01 | P1 | Yes |
| T003 | `project_late_gate_matrix_commits` seam stage | WP01 | P1 | No |
| T004 | Established-judgement guard + forward-only refusal | WP01 | P1 | Yes |
| T005 | Completeness assertion + teardown wiring | WP01 | P1 | No |
| T006 | Guard/refusal/idempotence tests | WP01 | P1 | No |
| T007 | Targeted suites, ruff, mypy | WP01 | P1 | No |
| T008 | Changelog `[Unreleased]` entry | WP02 | P2 | Yes |
| T009 | Teardown recovery docs | WP02 | P2 | Yes |
| T010 | Docs freshness + terminology checks | WP02 | P2 | No |
