# Mission Specification: Consolidation / done-bookkeeping regressions (#6071, #6073)

**Mission Branch**: `issue-6071-consolidation-bookkeeping-regressions`
**Created**: 2026-10-12
**Status**: Draft
**Input**: Fix the persistent consolidation / done-bookkeeping P0 regressions that stay RED
under `spec-kitty-events` 10.4.4, reported in nightly escalations #6071 (integration) and
#6073 (specify-cli-out-of-matrix), children of EPIC #5106. Bugfix mission.

## Context & Scope

Scope is EXACTLY the seven tests that stay RED on `origin/main` under events 10.4.4 (the
others listed in #6071/#6073 self-healed under 10.4.4 and are out of scope). Grounding proved
**four distinct root causes** — the single-root-cause hypothesis in the dispatch brief is
refuted; see `research/defect-diagnosis.md` for the full evidence, probes and regression
windows. Cluster C (skip-lanes) is a **stale-test-fixture** remediation, not a product bug —
a deliberate, evidence-backed divergence from the brief's "product fix" framing (Charter
Standing Order 4: stale → re-pin with realistic data; not green-washing — the product path is
verified correct once the fixture is realistic).

NON-GOALS: do not touch `spec-kitty-events` or the status reducer; do not widen to the
orchestrator-unclassified / self-healing failures; do not change refusal text, exit codes or
state-file shape except where that IS the bug; no new size/ratchet gates; never publish/push
to `main`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Post-merge done-check agrees with the canonical reducer (Priority: P1)

As a maintainer consolidating a coord-topology mission, I want the post-merge target
validation to read WP done-state through the canonical (Lamport/causal) reducer, so a WP that
is causally `done` is not falsely reported as stuck at `approved` merely because a later-
authored `approved` event has a later wall-clock `at`.

**Why this priority**: a false "did not reach done" aborts an otherwise-sound consolidation.

**Independent Test**:
`tests/specify_cli/cli/commands/test_merge_coord_topology_1772.py::test_post_merge_validation_reads_in_branch_status_path`.

**Acceptance Scenarios**:
1. **Given** a target log with `approved` (later `at`) then `done` (earlier `at`), **When**
   `_assert_merged_wps_done_on_target` runs, **Then** it reads WP01 as `done` and does not exit 1.
2. **Given** the #5354 migration-seed log (newer-`at` `done`, older-`at` seed written
   physically after), **When** the done-check runs, **Then** WP01 still resolves to `done`.

### User Story 2 — A bare-slug coord mission re-consolidates after a failed bookkeeping commit (Priority: P1)

As a maintainer resuming a consolidation whose bookkeeping commit failed, I want teardown to
recognise the mission's composed `<slug>-<mid8>` coordination directory as part of the
mission, so its status files are landed/torn down rather than flagged as "files outside the
Mission directory".

**Independent Test**:
`tests/integration/test_merge_lane_planning_data_loss.py::test_bare_slug_coord_mission_consolidates_again_after_the_bookkeeping_commit_failed`.

**Acceptance Scenarios**:
1. **Given** a bare-slug coord mission (primary `kitty-specs/<slug>/`, coordination
   `kitty-specs/<slug>-<mid8>/`) whose first run's bookkeeping commit failed, **When**
   consolidation is resumed, **Then** it succeeds (exit 0), ends with exactly one Mission
   directory, the full event log, the coordination branch/worktree gone, and a clean tree.

### User Story 3 — `--skip-lanes` completes a genuinely merge-ready direct-on-target mission (Priority: P1)

As a maintainer of a direct-on-target mission, I want `merge --skip-lanes` to complete a
genuinely merge-ready mission and to refuse / roll back / honor its persisted choice exactly
as designed — with the test fixture using a realistic (reducer-valid) transition chain so the
mission is actually merge-ready.

**Independent Test**:
`tests/specify_cli/cli/commands/test_issue_2745_merge_skip_lanes.py::test_skip_lanes_flag_is_what_enables_genuine_completion`,
`::test_skip_lanes_completion_rolls_back_on_post_mutation_failure`,
`::test_resume_without_reflagging_skip_lanes_auto_honors_persisted_choice`.

**Acceptance Scenarios**:
1. **Given** a direct-on-target mission whose WP01 reaches `approved` via a valid transition
   chain, **When** run with `--skip-lanes`, **Then** it completes (exit 0, baseline recorded,
   target ref advanced); run without the flag it hard-fails `MissingLanesError`.
