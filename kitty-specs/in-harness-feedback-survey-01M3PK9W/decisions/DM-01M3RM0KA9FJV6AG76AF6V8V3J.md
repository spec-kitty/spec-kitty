# Decision Moment `01M3RM0KA9FJV6AG76AF6V8V3J`

- **Mission:** `in-harness-feedback-survey-01M3PK9W`
- **Origin flow:** `plan`
- **Slot key:** `plan.data.preferences-storage`
- **Input key:** `preferences_storage`
- **Status:** `resolved`
- **Created:** `2026-09-30T07:38:38.281646+00:00`
- **Resolved:** `2026-09-30T07:45:53.996247+00:00`
- **Opened by:** `cursor`
- **Other answer:** `false`

## Question

Where do survey preferences and throttle state live?

## Options

- One hardened feedback.json in the user config dir
- Split: preferences in user config dir, last-shown in user cache dir
- Other

## Final answer

One hardened feedback.json in the per-user config dir (prefs + last-shown), reusing upgrade-cache hardening

## Rationale

_(none)_

## Change log

- `2026-09-30T07:38:38.281646+00:00` — opened
- `2026-09-30T07:45:53.996247+00:00` — resolved (final_answer="One hardened feedback.json in the per-user config dir (prefs + last-shown), reusing upgrade-cache hardening")
