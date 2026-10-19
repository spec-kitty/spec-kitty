# Decision Moment `01M5ASPC7101YP5CQE54DC3G3Z`

- **Mission:** `charter-synthesis-graph-and-languages-01M59RZ5`
- **Origin flow:** `specify`
- **Slot key:** `specify.languages.non-interactive-store`
- **Input key:** `non_interactive_language_store`
- **Status:** `resolved`
- **Created:** `2026-10-19T19:19:56.385371+00:00`
- **Resolved:** `2026-10-19T19:20:00.463224+00:00`
- **Resolved by:** `stijn-dejongh`
- **Opened by:** `claude`
- **Other answer:** `true`

## Question

What does a non-interactive charter interview do when config.yaml has no languages list (#6444)?

## Options

_(none)_

## Final answer

Store the detected list, make the operator clearly aware (text and JSON: what was stored, that it was detected, how to change it), and apply the 20% rule: a secondary language is detected only when it holds at least 20% of the counted sources; a manifest alone only nominates a candidate.

## Rationale

Operator write-in 2026-10-19 on the WP07 review finding (tooling-only package.json).

## Change log

- `2026-10-19T19:19:56.385371+00:00` — opened
- `2026-10-19T19:20:00.463224+00:00` — resolved (final_answer="Store the detected list, make the operator clearly aware (text and JSON: what was stored, that it was detected, how to change it), and apply the 20% rule: a secondary language is detected only when it holds at least 20% of the counted sources; a manifest alone only nominates a candidate.")
