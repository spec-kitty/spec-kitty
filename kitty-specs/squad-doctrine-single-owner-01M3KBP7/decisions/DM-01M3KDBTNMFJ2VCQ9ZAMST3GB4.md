# Decision Moment `01M3KDBTNMFJ2VCQ9ZAMST3GB4`

- **Mission:** `squad-doctrine-single-owner-01M3KBP7`
- **Origin flow:** `specify`
- **Slot key:** `specify.testing.p0_carveout`
- **Input key:** `bugfix_commit_topology`
- **Status:** `resolved`
- **Created:** `2026-09-28T07:06:14.069089+00:00`
- **Resolved:** `2026-09-28T07:06:16.556892+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

#5220 item 3: test and fix committed together?

## Options

_(none)_

## Final answer

Default: together, unless a failing reproduction test already landed on the mainline under red-main-release-discipline; then the fix commit turns that test green.

## Rationale

_(none)_

## Change log

- `2026-09-28T07:06:14.069089+00:00` — opened
- `2026-09-28T07:06:16.556892+00:00` — resolved (final_answer="Default: together, unless a failing reproduction test already landed on the mainline under red-main-release-discipline; then the fix commit turns that test green.")
