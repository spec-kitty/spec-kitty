# Decision Moment `01M78JC7ZBJM0CY442BKDGBP7V`

- **Mission:** `coord-closeout-leftovers-01M78FRR`
- **Origin flow:** `plan`
- **Slot key:** `plan.reclaim.tip-record`
- **Input key:** `r1_tip_record`
- **Status:** `resolved`
- **Created:** `2026-11-12T19:04:59.115689+00:00`
- **Resolved:** `2026-11-12T19:05:04.059502+00:00`
- **Resolved by:** `operator`
- **Opened by:** `claude`
- **Other answer:** `false`

## Question

#4041: where does consolidate record the coordination tip its verified landing covered?

## Options

_(none)_

## Final answer

Git ref refs/spec-kitty/landed-coordination/<coordination branch>, written at the verified coordination tip after reconciliation PASS and advanced when teardown proves late commits. Reclaim requires merged_at AND live coordination tip == or ancestor of the ref; legacy Missions without the ref refuse.

## Rationale

Operator ruling 2026-11-12; avoids the circular meta.json commit and survives record clearing.

## Change log

- `2026-11-12T19:04:59.115689+00:00` - opened
- `2026-11-12T19:05:04.059502+00:00` - resolved (final_answer="Git ref refs/spec-kitty/landed-coordination/<coordination branch>, written at the verified coordination tip after reconciliation PASS and advanced when teardown proves late commits. Reclaim requires merged_at AND live coordination tip == or ancestor of the ref; legacy Missions without the ref refuse.")
