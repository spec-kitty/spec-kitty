# Decision Moment `01M6HAJAX5Z0K6A271EHAZXX24`

- **Mission:** `owned-files-unresolved-fail-closed-01M6HAHF`
- **Origin flow:** `specify`
- **Slot key:** `specify.verdict.trigger`
- **Input key:** `verdict_trigger`
- **Status:** `resolved`
- **Created:** `2026-11-03T18:25:58.181887+00:00`
- **Resolved:** `2026-11-03T18:25:59.414675+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

What exactly counts as unresolved ownership for an approved work package?

## Options

_(none)_

## Final answer

An approved WP is unresolved when its owned_files yield no patterns: the tasks/ directory is missing, the WP's task file is absent or unreadable, or the file declares no owned_files (missing or empty list). The refusal names the directory or file read. It is checked before the implementation-missing test, so IMPLEMENTATION_MISSING is reported only when ownership resolved and the window has no owned change.

## Rationale

_(none)_

## Change log

- `2026-11-03T18:25:58.181887+00:00` - opened
- `2026-11-03T18:25:59.414675+00:00` - resolved (final_answer="An approved WP is unresolved when its owned_files yield no patterns: the tasks/ directory is missing, the WP's task file is absent or unreadable, or the file declares no owned_files (missing or empty list). The refusal names the directory or file read. It is checked before the implementation-missing test, so IMPLEMENTATION_MISSING is reported only when ownership resolved and the window has no owned change.")
