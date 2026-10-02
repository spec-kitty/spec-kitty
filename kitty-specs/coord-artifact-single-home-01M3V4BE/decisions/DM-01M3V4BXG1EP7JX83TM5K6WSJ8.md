# Decision Moment `01M3V4BXG1EP7JX83TM5K6WSJ8`

- **Mission:** `coord-artifact-single-home-01M3V4BE`
- **Origin flow:** `specify`
- **Slot key:** `specify.scope.decision-ledger-partition`
- **Input key:** `decision_ledger_partition`
- **Status:** `resolved`
- **Created:** `2026-10-01T07:02:55.233476+00:00`
- **Resolved:** `2026-10-01T07:06:41.648010+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

#5023: reconcile the decision ledger (DM-*.md, index.json) by moving its classification to PRIMARY (matching where it is read and written today), or by moving its reads and writes to the coordination surface (matching its current COORD classification)?

## Options

- Classify as PRIMARY
- Move reads/writes to COORD
- Other

## Final answer

Classify as PRIMARY: DECISION_LEDGER (DM-*.md + index.json) moves to the PRIMARY partition, matching where it is read and written today; decision events stay in the COORD status log; doctor joins the two through the seam; ADR amendment records the reversal of the #3928 intent.

## Rationale

_(none)_

## Change log

- `2026-10-01T07:02:55.233476+00:00` — opened
- `2026-10-01T07:06:41.648010+00:00` — resolved (final_answer="Classify as PRIMARY: DECISION_LEDGER (DM-*.md + index.json) moves to the PRIMARY partition, matching where it is read and written today; decision events stay in the COORD status log; doctor joins the two through the seam; ADR amendment records the reversal of the #3928 intent.")
