# Decision Moment `01M6R0QQM5FCPY736008AD4W6V`

- **Mission:** `lane-worktree-model-hardening-01M6QY1M`
- **Origin flow:** `plan`
- **Slot key:** `plan.topology.pr-bound-fallback`
- **Input key:** `pr_bound_fallback`
- **Status:** `resolved`
- **Created:** `2026-11-06T08:48:50.309351+00:00`
- **Resolved:** `2026-11-06T08:48:52.726729+00:00`
- **Resolved by:** `stijn-dejongh`
- **Opened by:** `claude`
- **Other answer:** `false`

## Question

A-5: keep the --pr-bound fallback to plain lanes when coordination is unreachable?

## Options

_(none)_

## Final answer

Drop the fallback: with the topic branch as the coordination branch the #2533 hazard no longer applies to default Missions; multi-lane settlement always yields lanes_with_coord; plain lanes stays explicit-only.

## Rationale

Operator answer, stijn-dejongh, 2026-11-06.

## Change log

- `2026-11-06T08:48:50.309351+00:00` - opened
- `2026-11-06T08:48:52.726729+00:00` - resolved (final_answer="Drop the fallback: with the topic branch as the coordination branch the #2533 hazard no longer applies to default Missions; multi-lane settlement always yields lanes_with_coord; plain lanes stays explicit-only.")
