# Work Packages: coord-topology `accept` commits its own coordination-worktree residual

**Inputs**: Design documents from `kitty-specs/7091-accept-coord-residual-artifact-commit-01M6G9GS/`
**Prerequisites**: plan.md (required), spec.md (user stories)
**Issue**: [#7091](https://github.com/spec-kitty/spec-kitty/issues/7091)

**Tests**: required. This is a residual-routing defect: the regression test runs red-first
through the pre-existing entry point (`accept.py::_run_residual_acceptance_commit` against a
real coordination-topology worktree) before the survivor lands, and narrowness / flat / C-002
guards keep the boundary honest afterwards.

**Organization**: one work package. The whole change is one coherent slice (the survivor, the
reporting note, the guards and the changelog); splitting it would put the red-first proof and
the fix in different review units.

**Prompt Files**: `/tasks/WP01-mission-event-log-coord-kind.md`.

## Path Conventions

- Source: `src/specify_cli/cli/commands/accept.py`; tests:
  `tests/specify_cli/cli/commands/test_accept_residual_partition.py`; changelog:
  `docs/changelog/unreleased/<pr>.fixed.md`. `src/mission_runtime/artifacts.py`,
  `src/specify_cli/coordination/commit_router.py`, `src/specify_cli/git/safe_commit*` and
  `tests/review/test_mission_events_dirty_survivor_5669.py` are read-only for this mission.

---

## Work Package WP01: Defer a non-artifact coordination residual (Priority: P0)

**Goal**: accept's residual artifact commit stops failing on a coordination-worktree path that
classifies to no mission artifact kind (`mission-events.jsonl`), leaves that keep-local log
where it lives (#5669), reports it on the acceptance result, and keeps committing every
classified artifact exactly as before — so a ready coordination-topology mission records its
own acceptance instead of exiting 1.
**Independent Test**: build a real coordination-topology fixture (canonical
`CoordinationWorkspace` worktree), dirty `mission-events.jsonl` and the acceptance matrix in the
coordination worktree, call `_run_residual_acceptance_commit` — before the change it raises
`ResidualCommitError` naming `safe_commit: refusing to stage path under .worktrees/`; after it
returns with no refused surface, the matrix commits on the coordination branch, the primary
branch gains no commit, the log stays tracked-modified where it lives, and the acceptance result
carries one note naming it.
**Prompt**: `/tasks/WP01-mission-event-log-coord-kind.md`
**Requirement Refs**: FR-001, FR-002, FR-003, FR-004, FR-005, FR-006, FR-007, NFR-001, NFR-002, NFR-003, C-001, C-002, C-003, SC-001, SC-002, SC-003, SC-004

### Included Subtasks

T001 Red-first: add the coordination-topology survivor regression test in `tests/specify_cli/cli/commands/test_accept_residual_partition.py` (coord-worktree `mission-events.jsonl` + matrix, drive `_run_residual_acceptance_commit`) and confirm it fails on the current code with the issued `safe_commit` refusal
T002 Add `_nonartifact_residual_paths` (classifier-derived) and exclude those paths from the residual batch in `src/specify_cli/cli/commands/accept.py`
T003 Add `_note_deferred_residuals` and call it from `_run_post_acceptance_steps` so the deferral is reported on both output lanes (with an empty-deferral negative control)
T004 Add the narrowness test: a PRIMARY-classified artifact stranded in the coordination worktree still refuses through `safe_commit` (pins FR-003 / NFR-003)
T005 Add the flat/single-branch paired test proving a dirty `mission-events.jsonl` still commits on the mission's own branch
T006 Confirm the #5669 C-002 guard (`is_toolchain_generated_churn` still `False`) and the partition pins stay green untouched; run the targeted modules, ruff and mypy on the touched files; record the self-review
T007 Add the per-PR changelog fragment `docs/changelog/unreleased/<pr>.fixed.md`

### Implementation Notes

- The fix is the exclusion + the note. Do not add a `MissionArtifactKind` for the log, do not
  widen `is_self_bookkeeping_churn` / `is_toolchain_generated_churn`, and do not touch
  `safe_commit`, the commit router's grouping or `accept`'s readiness pipeline.
- Derive the survivor from `kind_for_mission_file` — no filename literal (C-001).
- A CLASSIFIED PRIMARY path in the coordination worktree must still refuse; only
  `kind is None` is deferred.
- CI's diff-cover gate wants coverage on changed lines: the survivor, the note and their
  negative controls cover both new helpers.

### Parallel Opportunities

None: production change is one module, and the tests pin that module's behavior.

### Dependencies

- None (single package).

### Risks

- The survivor's breadth: every unclassified coordination-worktree residual is deferred (and
  reported). That is the principled boundary; misscoped unclassified agent artifacts
  (`reasons-canvas.md` and friends) are recorded as a separate follow-up in the PR.
- The reporting note adds one `git status` per accept run and must never become a new failure
  path (it swallows its own errors).
- Never classify the log to "simplify" this: that reverses #5669 and fails the pinned C-002
  guard.
