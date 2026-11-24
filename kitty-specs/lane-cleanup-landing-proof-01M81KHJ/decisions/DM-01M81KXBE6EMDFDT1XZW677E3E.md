# Decision Moment `01M81KXBE6EMDFDT1XZW677E3E`

- **Mission:** `lane-cleanup-landing-proof-01M81KHJ`
- **Origin flow:** `specify`
- **Slot key:** `specify.proof.squash_authorship`
- **Input key:** `squash_authorship`
- **Status:** `resolved`
- **Created:** `2026-11-22T12:32:49.094693+00:00`
- **Resolved:** `2026-11-23T07:19:01.245845+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

After a squash landing the coordination history is gone from the target. How is 'the lane never authored it' proven: (A) from the lane's own commit graph, or (B) from the target plus a recorded coordination tip?

## Options

- A: lane graph
- B: recorded coordination tip
- Other

## Final answer

A: lane graph. Operator ruling 2026-11-23 (dispatcher ledger R71): a Mission bookkeeping file (status.json, meta.json, tasks/WP*.md of the lane's own Mission) is set aside only when both lane and target have it and no lane-own first-parent commit changed it, except a merge whose result equals its non-first parent's version; any merge-driver or conflict result counts as authored. status.events.jsonl keeps line containment; membership in the target's history still passes. One predicate for consolidate and doctor; everything else fails closed. The residual (a version merged in from a non-coordination branch) is recorded in the ADR 2026-11-06-1 amendment.

## Rationale

_(none)_

## Change log

- `2026-11-22T12:32:49.094693+00:00` - opened
- `2026-11-23T07:19:01.245845+00:00` - resolved (final_answer="A: lane graph. Operator ruling 2026-11-23 (dispatcher ledger R71): a Mission bookkeeping file (status.json, meta.json, tasks/WP*.md of the lane's own Mission) is set aside only when both lane and target have it and no lane-own first-parent commit changed it, except a merge whose result equals its non-first parent's version; any merge-driver or conflict result counts as authored. status.events.jsonl keeps line containment; membership in the target's history still passes. One predicate for consolidate and doctor; everything else fails closed. The residual (a version merged in from a non-coordination branch) is recorded in the ADR 2026-11-06-1 amendment.")
