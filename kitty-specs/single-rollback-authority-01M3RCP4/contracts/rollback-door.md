# Contract: the consolidate rollback door

1. **Span.** Every call in `_run_lane_based_consolidation_locked` from `_phase_merge_lanes` through `_phase_reconcile_before_teardown` executes inside one `try` whose handlers call `_report_rollback`.
2. **Triggers.** `typer.Exit` with a non-zero code, any other `BaseException` (including `KeyboardInterrupt`). `typer.Exit(0)` passes through with no rollback.
3. **Order.** The phase's own working-tree byte restore and strand marker run first (inside the phase); then the authority restores refs; then the original exception is re-raised unchanged.
4. **Never masks.** A failure inside the rollback prints one line naming the branches to inspect; the original exception still propagates.
5. **One door.** `rollback_to_snapshot` is called only from `executor._report_rollback` and `consolidate._abort_restore_or_keep_record`; no function in the executor reverts commits (`git revert`) to undo a phase.
6. **Preflight.** Before the merge lock, `status_write_refusal` over the done-write request returns the policy `Refused` when the done write would be refused and at least one merged work package is not yet done; consolidate prints `error_code`, message and `next_step` and exits 1 with no ref moved and no record written. `--dry-run` reports the same `error_code`.
