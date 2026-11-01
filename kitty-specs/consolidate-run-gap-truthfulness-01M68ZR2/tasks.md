# Work Packages: Consolidate run-gap truthfulness

**Inputs**: Design documents from `/kitty-specs/consolidate-run-gap-truthfulness-01M68ZR2/`
**Prerequisites**: plan.md (required), spec.md (user stories), research.md (decisions D-01..D-04)

**Tests**: Required — all three items are defect fixes. Each reproduction runs red through the
pre-existing entry point before the fix exists (DIRECTIVE_034, charter ATDD-First).

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

## Work Package WP01: Commit the tombstoned workspace contexts (Priority: P1) 🎯 MVP

**Goal**: `consolidate` commits the tracked `.kittify/workspaces/<slug>-<lane>.json` it tombstones
during lane-worktree cleanup, so a landed merge leaves the target branch clean.
**Independent Test**: In a real git repo with one tracked and one untracked lane context, drive
`_phase_cleanup_worktrees_and_branches` on a merge run; assert both files are gone from disk, exactly
one commit was created, its path list is the tracked context only, and `git status --porcelain` is
empty.
**Prompt**: `/tasks/WP01-tombstone-context-commit.md`
**Requirement Refs**: FR-001, FR-002, NFR-001, NFR-002, C-002, SC-001

### Included Subtasks

T001 Write the red-first test in `tests/specify_cli/test_workspace_context_tombstone.py` and prove it fails on the unfixed cleanup phase
T002 Collect the contexts the cleanup phase actually unlinked, keeping only paths tracked at the pre-run commit
T003 Commit that path set through `commit_merge_bookkeeping` with the resolved merge target as destination, warning (never failing the landed merge) when the commit cannot land
T004 Add the scoped/no-op assertions (one commit, tracked-only paths, no commit when nothing tracked was removed) and run the targeted suites plus ruff and mypy

### Implementation Notes

- Red first: the new test must fail (`git status --porcelain` non-empty) before any production edit,
  and the red output is quoted in the PR.
- `commit_merge_bookkeeping` is the ONE sanctioned protected-flow seam already imported by
  `phase_teardown.py`; do not add a second guarded call site or a raw `git commit` (NFR-001).
- Only commit contexts that were tracked before the tombstone: `safe_commit` stages with
  `git add --force` and fails on a path that is neither on disk nor tracked.
- The deletion happens after `_phase_commit_and_assert`, so this is a second, separate commit; keep
  it out of the `--keep-worktree` path (no tombstone there) and out of the planning-artifact lane
  case (nothing to tombstone).
- A failure to commit must not fail an already-landed merge; surface it and keep the run's existing
  teardown behaviour.

### Parallel Opportunities

- T002–T003 are one function; T004's assertions can be drafted alongside the red test.

### Dependencies

- None (starting package).

### Risks & Mitigations

- Committing an unrelated path → the path set is built from the exact list of contexts the loop
  unlinked, never from a glob, and the test asserts the commit's path list.
- Protected-target refusal on the bookkeeping commit → the seam already handles protected refs; the
  fallback is a warning, not a crash, and the existing consolidation tests are the regression net.

---

## Work Package WP02: Accept guidance follows the landing path (Priority: P2)

**Goal**: On coordination topology, `accept`'s next steps name `spec-kitty consolidate` instead of
telling the operator to push a branch and open a pull request.
**Independent Test**: Call `_build_acceptance_instructions` (through `perform_acceptance` where
practical) for a coordination-topology Mission whose HEAD is its target branch in `pr` mode; assert
no "pull request" instruction and one consolidation instruction, and assert the non-coord
integration-branch wording is unchanged on the same helper.
**Prompt**: `/tasks/WP02-accept-guidance-topology.md`
**Requirement Refs**: FR-003, FR-004, C-002, SC-002

### Included Subtasks

T005 Write the failing test for the coord-topology `pr` next steps (and the non-coord positive control) in `tests/specify_cli/test_acceptance_regressions.py`
T006 Compute the topology fact once in `perform_acceptance` and pass it to `_build_acceptance_instructions`
T007 Emit the consolidation instruction (no pull request) in the `pr`/integration-branch arm for coordination topology, leaving every other arm byte-identical

### Implementation Notes

- Red first: assert the current sentence is present (or the consolidation instruction absent) before
  the fix, and record that failure.
