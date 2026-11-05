# Decision Moment `01M6KZQ0M9R8YCB5Y0MSCCDMDR`

- **Mission:** `landed-worktree-cleanup-01M6KZNP`
- **Origin flow:** `specify`
- **Slot key:** `specify.proof.offline`
- **Input key:** `landed_proof_source`
- **Status:** `resolved`
- **Created:** `2026-11-04T19:14:00.457945+00:00`
- **Resolved:** `2026-11-04T19:14:02.907657+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

Is an offline proof of landed enough?

## Options

_(none)_

## Final answer

Offline only: lane_tip.is_absorbed against the local origin/<primary> ref, no fetch, no GitHub lookup; fail closed without git >= 2.38.

## Rationale

_(none)_

## Change log

- `2026-11-04T19:14:00.457945+00:00` - opened
- `2026-11-04T19:14:02.907657+00:00` - resolved (final_answer="Offline only: lane_tip.is_absorbed against the local origin/<primary> ref, no fetch, no GitHub lookup; fail closed without git >= 2.38.")
