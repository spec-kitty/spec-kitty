# Decision Moment `01M3TZHQVRFJW8PYRF0K4NBJET`

- **Mission:** `ci-runtime-stabilisation-01M3TZH6`
- **Origin flow:** `specify`
- **Slot key:** `specify.ci.main-push-concurrency`
- **Input key:** `main_push_concurrency`
- **Status:** `resolved`
- **Created:** `2026-10-01T05:38:43.192917+00:00`
- **Resolved:** `2026-10-01T05:38:44.728409+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

CI Modules/Packs/Aggregate cancel main pushes per ref, leaving cancelled tips untested until nightly. Fix?

## Options

- Per-SHA like #4347
- Cancel but diff vs last completed run
- Out of scope
- Other

## Final answer

Out of scope (deferred to #5511 under #4437)

## Rationale

_(none)_

## Change log

- `2026-10-01T05:38:43.192917+00:00` — opened
- `2026-10-01T05:38:44.728409+00:00` — resolved (final_answer="Out of scope (deferred to #5511 under #4437)")
