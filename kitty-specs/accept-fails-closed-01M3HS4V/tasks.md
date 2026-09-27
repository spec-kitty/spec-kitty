# Work Packages: Accept fails closed on a stale or pending acceptance matrix

**Inputs**: `spec.md`, `plan.md`, `research.md` in `kitty-specs/accept-fails-closed-01M3HS4V/`

**Tests**: Every [build] requirement gets an issue-pinned regression test written RED first through the production entry point (charter ATDD-first; SC-004).

## Subtask Format: `[Txxx] [P?] Description`

Subtasks are reference rows; record completion with `spec-kitty agent tasks mark-status <Txxx> --status done`.

---

## Work Package WP01: Shared locked acceptance-matrix write seam (Priority: P0)

**Goal**: One locked read-modify-write seam for `acceptance-matrix.json`, plus the owned-row splice and the locked pre-stamp verdict guard primitives; the verdict command uses the seam.
**Independent Test**: Seam lock-spy test (re-read and write inside `feature_status_lock(matrix_dir.name)`), owned-row splice unit tests incl. re-registration, guard refuses fail/pending, `acceptance-verdict` CLI fails when the seam is patched to raise.
**Prompt**: `tasks/WP01-shared-locked-matrix-write-seam.md`
**Requirement Refs**: FR-001, FR-002, NFR-001, NFR-002, C-004

### Included Subtasks

T001 Lift `_locked_reread_splice_and_write` into `acceptance/matrix.py` as `locked_reread_splice_and_write(..., commit: bool)`
T002 Add `splice_owned_rows(fresh, snapshot, judged)` implementing the spec's row ownership rule
T003 Add `locked_acceptance_verdict_guard(repo_root, matrix_dir)` context manager (lock, re-read, refuse unless pass / pass_pending_consolidation)
T004 Route `acceptance_verdict.py` (both modes) through the shared seam; delete the private copy
T005 Tests: lock-spy, splice ownership matrix (incl. re-registration, fresh-only, snapshot-only rows), guard, FR-002 wiring control

### Dependencies

- None.

### Risks & Mitigations

- #4858 spy tests patch names at the verdict module's import site; re-point them at the seam module rather than weakening them.

---

## Work Package WP02: Accept gate and stamp fail closed (Priority: P0)

**Goal**: Accept judges the fresh spliced matrix, never erases a concurrent verdict, re-checks the verdict under the lock before writing the acceptance record, and fails closed on lock timeout.
**Independent Test**: #4974 regression through the `accept` CLI (NI + criterion variants, real `acceptance-verdict` mid-check, HEAD content asserted), late-verdict (post-splice, pre-stamp) variant, lock-held variant, each with a same-fixture positive control.
**Prompt**: `tasks/WP02-accept-gate-and-stamp-fail-closed.md`
**Requirement Refs**: FR-003, FR-004, FR-005, FR-010, C-003

### Included Subtasks

T006 Write the #4974 regression tests RED first (SC-001, SC-005, SC-006)
T007 Route `_evaluate_acceptance_matrix`'s write through the seam (`commit=False`) with `splice_owned_rows`; judge evidence and verdict from the fresh matrix; extract helpers to stay ≤ 15 complexity
T008 Carry `acceptance_matrix_dir` on `AcceptanceSummary`; call `record_acceptance` inside the guard in `_commit_acceptance_meta`
T009 Map `FeatureStatusLockTimeoutError` to a fail-closed accept diagnostic (no write, no `accepted_at`)

### Dependencies

- Depends on WP01.

### Risks & Mitigations

- `--no-commit` must leave HEAD unchanged; keep `tests/specify_cli/test_accept_no_commit_readonly.py` green.

---

## Work Package WP03: accept-mission applies the host readiness verdict (Priority: P0)

**Goal**: `orchestrator-api accept-mission` refuses a not-ok summary with `MISSION_NOT_READY` and records acceptance only through the guarded record; contract version and docs updated.
**Independent Test**: CLI tests on a pending-matrix mission, a no-`lanes.json` mission and a late-verdict mission refuse with nothing recorded; the same acceptable fixture is accepted.
**Prompt**: `tasks/WP03-accept-mission-readiness.md`
**Requirement Refs**: FR-007, FR-009, C-001, C-002

### Included Subtasks

T010 Build a shared acceptable-mission fixture; write the #4934 regression tests RED first
T011 Gate `accept_mission` on `summary.ok` (strict metadata) with the FR-007 error data; record under the guard
T012 Repair `test_all_done_accepted` / `test_all_approved_accepted` onto the acceptable fixture
T013 Bump `CONTRACT_VERSION` to 1.7.0 with a ledger entry; update the pin test, `docs/api/orchestrator-api.md`, the operator skill and its contract reference

### Dependencies

- Depends on WP02 (summary matrix dir and guard wiring).

---

## Work Package WP04: Call-site gate and #4891 CLI pin (Priority: P1)

**Goal**: Make the seam structurally unavoidable and pin #4891 at the CLI.
**Independent Test**: The gate passes on the tree and its self-mutation test detects planted aliased and attribute-style calls; the #4891 CLI test refuses without `lanes.json` and accepts with it.
**Prompt**: `tasks/WP04-call-site-gate-and-4891-pin.md`
**Requirement Refs**: FR-006, FR-008

### Included Subtasks

T014 AST call-site gate over `src/` for both unlocked writers (Name, Attribute, alias) with a shrink-only per-function allowlist and a self-mutation test
T015 CLI-level #4891 test with a same-fixture positive control

### Dependencies

- Depends on WP02 (the gate's raw write must be gone).
