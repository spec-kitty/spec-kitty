# Data Model

No schema change. The event log and the snapshot keep their shapes.

| Entity | Change |
|--------|--------|
| `planned -> claimed` event `policy_metadata` | Every claim path now carries `agent` (= claiming actor). API claims also carry the orchestrator policy keys and omit `shell_pid`/`shell_pid_created_at`. |
| `InnerStateChanged` on `* -> planned` via orchestrator-api | New: carries `release_runtime_claim=True` and an empty `review` override, identical to `move-task`. |
| `WorkPackageState.metadata["agent"]` (accept summary) | Display only: the slot value, falling back to the implementer of record. |
| Missing-implementer metadata issue | Raised when `review_roles` yields no implementer and the lane is not `canceled`. It carries a command only when `implementer_claim_target(lane)` returns a lane. |

## State transitions used by the hint

| Lane | Implementing target | Printed command |
|------|---------------------|-----------------|
| planned | claimed | `spec-kitty agent action implement <WP> --agent <name>` |
| claimed | in_progress | `spec-kitty agent action implement <WP> --agent <name>` |
| blocked | in_progress | `spec-kitty agent tasks move-task <WP> --to in_progress --agent <name>` |
| in_progress | none (already implementing) | none |
| for_review, in_review, approved | none (an exit is a review verdict) | none |
| done, canceled | none (no targets) | none |
