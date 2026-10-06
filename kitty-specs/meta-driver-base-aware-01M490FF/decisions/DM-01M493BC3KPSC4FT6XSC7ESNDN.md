# Decision Moment `01M493BC3KPSC4FT6XSC7ESNDN`

- **Mission:** `meta-driver-base-aware-01M490FF`
- **Origin flow:** `plan`
- **Slot key:** `plan.scope.squash-ancestor`
- **Input key:** `squash_ancestor_policy`
- **Status:** `resolved`
- **Created:** `2026-10-06T17:14:30.899758+00:00`
- **Resolved:** `2026-10-06T20:25:34.666883+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

The mission-to-target squash records no ancestry, so after a reopen and a second consolidate git hands the driver the original fork point as %O; a 3-way merge then resurrects target-side content the mission removed. Should the squash path keep today's 2-way rule explicitly (consolidation opts out of base-awareness for its own merge; 3-way only for real merges/pulls), or should the 3-way rule apply everywhere with the stale-ancestor case recorded as a pinned residual?

## Options

- squash keeps the 2-way rule explicitly (recommended)
- 3-way everywhere, stale-ancestor residual pinned
- Other

## Final answer

squash keeps the 2-way rule explicitly (recommended)

## Rationale

_(none)_

## Change log

- `2026-10-06T17:14:30.899758+00:00` — opened
- `2026-10-06T20:25:34.666883+00:00` — resolved (final_answer="squash keeps the 2-way rule explicitly (recommended)")
