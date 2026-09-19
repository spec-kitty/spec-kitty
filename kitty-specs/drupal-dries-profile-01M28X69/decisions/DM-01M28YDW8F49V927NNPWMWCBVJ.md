# Decision Moment `01M28YDW8F49V927NNPWMWCBVJ`

- **Mission:** `drupal-dries-profile-01M28X69`
- **Origin flow:** `plan`
- **Slot key:** `plan.artifacts.styleguide-split`
- **Input key:** `styleguide_split`
- **Status:** `resolved`
- **Created:** `2026-09-11T19:17:06.447426+00:00`
- **Resolved:** `2026-09-11T19:20:12.113782+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

Should Drupal conventions be one styleguide artifact (~400+ lines, well above the 158-170 line peer norm) or split into conventions plus a separate security/performance guide?

## Options

- single-conventions-guide
- split-conventions-and-security
- Other

## Final answer

split-conventions-and-security: two styleguide artifacts — drupal-conventions (style, DI, entity/plugin/hook/form/routing patterns, theming, 14 anti-patterns) and drupal-security-performance (sanitization, access checks, cacheability, query discipline). Each targets the 150-200 line peer norm.

## Rationale

_(none)_

## Change log

- `2026-09-11T19:17:06.447426+00:00` — opened
- `2026-09-11T19:20:12.113782+00:00` — resolved (final_answer="split-conventions-and-security: two styleguide artifacts — drupal-conventions (style, DI, entity/plugin/hook/form/routing patterns, theming, 14 anti-patterns) and drupal-security-performance (sanitization, access checks, cacheability, query discipline). Each targets the 150-200 line peer norm.")
