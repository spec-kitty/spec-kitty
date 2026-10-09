# Decision Moment `01M4CYXSH8P2N42Z8KBCB06Z5F`

- **Mission:** `mission-writer-followups-01M4CYWW`
- **Origin flow:** `specify`
- **Slot key:** `specify.runtime.run-log-rollback`
- **Input key:** `run_log_rollback`
- **Status:** `resolved`
- **Created:** `2026-10-08T05:14:09.320297+00:00`
- **Resolved:** `2026-10-08T05:14:22.955287+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

#5884: how should the runtime run-log speculative rollback be fixed?

## Options

- Remove the rollback (gate as before_run_completed hook)
- Kernel verified truncate + run-dir lock
- Defer #5884

## Final answer

Remove the rollback (gate as before_run_completed hook)

## Rationale

_(none)_

## Change log

- `2026-10-08T05:14:09.320297+00:00` — opened
- `2026-10-08T05:14:22.955287+00:00` — resolved (final_answer="Remove the rollback (gate as before_run_completed hook)")
