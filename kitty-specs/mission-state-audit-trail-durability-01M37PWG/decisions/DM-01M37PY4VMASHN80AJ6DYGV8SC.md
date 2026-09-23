# Decision Moment `01M37PY4VMASHN80AJ6DYGV8SC`

- **Mission:** `mission-state-audit-trail-durability-01M37PWG`
- **Origin flow:** `specify`
- **Slot key:** `specify.audit-trail.fix-direction`
- **Input key:** `fix_direction`
- **Status:** `resolved`
- **Created:** `2026-09-23T18:02:38.324160+00:00`
- **Resolved:** `2026-09-23T18:06:48.774553+00:00`
- **Resolved by:** `stijn-dejongh`
- **Opened by:** `claude`
- **Other answer:** `false`

## Question

How should doctor mission-state --fix make its audit trail durable/visible: relocate manifest+quarantine to a git-tracked path, warn the operator at exit that the artifacts are untracked, or both?

## Options

- relocate-to-tracked-path
- warn-at-exit-only
- both-relocate-and-warn
- Other

## Final answer

both-relocate-and-warn

## Rationale

Operator chose strongest durability+visibility: relocate manifest+quarantine to a git-tracked path AND print an operator-visible summary of what was written/quarantined at --fix exit.

## Change log

- `2026-09-23T18:02:38.324160+00:00` — opened
- `2026-09-23T18:06:48.774553+00:00` — resolved (final_answer="both-relocate-and-warn")
