# Decision Moment `01M3SSV4FFQF6M2Q195JBKZ26N`

- **Mission:** `test-suite-remediation-01M3SSDW`
- **Origin flow:** `specify`
- **Slot key:** `specify.rules.unmasked-red-policy`
- **Input key:** `unmasked_red_policy`
- **Status:** `resolved`
- **Created:** `2026-09-30T18:39:45.135933+00:00`
- **Resolved:** `2026-09-30T18:40:41.555920+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

When a masked-green test is unmasked and goes red because it catches a real product defect, what happens?

## Options

- Fix small defects red-first in-mission; larger ones become an honest strict xfail citing a new open issue
- Always fix the product in-mission
- Always record as honest strict xfail + new open issue
- Other

## Final answer

Fix the product red-first in-mission when the fix fits one work package; otherwise keep the test as an honest strict xfail citing a newly filed open issue.

## Rationale

_(none)_

## Change log

- `2026-09-30T18:39:45.135933+00:00` — opened
- `2026-09-30T18:40:41.555920+00:00` — resolved (final_answer="Fix the product red-first in-mission when the fix fits one work package; otherwise keep the test as an honest strict xfail citing a newly filed open issue.")
