# Decision Moment `01M3RCRDBS2RKWVVZH07AZ1B4M`

- **Mission:** `single-rollback-authority-01M3RCP4`
- **Origin flow:** `specify`
- **Slot key:** `specify.rules.committed-bookkeeping-on-failure`
- **Input key:** `committed_bookkeeping_on_failure`
- **Status:** `resolved`
- **Created:** `2026-09-30T05:31:50.009814+00:00`
- **Resolved:** `2026-09-30T05:32:06.836059+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

When a consolidate step after the squash fails (bookkeeping commit, working-tree invariant), should the committed coordination done events and completed_wps survive for resume (today's #1826 contract) or be rolled back with every other branch to the pre-run snapshot?

## Options

- Roll everything back to the snapshot; re-pin the #1826 keep-done tests
- Keep committed done state for those phases (carve-out from the authority)
- Other

## Final answer

Roll everything back to the snapshot; re-pin the #1826 keep-done tests. Follows Stijn's ruling on #5385 (route every non-zero exit through rollback_to_snapshot) and ADR 2026-09-19-1 Amendment A3; a resume then re-runs from the snapshot. Default picked by the orchestrator and flagged in the PR.

## Rationale

_(none)_

## Change log

- `2026-09-30T05:31:50.009814+00:00` — opened
- `2026-09-30T05:32:06.836059+00:00` — resolved (final_answer="Roll everything back to the snapshot; re-pin the #1826 keep-done tests. Follows Stijn's ruling on #5385 (route every non-zero exit through rollback_to_snapshot) and ADR 2026-09-19-1 Amendment A3; a resume then re-runs from the snapshot. Default picked by the orchestrator and flagged in the PR.")
