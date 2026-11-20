# Trace: design-decisions

Mission approved-lane-resolution-route-01M7WW0Z (mission-tracer-files procedure). Append entries during implementation; WP history notes tagged trace(design-decisions) are folded in here.

- 2026-11-20: Operator ruled approach A+B+E, rejected C, and sent D′ to #7324. Rulings DM-01M7WW1RVG4TQ9S2CABCCVK9G9 and DM-01M7WX8AX56E23AXBZRWGNX4EM (`--incorporate`).
- 2026-11-20: Durable auto-rebase record as refs (R-03). The FR-004 predicate is shared with the gate (R-04).
- 2026-11-20: `LANE_MOVED_SINCE_AUTO_REBASE` counts as settled and keeps its record (WP03). `--incorporate` exits 0 on a conflict (WP08). Both can be overruled by the operator.
- Pending: FR-010 committed-attribute question. Default (a) honours committed built-ins verified via `check-attr --source`.
