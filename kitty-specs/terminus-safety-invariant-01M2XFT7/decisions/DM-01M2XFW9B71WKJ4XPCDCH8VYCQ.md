# Decision Moment `01M2XFW9B71WKJ4XPCDCH8VYCQ`

- **Mission:** `terminus-safety-invariant-01M2XFT7`
- **Origin flow:** `specify`
- **Slot key:** `specify.policy.warn-gate-semantics`
- **Input key:** `warn_gate_semantics`
- **Status:** `resolved`
- **Created:** `2026-09-19T18:46:53.032020+00:00`
- **Resolved:** `2026-09-19T18:47:01.179040+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

What does policy.merge_gates.mode=warn soften — everything, or evidence-quality only while the terminal-lane invariant stays hard?

## Options

- evidence-quality-only
- everything

## Final answer

warn softens evidence-QUALITY gates only (review verdict/risk/hollow-review). The 'all non-cancelled WPs approved/done' terminal-lane invariant is enforced HARD regardless of mode => merge gets an unconditional merge-ready precondition, not a rollback-only fix.

## Rationale

_(none)_

## Change log

- `2026-09-19T18:46:53.032020+00:00` — opened
- `2026-09-19T18:47:01.179040+00:00` — resolved (final_answer="warn softens evidence-QUALITY gates only (review verdict/risk/hollow-review). The 'all non-cancelled WPs approved/done' terminal-lane invariant is enforced HARD regardless of mode => merge gets an unconditional merge-ready precondition, not a rollback-only fix.")
