# Decision Moment `01M3KDBNH3JE2GCW3S34S7Z52P`

- **Mission:** `squad-doctrine-single-owner-01M3KBP7`
- **Origin flow:** `specify`
- **Slot key:** `specify.testing.tidy_first`
- **Input key:** `bugfix_tidy_first`
- **Status:** `resolved`
- **Created:** `2026-09-28T07:06:08.803670+00:00`
- **Resolved:** `2026-09-28T07:06:11.237833+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

#5220 item 1: where does tidy-first sit in a bug fix?

## Options

_(none)_

## Final answer

Default: DIRECTIVE_025 owns it. Tidy-first is a separate behaviour-preserving commit on the surfaces the fix will touch, before the red repro; refactor-after-green in test-first-bug-fixing is limited to the fix's own code.

## Rationale

_(none)_

## Change log

- `2026-09-28T07:06:08.803670+00:00` — opened
- `2026-09-28T07:06:11.237833+00:00` — resolved (final_answer="Default: DIRECTIVE_025 owns it. Tidy-first is a separate behaviour-preserving commit on the surfaces the fix will touch, before the red repro; refactor-after-green in test-first-bug-fixing is limited to the fix's own code.")
