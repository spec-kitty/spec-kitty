# Decision Moment `01M3EVPPG6J6ZCPBA6AW7CEV04`

- **Mission:** `lane-branch-naming-authority-01M3EVC4`
- **Origin flow:** `specify`
- **Slot key:** `specify.merge.resume-unanchored-tips`
- **Input key:** `resume_unanchored_tips`
- **Status:** `resolved`
- **Created:** `2026-09-26T12:40:38.150352+00:00`
- **Resolved:** `2026-09-26T12:40:40.728783+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

A merge interrupted under the old code can resume with an empty lane-tip record. What should resume do?

## Options

- Refuse, name remedy
- Recompute tips
- Other

## Final answer

Refuse, name remedy (merge --abort); fail-closed like the coordination base anchor

## Rationale

_(none)_

## Change log

- `2026-09-26T12:40:38.150352+00:00` — opened
- `2026-09-26T12:40:40.728783+00:00` — resolved (final_answer="Refuse, name remedy (merge --abort); fail-closed like the coordination base anchor")
