# Decision Moment `01M78G590V8HGBR048SMBQK9WC`

- **Mission:** `coord-closeout-leftovers-01M78FRR`
- **Origin flow:** `specify`
- **Slot key:** `e7491`
- **Input key:** `e7491`
- **Status:** `resolved`
- **Created:** `2026-11-12T18:26:13.659876+00:00`
- **Resolved:** `2026-11-12T18:26:29.133844+00:00`
- **Resolved by:** `operator`
- **Opened by:** `claude`
- **Other answer:** `false`

## Question

#7491: how does consolidate --resume re-prove a landing in the late-coordination window?

## Options

_(none)_

## Final answer

Persist verified tip: save the post-projection coordination tip at reconciliation PASS; use it as the resume base only when landing_verified_for_resume; else pre_mutation_coord_sha. Cleared/restored with the PASS anchor.

## Rationale

Operator ruling 2026-11-12 (escalation before specify). Challenger showed a non-verified tip is unsound.

## Change log

- `2026-11-12T18:26:13.659876+00:00` - opened
- `2026-11-12T18:26:29.133844+00:00` - resolved (final_answer="Persist verified tip: save the post-projection coordination tip at reconciliation PASS; use it as the resume base only when landing_verified_for_resume; else pre_mutation_coord_sha. Cleared/restored with the PASS anchor.")
