# Decision Moment `01M7X1RECT6FH6ZM1ZB97FMZVC`

- **Mission:** `stale-lane-sibling-recovery-01M7X1QS`
- **Origin flow:** `specify`
- **Slot key:** `specify.remedy.route`
- **Input key:** `remedy_route`
- **Status:** `resolved`
- **Created:** `2026-11-20T17:58:36.186862+00:00`
- **Resolved:** `2026-11-20T17:58:38.907186+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

Which recovery route does the refusal prescribe for an approved work package?

## Options

_(none)_

## Final answer

Reopen the WP (move-task --to planned --review-feedback-file, costs a re-review), re-enter it with agent action implement (names the lane checkout), merge the named sibling lane branch there and resolve, commit, hand back for review and approval, re-run consolidate. Verified end to end in an exploratory run: the next consolidate passes the lane and reconciliation verifies. A refusal with no sibling lane keeps the implement auto-rebase refresh, preceded by the reopen step (#7754).

## Rationale

_(none)_

## Change log

- `2026-11-20T17:58:36.186862+00:00` - opened
- `2026-11-20T17:58:38.907186+00:00` - resolved (final_answer="Reopen the WP (move-task --to planned --review-feedback-file, costs a re-review), re-enter it with agent action implement (names the lane checkout), merge the named sibling lane branch there and resolve, commit, hand back for review and approval, re-run consolidate. Verified end to end in an exploratory run: the next consolidate passes the lane and reconciliation verifies. A refusal with no sibling lane keeps the implement auto-rebase refresh, preceded by the reopen step (#7754).")
