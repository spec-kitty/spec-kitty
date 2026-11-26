# Trace: design-decisions

Mission approved-lane-resolution-route-01M7WW0Z (mission-tracer-files procedure). Append entries during implementation; WP history notes tagged trace(design-decisions) are folded in here.

- 2026-11-20: Operator ruled approach A+B+E, rejected C, and sent D′ to #7324. Rulings DM-01M7WW1RVG4TQ9S2CABCCVK9G9 and DM-01M7WX8AX56E23AXBZRWGNX4EM (`--incorporate`).
- 2026-11-20: Durable auto-rebase record as refs (R-03). The FR-004 predicate is shared with the gate (R-04).
- 2026-11-20: `LANE_MOVED_SINCE_AUTO_REBASE` counts as settled and keeps its record (WP03). `--incorporate` exits 0 on a conflict (WP08). Both can be overruled by the operator.
- 2026-11-20 operator rulings: FR-010 option (a) (committed built-in union/set honoured only when `check-attr --source <pre-run target tip>` matches and no driver is configured; clone-local sources and git < 2.40 refuse). WP03 `LANE_MOVED_SINCE_AUTO_REBASE` accepted. WP08 `--incorporate` exits non-zero on a conflict (overrides the exit-0 draft).
