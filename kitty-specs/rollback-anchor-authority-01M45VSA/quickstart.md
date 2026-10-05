# Quickstart: verifying the rollback-anchor fix

```bash
# The two former P0 reproductions are now ordinary per-PR tests (no p0_repro marker):
uv run --frozen pytest tests/consolidation/test_rollback_anchor_p0_repro.py -q -n0

# Rollback authority, door wiring, abort CLI:
uv run --frozen pytest tests/consolidation/test_rollback_authority.py \
  tests/consolidation/test_executor_rollback_wiring.py \
  tests/consolidation/test_refuse_restores_target.py \
  tests/consolidation/test_single_rollback_authority.py \
  tests/terminus/test_rollback_door.py \
  tests/specify_cli/cli/commands/test_consolidate_abort_rollback.py -q
```

Operator-facing behaviour:

- A reconciliation FAIL/REFUSE with a teammate's commit on top of the landing prints `NOT restored main ... moved by another actor`. The teammate's commit stays on `main`.
- After a kill that left `main` at a landing this run wrote, `spec-kitty consolidate --abort` restores `main` to its snapshot and says so.
- After a kill that left a move the record cannot prove, a re-run refuses with `UNEXPLAINED_BRANCH_MOVE`, and `--abort` keeps the record. To keep the current tip and clear the record:

  ```bash
  spec-kitty consolidate --abort --release-branch main --release-reason "keep the teammate commit"
  ```
