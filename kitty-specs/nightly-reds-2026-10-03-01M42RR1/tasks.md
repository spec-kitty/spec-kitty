# Tasks: Nightly reds 2026-10-03

**Mission**: `nightly-reds-2026-10-03-01M42RR1`
**Branch contract**: plan and consolidate on `kitty/nightly-reds-2026-10-03`.
**Inputs**: [spec.md](spec.md), [plan.md](plan.md), [research/nightly-red-memo.md](research/nightly-red-memo.md)

Four independent work packages, one per failure group, with disjoint owned files and no dependencies.

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Record red baseline for the three census tests | WP01 | |
| T002 | Add `run-index` to the frozen doctor surface | WP01 | |
| T003 | Derive the `doctor skills` command count | WP01 | [P] |
| T004 | Derive the hybrid-install shim and file counts | WP01 | [P] |
| T005 | Record red baseline for the handle matrix | WP02 | |
| T006 | Let `_seed_mission` take a mission type and seed the custom type | WP02 | |
| T007 | Validate the whole handle-matrix file | WP02 | |
| T008 | Record red baseline for migration sequencing | WP03 | |
| T009 | Apply only the two migrations under test, in registry order, on a temporary project | WP03 | |
| T010 | Validate the whole backfill test file | WP03 | |
| T011 | Failing test: snapshot from a depth-1 clone | WP04 | |
| T012 | Add `--update-shallow` to the snapshot fetch | WP04 | |
| T013 | Run one e2e owned-worktree case on the full clone | WP04 | |
| T014 | Check other callers of the snapshot builder | WP04 | |

## Phase 1 - Test repairs

### Work Package WP01 – Command-registry censuses follow the registry

**Prompt**: [tasks/WP01-command-registry-censuses.md](tasks/WP01-command-registry-censuses.md)
**Goal**: the frozen doctor surface lists `run-index`; the `doctor skills` and hybrid-install counts come from the registry.
**Priority**: P1. **Independent test**: the three named test files pass.
**Requirements**: FR-001, FR-002, FR-003
**Dependencies**: None
**Estimated prompt size**: ~110 lines

T001 Record red baseline for the three census tests (WP01)
T002 Add `run-index` to the frozen doctor surface (WP01)
T003 Derive the `doctor skills` command count (WP01)
T004 Derive the hybrid-install shim and file counts (WP01)

### Work Package WP02 – Handle-equivalence matrix seeds the mission type it runs

**Prompt**: [tasks/WP02-handle-matrix-mission-type.md](tasks/WP02-handle-matrix-mission-type.md)
**Goal**: the run-identity test runs a custom mission on a mission of that type.
**Priority**: P1. **Independent test**: the three handle-form params pass.
**Requirements**: FR-004
**Dependencies**: None
**Estimated prompt size**: ~90 lines

T005 Record red baseline for the handle matrix (WP02)
T006 Let `_seed_mission` take a mission type and seed the custom type (WP02)
T007 Validate the whole handle-matrix file (WP02)

### Work Package WP03 – Migration sequencing test applies only its two migrations

**Prompt**: [tasks/WP03-migration-sequencing-harness.md](tasks/WP03-migration-sequencing-harness.md)
**Goal**: order comes from the registry, only the two migrations under test are applied, on a temporary project.
**Priority**: P1. **Independent test**: `TestMigrationSequencing` passes.
**Requirements**: FR-005
**Dependencies**: None
**Estimated prompt size**: ~90 lines

T008 Record red baseline for migration sequencing (WP03)
T009 Apply only the two migrations under test, in registry order, on a temporary project (WP03)
T010 Validate the whole backfill test file (WP03)

### Work Package WP04 – Source snapshot builder handles a shallow checkout

**Prompt**: [tasks/WP04-shallow-source-snapshot.md](tasks/WP04-shallow-source-snapshot.md)
**Goal**: a snapshot built from a shallow checkout is a readable repository.
**Priority**: P1. **Independent test**: the new snapshot-builder test passes.
**Requirements**: FR-006
**Dependencies**: None
**Estimated prompt size**: ~100 lines

T011 Failing test: snapshot from a depth-1 clone (WP04)
T012 Add `--update-shallow` to the snapshot fetch (WP04)
T013 Run one e2e owned-worktree case on the full clone (WP04)
T014 Check other callers of the snapshot builder (WP04)

## Parallelisation

All four work packages are independent and can run at the same time.

## Closeout (orchestrator, not a work package)

Changelog entry in `docs/changelog/CHANGELOG.md`, `make test-fast` baseline, pre-PR squad, pull request. Group G (three budget tests in `tests/performance/test_owned_checkout_perf.py`) is reported to the operator and not changed.
