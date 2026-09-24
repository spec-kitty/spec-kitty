# Decision Moment `01M380TSA29XFB3AXGCC92JSE5`

- **Mission:** `terminus-merge-integrity-01M380R6`
- **Origin flow:** `specify`
- **Slot key:** `specify.behavior.divergence_response`
- **Input key:** `divergence_response`
- **Status:** `resolved`
- **Created:** `2026-09-23T20:55:33.954040+00:00`
- **Resolved:** `2026-09-23T20:57:24.670082+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

When the Terminus Reconciliation Gate detects the target tree diverges from the claimed WP set, what is the command's contract?

## Options

- Refuse + non-zero + recovery instruction
- Attempt bounded auto-recovery then refuse
- Other

## Final answer

Refuse + non-zero exit + explicit recovery guidance; no teardown, no auto-mutation on a divergent tree.

## Rationale

_(none)_

## Change log

- `2026-09-23T20:55:33.954040+00:00` — opened
- `2026-09-23T20:57:24.670082+00:00` — resolved (final_answer="Refuse + non-zero exit + explicit recovery guidance; no teardown, no auto-mutation on a divergent tree.")
