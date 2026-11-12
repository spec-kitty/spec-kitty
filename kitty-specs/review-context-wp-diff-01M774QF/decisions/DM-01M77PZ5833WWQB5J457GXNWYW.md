# Decision Moment `01M77PZ5833WWQB5J457GXNWYW`

- **Mission:** `review-context-wp-diff-01M774QF`
- **Origin flow:** `plan`
- **Slot key:** `nfr002_derived_budget`
- **Input key:** `nfr002_derived_budget`
- **Status:** `resolved`
- **Created:** `2026-11-12T11:05:58.787175+00:00`
- **Resolved:** `2026-11-12T11:06:10.401806+00:00`
- **Resolved by:** `orchestrator`
- **Opened by:** `orchestrator`
- **Other answer:** `false`

## Question

NFR-002 caps the review range at 10 git calls. Since WP02's stamps, a commit-to-target Mission whose events predate the stamps (the DERIVED path) costs a constant 11: read_lane_head now returns the target head, so the moved-past rev-parse + rev-list run. Split the budget (recorded <=10, derived <=12, both constant), or cut a production call (drop the moved-past note on derived ranges / merge a race-guard probe)?

## Options

- Split budget: recorded <=10, derived <=12 (Recommended)
- Drop moved-past note on derived ranges
- Merge a race-guard probe

## Final answer

Split budget: recorded <=10, derived <=12 (Recommended)

## Rationale

The derived path now serves only commit-to-target Missions whose events predate the #7578 stamps; its cost stays constant (11, independent of range size), which is NFR-002's intent. Cutting the moved-past note would hide a real fact from the reviewer; merging a race-guard probe weakens a correctness guard. No refusal, exit code, gate severity or ADR behaviour changes, so this is not an operator escalation; flagged in the PR.

## Change log

- `2026-11-12T11:05:58.787175+00:00` - opened
- `2026-11-12T11:06:10.401806+00:00` - resolved (final_answer="Split budget: recorded <=10, derived <=12 (Recommended)")
