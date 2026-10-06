# Decision Moment `01M490G3K9WRBMAQTNVQWK4300`

- **Mission:** `runtime-bridge-query-seam-01M490EQ`
- **Origin flow:** `specify`
- **Slot key:** `specify.tests.false_green`
- **Input key:** `false_green_policy`
- **Status:** `resolved`
- **Created:** `2026-10-06T16:24:40.297722+00:00`
- **Resolved:** `2026-10-06T16:24:44.595656+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

How are test patches of runtime_bridge names that stop intercepting after the move handled?

## Options

- drop unused imports so stale patches fail loudly, then review remaining shared-name patches by call path and repoint with proof the fake ran
- leave as-is
- Other

## Final answer

drop unused imports so stale patches fail loudly, then review remaining shared-name patches by call path and repoint with proof the fake ran (operator brief acceptance criterion)

## Rationale

_(none)_

## Change log

- `2026-10-06T16:24:40.297722+00:00` — opened
- `2026-10-06T16:24:44.595656+00:00` — resolved (final_answer="drop unused imports so stale patches fail loudly, then review remaining shared-name patches by call path and repoint with proof the fake ran (operator brief acceptance criterion)")
