# Decision Moment `01M3XF7ZVTN26Q17447HPQRGC6`

- **Mission:** `coord-artifact-single-home-01M3V4BE`
- **Origin flow:** `plan`
- **Slot key:** `plan.design.accept-primary-leg-ref`
- **Input key:** `accept_primary_leg_ref`
- **Status:** `resolved`
- **Created:** `2026-10-02T04:51:29.786490+00:00`
- **Resolved:** `2026-10-02T04:51:31.246613+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

accept run with HEAD != meta target_branch (11 existing fixtures model it): which ref does the PRIMARY residual leg commit to now that it goes through commit_for_mission?

## Options

_(none)_

## Final answer

(a) The PRIMARY residual leg commits on the same ref the accept meta.json commit lands on (pass that branch explicitly as the router's target_branch); the router's protected-branch guard still applies. Preserves base behaviour (C-008); no up-front 'accept must run on target' preflight. The 4 fixture re-pins that hid the regression are reverted.

## Rationale

_(none)_

## Change log

- `2026-10-02T04:51:29.786490+00:00` — opened
- `2026-10-02T04:51:31.246613+00:00` — resolved (final_answer="(a) The PRIMARY residual leg commits on the same ref the accept meta.json commit lands on (pass that branch explicitly as the router's target_branch); the router's protected-branch guard still applies. Preserves base behaviour (C-008); no up-front 'accept must run on target' preflight. The 4 fixture re-pins that hid the regression are reverted.")
