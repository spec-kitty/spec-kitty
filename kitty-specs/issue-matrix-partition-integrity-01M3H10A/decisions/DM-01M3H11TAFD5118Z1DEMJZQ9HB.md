# Decision Moment `01M3H11TAFD5118Z1DEMJZQ9HB`

- **Mission:** `issue-matrix-partition-integrity-01M3H10A`
- **Origin flow:** `specify`
- **Slot key:** `specify.scope.verdict-terminality`
- **Input key:** `verdict_terminality`
- **Status:** `resolved`
- **Created:** `2026-09-27T08:52:34.255942+00:00`
- **Resolved:** `2026-09-27T08:52:36.474812+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

How to handle #4943's second leg (merge records done bypassing the in-mission->done terminal-verdict rule)?

## Options

- Fold into this mission
- Carve as sibling follow-up
- Other

## Final answer

Fold into this mission: merge must apply the same terminal-verdict rule move-task applies, refusing (block) or warning when a gating row is still in-mission/unknown before the target advances.

## Rationale

_(none)_

## Change log

- `2026-09-27T08:52:34.255942+00:00` — opened
- `2026-09-27T08:52:36.474812+00:00` — resolved (final_answer="Fold into this mission: merge must apply the same terminal-verdict rule move-task applies, refusing (block) or warning when a gating row is still in-mission/unknown before the target advances.")
