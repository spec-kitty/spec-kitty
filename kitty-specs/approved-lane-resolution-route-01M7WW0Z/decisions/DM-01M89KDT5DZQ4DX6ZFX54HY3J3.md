# Decision Moment `01M89KDT5DZQ4DX6ZFX54HY3J3`

- **Mission:** `approved-lane-resolution-route-01M7WW0Z`
- **Origin flow:** `plan`
- **Slot key:** `plan.wp07.reopen-route`
- **Input key:** `wp07_reopen_route_protected_target`
- **Status:** `resolved`
- **Created:** `2026-11-25T14:58:15.342077+00:00`
- **Resolved:** `2026-11-25T14:58:20.297899+00:00`
- **Opened by:** `operator`
- **Other answer:** `false`

## Question

Main's #7754 reopen step 'move-task <WP> --to planned --review-feedback-file' exits 1 on a coordination Mission whose target is protected main. Should WP07 print the move-back form (a), or keep main's text and fix move-task (b)?

## Options

_(none)_

## Final answer

Option (b): KEEP main's reopen text (move-task <WP> --to planned --review-feedback-file ...) and FIX move-task --to planned on a coordination Mission whose target is protected main. Two things must hold: (1) the verdict evidence commit lands on the allowed branch (coordination), never on the protected target; (2) after the reopen, implement finds the review feedback artifact. Red-first on the two real-git fixtures. Folded into this Mission. Also fold the --agent token into main's no-sibling remedy line. File the main-bug issue and close it with this Mission. (operator, 2026-11-25)

## Rationale

_(none)_

## Change log

- `2026-11-25T14:58:15.342077+00:00` - opened
- `2026-11-25T14:58:20.297899+00:00` - resolved (final_answer="Option (b): KEEP main's reopen text (move-task <WP> --to planned --review-feedback-file ...) and FIX move-task --to planned on a coordination Mission whose target is protected main. Two things must hold: (1) the verdict evidence commit lands on the allowed branch (coordination), never on the protected target; (2) after the reopen, implement finds the review feedback artifact. Red-first on the two real-git fixtures. Folded into this Mission. Also fold the --agent token into main's no-sibling remedy line. File the main-bug issue and close it with this Mission. (operator, 2026-11-25)")
