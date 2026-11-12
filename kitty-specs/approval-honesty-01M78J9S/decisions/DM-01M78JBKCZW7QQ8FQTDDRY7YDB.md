# Decision Moment `01M78JBKCZW7QQ8FQTDDRY7YDB`

- **Mission:** `approval-honesty-01M78J9S`
- **Origin flow:** `specify`
- **Slot key:** `review_cycles`
- **Input key:** `review_cycles`
- **Status:** `resolved`
- **Created:** `2026-11-12T19:04:38.047874+00:00`
- **Resolved:** `2026-11-12T19:04:40.018571+00:00`
- **Resolved by:** `operator`
- **Opened by:** `claude`
- **Other answer:** `false`

## Question

How are duplicate cycles (#7571) and uncited cycles (#7570) fixed?

## Options

_(none)_

## Final answer

Adopt + verify: adopt an approved review-cycle artifact written after the current in_review claim instead of writing N+1; otherwise write as today. A review-cycle:// --approval-ref or a note citing cycle N must resolve to an existing artifact, else refuse naming the missing path. No backfill of append-only event logs; follow-up issue for a doctor/flag report.

## Rationale

Operator ruling 2026-11-12 (recommended option).

## Change log

- `2026-11-12T19:04:38.047874+00:00` - opened
- `2026-11-12T19:04:40.018571+00:00` - resolved (final_answer="Adopt + verify: adopt an approved review-cycle artifact written after the current in_review claim instead of writing N+1; otherwise write as today. A review-cycle:// --approval-ref or a note citing cycle N must resolve to an existing artifact, else refuse naming the missing path. No backfill of append-only event logs; follow-up issue for a doctor/flag report.")