- Reuse the existing topology read (`load_meta_or_empty(...)["topology"]`/`coordination_branch`) —
  no new resolver, and no second `target_branch` read.
- The `local` and `checklist` arms and the non-integration `pr` arm must not change (FR-004).

### Parallel Opportunities

- Independent of WP01 and WP03 (different modules).

### Dependencies

- None.

### Risks & Mitigations

- Sentence drift for flat topologies → the positive-control assertion pins the existing wording.

---

## Work Package WP03: The `done` refusal names its cause (Priority: P2)

**Goal**: `issue_matrix_done_outcome` prints the verdict-recording remedy only when a verdict is
missing or unresolved; a fully-verdicted matrix with validation diagnostics gets a cause-accurate
message and the same FAIL decision.
**Independent Test**: Request the `done` judgement for a matrix whose only failure is a
`deferred-with-followup` row with no follow-up handle: the message must not contain "Fill in
verdicts" or the `agent issue-verdict` remedy, and the gate must still FAIL in block mode. The
missing/in-mission families must keep the old wording.
**Prompt**: `/tasks/WP03-done-refusal-cause.md`
**Requirement Refs**: FR-005, FR-006, NFR-003, SC-003, SC-004

### Included Subtasks

T008 Write the failing tests (diagnostic-only message, missing-verdict positive control, gate verdict unchanged) in `tests/policy/test_merge_gates_issue_matrix.py` and `tests/specify_cli/cli/commands/agent/test_tasks_parsing_validation.py`
T009 Split the header and the remedy decision by cause in `issue_matrix_done_outcome`
T010 Run the existing terminality/approval suites to prove no gate decision changed

### Implementation Notes

- Red first: the diagnostic-only test must fail on the current message.
- The decision stays FAIL for both families — only the header and whether `_ISSUE_VERDICT_REMEDY` is
  appended change (FR-006). Do not touch `_issue_matrix_evaluation` or the validators.
- `unknown` placeholders and `in-mission` rows stay in the "verdict missing/unresolved" family, so
  the existing pins (`"has unresolved entries"`, `"Fill in verdicts before done."`,
  `"Still 'in-mission'"`) keep passing.

### Parallel Opportunities

- Independent of WP01 and WP02 (different module).

### Dependencies

- None.

### Risks & Mitigations

- Over-eager reword of the missing-verdict arm → the existing tests in
  `test_tasks_parsing_validation.py` and `test_merge_gates_issue_matrix.py` pin that wording.

---

## Work Package WP04: Changelog and the docs the behaviour touches (Priority: P3)

**Goal**: The user-facing change is recorded under `[Unreleased]` with a `(#6450)` reference and
before/after, and the docs that describe consolidation teardown/acceptance next steps match the new
behaviour.
**Independent Test**: `docs/changelog/CHANGELOG.md` carries the entry; the touched doc pages state
the new behaviour; `uv run python -m scripts.docs.check_docs_freshness --ci` reports errors=0.
**Prompt**: `/tasks/WP04-changelog-and-docs.md`
**Requirement Refs**: C-003, SC-001, SC-002, SC-003

### Included Subtasks

T011 Add the `[Unreleased]` changelog entry (impact-first lead, `(#6450)`, before/after, under 1,200 characters)
T012 Update the existing consolidation/recovery doc prose for the tombstone commit and the accept next steps
T013 Verify docs freshness and the terminology test

### Implementation Notes

- Root `CHANGELOG.md` is a symlink to `docs/changelog/CHANGELOG.md`; edit the target file.
- Edit existing pages; do not add a page, so the docs index needs no rebuild (shared machine state:
  do not rebuild the whole CLI reference).
- Never write machine-local paths or personal data into the entry.

### Parallel Opportunities

- Draftable during WP01–WP03; must land after them so it describes shipped behaviour.

### Dependencies

- Depends on WP01, WP02, WP03.

### Risks & Mitigations

- Docs index drift → `check_docs_freshness --ci` (errors=0) plus
  `tests/architectural/test_no_legacy_terminology.py`.

---

## Dependency & Execution Summary

- **Sequence**: WP01 → WP02 → WP03 → WP04; the three fixes are independent of each other, WP04
  documents all three.
- **Parallelization**: WP02 and WP03 touch different modules and can be reordered freely.
- **MVP Scope**: WP01.
