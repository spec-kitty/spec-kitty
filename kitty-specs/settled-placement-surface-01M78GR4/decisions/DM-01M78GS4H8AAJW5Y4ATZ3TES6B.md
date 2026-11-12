# Decision Moment `01M78GS4H8AAJW5Y4ATZ3TES6B`

- **Mission:** `settled-placement-surface-01M78GR4`
- **Origin flow:** `specify`
- **Slot key:** `specify.guards.protected-check-input`
- **Input key:** `protected_check_input`
- **Status:** `resolved`
- **Created:** `2026-11-12T18:37:04.424121+00:00`
- **Resolved:** `2026-11-12T18:37:06.933564+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

What does implement's protected-status preflight (and move-task's metadata guard) judge?

## Options

- placement_seam.write_target(WORK_PACKAGE_TASK).ref
- HEAD of the claim commit checkout
- Other

## Final answer

placement_seam.write_target(WORK_PACKAGE_TASK).ref, draining allow-list entry #2453 in test_no_write_side_rederivation. Accepted side effect (note in PR): a flat Mission whose root HEAD differs from a protected target gets the protected refusal instead of the #5738 mismatch refusal; both still refuse. Operator ruling 2026-11-12.

## Rationale

_(none)_

## Change log

- `2026-11-12T18:37:04.424121+00:00` - opened
- `2026-11-12T18:37:06.933564+00:00` - resolved (final_answer="placement_seam.write_target(WORK_PACKAGE_TASK).ref, draining allow-list entry #2453 in test_no_write_side_rederivation. Accepted side effect (note in PR): a flat Mission whose root HEAD differs from a protected target gets the protected refusal instead of the #5738 mismatch refusal; both still refuse. Operator ruling 2026-11-12.")
