# Decision Moment `01M3V70QMK2T4TB61V5EVAECQG`

- **Mission:** `coord-artifact-single-home-01M3V4BE`
- **Origin flow:** `plan`
- **Slot key:** `plan.design.pin-refresh-refusal`
- **Input key:** `pin_refresh_refusal`
- **Status:** `resolved`
- **Created:** `2026-10-01T07:49:14.515655+00:00`
- **Resolved:** `2026-10-01T07:52:44.504381+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

When the automatic planning_commit_sha refresh is refused by the advance-only rule, should finalize-tasks warn or fail?

## Options

_(none)_

## Final answer

Warn and continue: keep the old pin, print a warning naming both commits and the manual --refresh-planning-commit route.

## Rationale

_(none)_

## Change log

- `2026-10-01T07:49:14.515655+00:00` — opened
- `2026-10-01T07:52:44.504381+00:00` — resolved (final_answer="Warn and continue: keep the old pin, print a warning naming both commits and the manual --refresh-planning-commit route.")
