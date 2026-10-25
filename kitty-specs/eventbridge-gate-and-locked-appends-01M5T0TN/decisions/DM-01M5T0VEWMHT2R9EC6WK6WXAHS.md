# Decision Moment `01M5T0VEWMHT2R9EC6WK6WXAHS`

- **Mission:** `eventbridge-gate-and-locked-appends-01M5T0TN`
- **Origin flow:** `specify`
- **Slot key:** `specify.appends.validation`
- **Input key:** `append_validation`
- **Status:** `resolved`
- **Created:** `2026-10-25T17:13:39.477067+00:00`
- **Resolved:** `2026-10-25T17:13:43.394735+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

Should the locked append validate rows strictly through spec_kitty_events.persistence (the library model) where one exists, or only add the lock, torn-tail refusal and single write?

## Options

- Lock + torn-tail + single write only, no new validation
- Strict library validation where a model exists
- Other

## Final answer

Lock + torn-tail + single write only, no new validation. Operator ruling 2026-10-25 (#6117 comment, decision 2): the Java write service is authoritative for validation; do not grow new Python-side validation authority. Each writer keeps its current row bytes.

## Rationale

_(none)_

## Change log

- `2026-10-25T17:13:39.477067+00:00` — opened
- `2026-10-25T17:13:43.394735+00:00` — resolved (final_answer="Lock + torn-tail + single write only, no new validation. Operator ruling 2026-10-25 (#6117 comment, decision 2): the Java write service is authoritative for validation; do not grow new Python-side validation authority. Each writer keeps its current row bytes.")
