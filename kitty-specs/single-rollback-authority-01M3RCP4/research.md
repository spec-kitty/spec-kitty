# Research: single-rollback-authority-01M3RCP4

Sources: two brownfield scouts and a post-spec adversarial reviewer (architect lens) over main `c34481d7`; every claim below was checked at file:line.

## R-1 Where the span starts and ends

- **Decision**: the wrapper covers `_phase_merge_lanes` through `_phase_reconcile_before_teardown` in `_run_lane_based_consolidation_locked`. The snapshot is the last step of `_capture_reconciliation_claim` (inside the pre-mutation fresh-record guard), so no exit falls between snapshot and first mutation.
- **Rationale**: matches the issue and ADR A3; teardown, push and cleanup are post-gate and out of scope (C-003).
- **Alternatives**: one try per phase (rejected: N doors, the pin cannot prove coverage).

## R-2 How the preflight reuses the protection authority

- **Decision**: extract the pre-flight policy gate of `BookkeepingTransaction._acquire_locked` (change set + `WorkflowMutationPolicy.assert_allowed` with `mission_has_coordination_branch`) into one helper that `_acquire_locked` keeps calling, and expose a lock-free `BookkeepingTransaction.preflight_refusal(...)` that selects the arm with the same classifiers (`_is_legacy_mission`, `_warrants_legacy_warning`) and returns the gate's `Refused` only for the modern coordination-less arm. `status_transition.status_write_refusal(request)` builds the same identity and topology decision as `emit_status_transition_transactional` (`_resolve_transaction_entry`) and returns `None` for the non-transactional fallback. The consolidation preflight builds the same `TransitionRequest` shape the done write builds and calls it only when at least one merged work package is not yet `done`.
- **Rationale**: C-001; the scouts showed the verdict depends on arm selection, topology availability, destination resolution (meta target, not `--target`) and the pending write set. A standalone "LANES and protected" rule would over-refuse all-done resumes, fallback-topology missions and single_branch landings.
- **Alternatives**: `ProtectionPolicy.is_protected(target)` plus a topology check (rejected: a second rule); acquiring a real transaction as a probe (rejected: takes the status lock and may create the coordination worktree).

## R-3 Exception handling in the wrapper

- **Decision**: `except typer.Exit` rolls back only for a non-zero code; `except BaseException` rolls back for anything else (including `KeyboardInterrupt`); both re-raise the original. `_report_rollback` already never raises (it prints a "Rollback could not complete" line).
- **Rationale**: `typer.Exit` subclasses `RuntimeError`; exceptions keep their types for existing callers.

## R-4 What the old contract tests become

- `test_merge_coord_worktree_resync_1826.py` (keep-done-after-failure), `test_issue_2367_bake_strand.py` (strand shape), `test_issue_2786_revert_failure_split_brain.py` and `test_executor_coord_reconcile.py` (forced `git revert` failure), `test_executor_option_a_revert_helpers_2711.py` (helper unit tests), `test_executor_coverage.py` and `test_executor_rollback_wiring.py` (helper patches) are re-pinned to the snapshot-restore contract or deleted with the helper they test (DM-01M3RCRDBS2RKWVVZH07AZ1B4M). Tests whose assertions survive a CAS restore (tree equality, APPROVED lane after rollback, resume reaches done) are run unchanged.
- `tests/terminus/test_repro_5318_abort.py` used the #5385 crash to leave residue; it gets a documented injection that simulates a hard kill between the crash and the in-process rollback.

## R-5 Residuals surfaced by the squad (named in the spec)

Auto-rebased lane merge commits (lanes are report-only), the resume-start strand heal as a restore floor, a failed-resync checkout reading dirty, and the protected single_branch checkout switch. None is closed here.
