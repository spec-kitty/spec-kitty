# Decision Moment `01M43MY9BKY2BBJQN4D2GVM436`

- **Mission:** `single-branch-claim-gaps-01M43MVY`
- **Origin flow:** `specify`
- **Slot key:** `specify.occupancy.predicate`
- **Input key:** `occupancy_predicate`
- **Status:** `resolved`
- **Created:** `2026-10-04T14:26:29.875117+00:00`
- **Resolved:** `2026-10-04T14:26:42.323562+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

Which canonical predicate decides that a mission no longer occupies the write checkout?

## Options

_(none)_

## Final answer

Branch-scoped liveness: a WP occupies the write checkout only when its mission's write branch (mission_runtime.single_branch_write_ref over meta.json) is the branch the checkout is on, in addition to the existing is_mission_completed filter. Rationale: a single_branch mission's authoritative status surface is its write branch, so a status copy read on another branch is not live. The operator brief delegates the final choice to plan, where it is recorded with its authority.

## Rationale

_(none)_

## Change log

- `2026-10-04T14:26:29.875117+00:00` — opened
- `2026-10-04T14:26:42.323562+00:00` — resolved (final_answer="Branch-scoped liveness: a WP occupies the write checkout only when its mission's write branch (mission_runtime.single_branch_write_ref over meta.json) is the branch the checkout is on, in addition to the existing is_mission_completed filter. Rationale: a single_branch mission's authoritative status surface is its write branch, so a status copy read on another branch is not live. The operator brief delegates the final choice to plan, where it is recorded with its authority.")
