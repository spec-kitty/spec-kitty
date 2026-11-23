# Decision Moment `01M84SZDGPKXA5PBJ6HM6HQX08`

- **Mission:** `setup-plan-coord-lifecycle-commit-01M84SXJ`
- **Origin flow:** `specify`
- **Slot key:** `specify.scope.default-mission-pre-settlement`
- **Input key:** `default_mission_pre_settlement_scope`
- **Status:** `open`
- **Created:** `2026-11-23T18:16:31.510306+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

A default Mission (created without --topology) has no coordination branch until finalize-tasks settles it, so setup-plan's lifecycle log rides the plan commit on its topic branch. Is that case in scope for this Mission?

## Options

- out of scope: no coordination branch exists yet; the log already rides the plan commit
- in scope
- Other

## Final answer

_(none)_

## Rationale

_(none)_

## Change log

- `2026-11-23T18:16:31.510306+00:00` - opened
