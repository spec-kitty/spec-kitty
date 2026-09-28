# Decision Moment `01M3JCYVZ6TBD6HZZF4CDEHRBE`

- **Mission:** `python-interpreter-surface-honesty-01M3JCW8`
- **Origin flow:** `specify`
- **Slot key:** `specify.scope.py314-surface`
- **Input key:** `py314_surface_strategy`
- **Status:** `resolved`
- **Created:** `2026-09-27T21:39:54.982563+00:00`
- **Resolved:** `2026-09-27T22:17:18.160259+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

How should the declared and tested Python surfaces agree for 3.14?

## Options

- Advisory 3.14 canary + guard test
- Upper-bound requires-python <3.14
- Guard test only
- Other

## Final answer

Advisory 3.14 canary + guard test (operator choice 2026-09-27); sequenced after #5244 because it edits the same nightly workflow and helpers

## Rationale

_(none)_

## Change log

- `2026-09-27T21:39:54.982563+00:00` — opened
- `2026-09-27T22:17:18.160259+00:00` — resolved (final_answer="Advisory 3.14 canary + guard test (operator choice 2026-09-27); sequenced after #5244 because it edits the same nightly workflow and helpers")
