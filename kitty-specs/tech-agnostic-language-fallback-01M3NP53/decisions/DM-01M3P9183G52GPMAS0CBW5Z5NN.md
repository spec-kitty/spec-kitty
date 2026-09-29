# Decision Moment `01M3P9183G52GPMAS0CBW5Z5NN`

- **Mission:** `tech-agnostic-language-fallback-01M3NP53`
- **Origin flow:** `plan`
- **Slot key:** `plan.language.declared-answer-wins`
- **Input key:** `declared_language_answer_authoritative`
- **Status:** `resolved`
- **Created:** `2026-09-29T09:48:16.368781+00:00`
- **Resolved:** `2026-09-29T09:48:19.751678+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

Which interview answers decide the project language?

## Options

- Declared answer wins
- Keep all-answer scan

## Final answer

Declared answer wins: when the languages/frameworks answer is a real declaration, resolve from it alone (built-in words + doctrine vocabulary combined); nothing matched -> [unknown]; other answers only scanned when that answer is empty/default/placeholder.

## Rationale

_(none)_

## Change log

- `2026-09-29T09:48:16.368781+00:00` — opened
- `2026-09-29T09:48:19.751678+00:00` — resolved (final_answer="Declared answer wins: when the languages/frameworks answer is a real declaration, resolve from it alone (built-in words + doctrine vocabulary combined); nothing matched -> [unknown]; other answers only scanned when that answer is empty/default/placeholder.")
