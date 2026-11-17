# Discovery squad: tracked issues (pre-spec)

| Issue | State | Disposition for #7692 |
|---|---|---|
| #5783 | closed (PR #7688) | Direct predecessor. Its ruling put "adopt `--target` as the new record" out of scope. `--retarget` automates the remedy #7688 prints (correct `meta.json`, commit, re-run). |
| #7651 | closed, duplicate of #5783 | Fold in: the hatch control (`test_control_target_override_hatch_stands_the_guard_down`) must keep asserting its exit code; add a `--retarget` arm if the hatch shape applies. |
| #6464 | closed (PR #6895) | Constraint: the protection check runs against the new target BEFORE the meta rewrite, or `--retarget` launders `PROTECTED_BRANCH_REFUSED`. |
| #7360 | open sub-epic | Parent of #5783/#7692. Binding goal: the printed outcome, the status log and git agree. |
| #7301 | open P3 | Constraint: the bookkeeping projection writes a union before validating; do not widen it. Note it as a residual on the new target. |
| #7361 | open sub-epic | Constraint: orchestrator-api has no rollback door, so a retarget there is either refused or CLI-only. |
| #7329 | open P2 | Unrelated (lane freshness on implement/move-task). Out of scope. |

## Risks carried into the spec
1. Protected-branch bypass: judge `#6464` and `#5385` against the new target before writing.
2. Rollback/resume: the retarget commit is a mutation inside the snapshot; `--abort` restores; `--resume` honours the persisted retarget.
3. Placement: where the commit lands goes through the placement seam (coord: meta.json lives with the coordination branch before the landing).
4. Entry-point parity: `--dry-run` forecasts; orchestrator-api decision pending (operator Q5).
5. Outcome honesty: tests assert the exit code, a clean tree, and every S4 write on the new target, on lanes and coord.
