# Decision Moment `01M5ZBF17G07XDN9VP13PABYX3`

- **Mission:** `owned-refusal-shape-and-issue-matrix-migration-01M5ZBD5`
- **Origin flow:** `specify`
- **Slot key:** `specify.contract.mark-status-extras`
- **Input key:** `mark_status_extras`
- **Status:** `resolved`
- **Created:** `2026-10-27T18:55:18.768470+00:00`
- **Resolved:** `2026-10-27T18:57:24.841117+00:00`
- **Opened by:** `cli`
- **Other answer:** `true`

## Question

mark-status owned failure: drop its result keys (state_applied, event_ids, ...) under strict C2, or keep them beside ok/error?

## Options

- keep result keys beside C2 core
- drop to strict C2
- Other

## Final answer

keep them, nested in a context object beside the strict C2 core: {ok:false, error:{code,message}, context:{...}}

## Rationale

_(none)_

## Change log

- `2026-10-27T18:55:18.768470+00:00` — opened
- `2026-10-27T18:57:24.841117+00:00` — resolved (final_answer="keep them, nested in a context object beside the strict C2 core: {ok:false, error:{code,message}, context:{...}}")
