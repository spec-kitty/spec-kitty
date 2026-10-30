# Work Packages: Review feedback draft retirement

**Inputs**: Design documents from `/kitty-specs/review-feedback-draft-retirement-01M66YR3/`
**Prerequisites**: plan.md (required), spec.md (user stories), research.md, data-model.md
**Issue**: spec-kitty/spec-kitty#6632

**Tests**: Required. This is a defect fix, so ATDD/red-first applies *inside* WP01: the failing
regression through the real `move-task` entry point is WP01's first commit, and the implementation is
the commit after it. It is deliberately not a separate work package — a package whose own tests are
red cannot pass its per-WP review, and "the red test is the first commit of the lane" is what the
charter's ATDD-First Discipline actually prescribes.

**Organization**: Fine-grained subtasks (`Txxx`) roll up into work packages (`WPxx`). Each work
package is independently deliverable and testable.

**Prompt Files**: Each work package references a matching prompt file in `tasks/`.

## Subtask Format: `[Txxx] [P?] Description`

- **[P]** indicates the subtask can proceed in parallel (different files/components).
- Subtasks are **reference rows**, not checkboxes: record completion with
  `spec-kitty agent tasks mark-status <Txxx> --status done`.

## Path Conventions

- Single project: `src/`, `tests/`, `docs/`

---

## Work Package WP01: Retire the consumed draft at the durable-write seam (Priority: P1) 🎯 MVP

**Goal**: The printed rejection command leaves the mission directory clean, so the next
`move-task --to for_review` passes the planning-artifact check — and the reviewer's draft survives
whenever removing it would lose something.
**Independent Test**: `uv run pytest tests/specify_cli/cli/commands/agent/test_review_feedback_draft_retirement.py tests/specify_cli/review/test_cycle_feedback_draft_retirement.py -q` — the end-to-end module is red before the fix commit and green after it; the unit module covers the five predicates.
**Prompt**: `tasks/WP01-retirement-seam.md`
**Requirement Refs**: FR-001, FR-002, FR-003, FR-004, FR-005, FR-006, FR-008, NFR-001, NFR-002, NFR-003, C-001, C-002, C-003, SC-001, SC-002, SC-003

### Included Subtasks

T001 Build the end-to-end fixture harness (real `move-task` app, lanes manifest, lane implementation commit, draft at the advertised path)
T002 Red commit: the rejection leaves `git status --porcelain kitty-specs/<mission>/` clean and the next `--to for_review` exits 0
T003 Red commit: the non-durable, tracked, out-of-mission and edited-after-record cases each keep the draft on the same fixture
T004 `_resolve_review_body` returns the raw source text alongside the composed body
T005 Add `_retire_consumed_feedback_source` to `review/cycle.py`, call it after a durable persistence outcome, extend `CreatedRejectedReviewCycle`
T006 Print a kept-draft warning on stderr in `tasks_verdict_persistence.py` (JSON stdout unchanged)
T007 Unit tests for the five predicates in `tests/specify_cli/review/test_cycle_feedback_draft_retirement.py`
T008 Half-by-half revert proof (drop each predicate in turn, confirm a named test goes red) and tracer entry

### Implementation Notes

- Do not stub `_validate_research_artifacts`/`_validate_ready_for_review`: the reported defect is that
  gate. The existing sibling test stubs it, which is why the bug was invisible.
- Use `kernel.git.listing.is_tracked`; a `GitCommandError` means "keep".
- Resolve paths and compare with `Path.is_relative_to`; handle Windows separators.
- The unlink is best-effort: an `OSError` becomes a `warnings` entry, never an exception (NFR-002).

### Parallel Opportunities

- T002 and T003 are separate test functions on one fixture; T007 can be written alongside T005.

### Dependencies

- None. WP01 is the mission's only behavioural change.

### Risks & Mitigations

- Deleting a reviewer's only copy → five predicates, one test each (FR-002–FR-005).
- Fixture fights the lane/evidence-window gates → copy the fixture recipe from
  `research/repro-6632.py`, which is known to reach the gate.
- Behaviour change for `--no-auto-commit` users → FR-002 keeps the file; the `local_only` outcome is
  untouched.

---

## Work Package WP02: Prompt wording, guide and changelog (Priority: P2)

**Goal**: The review prompt stops claiming the draft is committed, the how-to guide documents the
lifecycle, and `[Unreleased]` records the user-visible fix.
**Independent Test**: `uv run pytest tests/agent/test_review_prompt_feedback_draft.py -q`, plus the docs freshness check.
**Prompt**: `tasks/WP02-prompt-and-docs.md`
**Requirement Refs**: FR-007, SC-004, C-001

### Included Subtasks

T009 Reword the two rejection blocks and the closing note in `_build_review_prompt_lines`
T010 Prompt-wording test in `tests/agent/test_review_prompt_feedback_draft.py`
T011 Update `docs/guides/how-to/missions/review-work-package.md`
T012 Add the `[Unreleased]` → `### Fixed` changelog entry with the `(#6632)` reference

### Implementation Notes

- The CLI `--review-feedback-file` help text and its fixture, plus the generated
  `docs/api/agent-subcommands.md`, are deliberately out of scope (plan.md, IC-02 risks). Say so in the
  PR's `## Deferred` section if a reviewer asks.
- Changelog shape: bold impact-first lead with `(#6632)`, then **Before:** / **After:**, under 1,200
  characters.

### Parallel Opportunities

- All three surfaces are disjoint; edit them in one pass.

### Dependencies

- None (independent of WP01; lands on the same branch).

### Risks & Mitigations

- Docs freshness gate → no new doc page and no ADR, so `docs_index`/ADR inventory are unchanged; run
  the freshness check to prove it.
- Prompt snapshots → grep for the old strings first; none exist today.

---

## Dependency & Execution Summary

- **Sequence**: WP01 and WP02 are independent and may run in parallel lanes.
- **Parallelization**: fully parallel (disjoint owned files).
- **MVP Scope**: WP01 (the defect). WP02 is the wording/doc half of the same PR.

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
| FR-007 | WP02 |
| FR-008 | WP01 |
| NFR-001 | WP01 |
| NFR-002 | WP01 |
| NFR-003 | WP01 |
| C-001 | WP01, WP02 |
| C-002 | WP01 |
| C-003 | WP01 |
| SC-001 | WP01 |
| SC-002 | WP01 |
| SC-003 | WP01 |
| SC-004 | WP02 |

---

## Subtask Index (Reference)

| Subtask ID | Summary | Work Package | Priority | Parallel? |
|------------|---------|--------------|----------|-----------|
| T001 | End-to-end fixture harness for the real move-task app | WP01 | P1 | No |
| T002 | Red: clean tree + next `for_review` exits 0 | WP01 | P1 | Yes |
| T003 | Red: kept-draft cases (non-durable, tracked, outside, edited) | WP01 | P1 | Yes |
| T004 | `_resolve_review_body` returns the raw source text | WP01 | P1 | No |
| T005 | The retirement seam + outcome fields | WP01 | P1 | No |
| T006 | stderr notice for a kept draft | WP01 | P1 | Yes |
| T007 | Unit tests for the five predicates | WP01 | P1 | Yes |
| T008 | Half-by-half revert proof + tracer entry | WP01 | P1 | No |
| T009 | Reword the review prompt's rejection blocks | WP02 | P2 | No |
| T010 | Prompt-wording test | WP02 | P2 | Yes |
| T011 | Update the review how-to guide | WP02 | P2 | Yes |
| T012 | Changelog `[Unreleased]` entry | WP02 | P2 | Yes |
