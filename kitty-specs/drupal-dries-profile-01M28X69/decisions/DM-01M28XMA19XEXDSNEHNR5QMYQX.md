# Decision Moment `01M28XMA19XEXDSNEHNR5QMYQX`

- **Mission:** `drupal-dries-profile-01M28X69`
- **Origin flow:** `specify`
- **Slot key:** `specify.scope.stack-breadth`
- **Input key:** `stack_breadth`
- **Status:** `resolved`
- **Created:** `2026-09-11T19:03:08.585315+00:00`
- **Resolved:** `2026-09-11T19:04:06.619569+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

Does Dries cover Drupal backend only, or also Drupal theming/frontend (Twig, libraries, JS behaviors)?

## Options

- backend-only
- backend-plus-theming
- Other

## Final answer

backend-plus-theming: Dries covers Drupal backend (modules, DI/services, Entity API, plugins, hooks, Forms API, routing, config, Batch/Queue/Migration) AND Drupal theming (Twig, *.libraries.yml, Drupal.behaviors, render arrays, preprocess). Overlap with frontend-freddy must be resolved by an explicit boundary: Dries owns Drupal-native theming layer; generic SPA/framework frontend work stays with Freddy.

## Rationale

_(none)_

## Change log

- `2026-09-11T19:03:08.585315+00:00` — opened
- `2026-09-11T19:04:06.619569+00:00` — resolved (final_answer="backend-plus-theming: Dries covers Drupal backend (modules, DI/services, Entity API, plugins, hooks, Forms API, routing, config, Batch/Queue/Migration) AND Drupal theming (Twig, *.libraries.yml, Drupal.behaviors, render arrays, preprocess). Overlap with frontend-freddy must be resolved by an explicit boundary: Dries owns Drupal-native theming layer; generic SPA/framework frontend work stays with Freddy.")