2. **Given** a `--skip-lanes` completion that fails after mutating, **When** retried, **Then**
   it rolled back to the pre-command tip and the retry completes cleanly.
3. **Given** a persisted interrupted `--skip-lanes` merge, **When** `--resume` without
   re-passing the flag, **Then** it auto-honors the persisted choice and completes.

### User Story 4 — An interrupted one-directory fold gets abort advice, not a lock error (Priority: P1)

As a maintainer whose consolidation was killed inside the one-directory fold, I want the
re-run to refuse with `MERGE_UNSAFE_PRIMARY_DIRTY` naming the composed directory and advising
`consolidate --abort`, instead of a leftover `__global_merge__` `MergeLockError`.

**Independent Test**:
`tests/integration/test_merge_lane_planning_data_loss.py::test_a_run_killed_inside_the_fold_gets_advice_that_leads_to_a_successful_consolidation[status-pair-only]` and `[every-coordination-kind]`.

**Acceptance Scenarios**:
1. **Given** a process killed mid-fold (composed-dir coordination files deleted in the root
   checkout, target landed), **When** consolidation is re-run (with or without `--resume`),
   **Then** it refuses `MERGE_UNSAFE_PRIMARY_DIRTY`, names the composed directory and advises
   `spec-kitty consolidate --abort`; **and** `--abort` then a fresh run reach the one-directory
   end state.

### Edge Cases
- A migration-seed event (`actor: migration:*`) with an older `at` written after a terminal
  `done` must not win the post-merge done-check (US1 scenario 2, #5354 invariant preserved).
- Only the composed directory's coordination-KIND files count as the interrupted-fold state;
  any other dirty file keeps the stock remedy (US4).
- Rollback-on-post-mutation-failure must still route through the single rollback authority
  (AST pin stays green, no loosening).

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Post-merge done-check uses the canonical reducer | US1 | High | Open | [folded] | no — paired with the #5354 seed row below on the same surface |
| FR-002 | #5354 migration-seed invariant preserved under the canonical reducer | US1 | High | Open | [folded] | no — the done must beat the older-`at` seed with realistic data |
| FR-003 | Teardown recognises the composed `<slug>-<mid8>` coordination directory on resume | US2 | High | Open | [folded] | no — the composed-dir status pair must land, not strand |
| FR-004 | Skip-lanes fixtures use a reducer-valid transition chain (realistic merge-ready data) | US3 | High | Open | [folded] | no — WP01 must reduce to approved so the product path is exercised |
| FR-005 | Interrupted-fold composed-dir deletions trip MERGE_UNSAFE_PRIMARY_DIRTY with abort advice | US4 | High | Open | [folded] | no — a clean root checkout must still pass (positive control) |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Single canonical reducer authority | Done-state reads route through the canonical status reducer, never a second hand-rolled fold | Maintainability | High | Open |
| NFR-002 | No gate loosening | The single-rollback-authority AST pin and any coord-teardown/bookkeeping gate stay green with no allowlist/suppression growth | Integrity | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Reducer untouched | No change to `spec-kitty-events` or the status reducer | Technical | High | Open |
| C-002 | Local-only consolidation | Never publish/push to `main`; operator merges the PR | Technical | High | Open |
| C-003 | Scope fence | Do not touch the orchestrator-unclassified / self-healing failures | Technical | High | Open |

## Success Criteria *(mandatory)*

### Measurable Outcomes
- **SC-001**: All seven target tests pass (serially and under `make test-fast`'s `-n auto`) on the branch, witnessed RED on `origin/main` first — [folded] · no-op passable: no
- **SC-002**: `tests/consolidation/`, `tests/integration/test_merge_lane_planning_data_loss.py`, the relevant `specify_cli` merge/2745/1772 tests, and `make test-fast` stay green — [folded] · no-op passable: no
- **SC-003**: The named architectural gate `tests/consolidation/test_single_rollback_authority.py` (and any coord-teardown/bookkeeping gate found in grounding) stays green with no loosening — [folded] · no-op passable: no
- **SC-004**: `ruff check`, `ruff format --check --force-exclude` on changed files, and mypy are clean; complexity ≤ 15 — [folded] · no-op passable: no
