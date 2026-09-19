# Decision Moment `01M28XMB432H0PPSHG8J3V4VG5`

- **Mission:** `drupal-dries-profile-01M28X69`
- **Origin flow:** `specify`
- **Slot key:** `specify.tooling.environment-assumption`
- **Input key:** `environment_assumption`
- **Status:** `resolved`
- **Created:** `2026-09-11T19:03:09.699760+00:00`
- **Resolved:** `2026-09-11T19:04:07.630095+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

Which local environment should the self-review commands assume: vanilla host tooling (php/composer/drush directly), containerized (ddev/lando prefixes), or environment-agnostic?

## Options

- vanilla-host
- containerized
- environment-agnostic
- Other

## Final answer

environment-agnostic: self-review commands written as bare composer/drush/phpcs/phpunit with an explicit note that containerized setups (ddev/lando) prefix them.

## Rationale

_(none)_

## Change log

- `2026-09-11T19:03:09.699760+00:00` — opened
- `2026-09-11T19:04:07.630095+00:00` — resolved (final_answer="environment-agnostic: self-review commands written as bare composer/drush/phpcs/phpunit with an explicit note that containerized setups (ddev/lando) prefix them.")
