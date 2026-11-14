# Decision Moment `01M7DW21P5D4WNVCGC6ARASAV3`

- **Mission:** `coordless-commit-checkout-01M7DW13`
- **Origin flow:** `specify`
- **Slot key:** `specify.scope.write-ref-held-elsewhere`
- **Input key:** `write_ref_held_elsewhere`
- **Status:** `resolved`
- **Created:** `2026-11-14T20:30:22.917612+00:00`
- **Resolved:** `2026-11-14T20:46:07.570916+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

#7633 shape (a) and the lane-holder row: the seam's checkout cannot hold a branch another checkout holds. Refuse up front with the same named code, refuse late (SafeCommitHeadMismatch), or keep today's holder routing?

## Options

- refuse up front, same code
- refuse late
- keep holder routing
- Other

## Final answer

Option 1 (operator ruling, relayed 2026-11-14): one up-front check in the coordination-less arm; refuse before any write with STATUS_WRITE_CHECKOUT_NOT_ON_WRITE_BRANCH, naming the holder and the remedy; covers (a), (b) and the lane-holder row; changelog entry for the (a) behaviour change.

## Rationale

_(none)_

## Change log

- `2026-11-14T20:30:22.917612+00:00` - opened
- `2026-11-14T20:46:07.570916+00:00` - resolved (final_answer="Option 1 (operator ruling, relayed 2026-11-14): one up-front check in the coordination-less arm; refuse before any write with STATUS_WRITE_CHECKOUT_NOT_ON_WRITE_BRANCH, naming the holder and the remedy; covers (a), (b) and the lane-holder row; changelog entry for the (a) behaviour change.")
