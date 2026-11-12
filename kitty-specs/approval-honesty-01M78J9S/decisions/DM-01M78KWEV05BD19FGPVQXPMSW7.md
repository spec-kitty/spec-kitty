# Decision Moment `01M78KWEV05BD19FGPVQXPMSW7`

- **Mission:** `approval-honesty-01M78J9S`
- **Origin flow:** `plan`
- **Slot key:** `plan.refusals.claimant-remedy`
- **Input key:** `claimant_remedy`
- **Status:** `resolved`
- **Created:** `2026-11-12T19:31:19.008755+00:00`
- **Resolved:** `2026-11-12T19:31:21.163206+00:00`
- **Resolved by:** `operator`
- **Opened by:** `claude`
- **Other answer:** `false`

## Question

APPROVER_NOT_CLAIMANT remedy, given re-claim by another identity is refused as a claim collision?

## Options

_(none)_

## Final answer

Remedy: the claimant records the verdict (--agent <claimant>), or the operator uses --force (recorded as a forced move, never a review). No new handoff path. Supersedes the re-claim remedy of decision claimant_mismatch.

## Rationale

Operator ruling 2026-11-12; no in_review->for_review edge and reviewer-role claims collide.

## Change log

- `2026-11-12T19:31:19.008755+00:00` - opened
- `2026-11-12T19:31:21.163206+00:00` - resolved (final_answer="Remedy: the claimant records the verdict (--agent <claimant>), or the operator uses --force (recorded as a forced move, never a review). No new handoff path. Supersedes the re-claim remedy of decision claimant_mismatch.")
