# Decision Moment `01M3V02AV3002PNZYY8HFJ6DQF`

- **Mission:** `ci-runtime-stabilisation-01M3TZH6`
- **Origin flow:** `specify`
- **Slot key:** `specify.ci.skip-if-green-scope`
- **Input key:** `skip_if_green_scope`
- **Status:** `resolved`
- **Created:** `2026-10-01T05:47:46.915702+00:00`
- **Resolved:** `2026-10-01T05:47:48.499493+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

How far should the ready_for_review skip-if-green guard go (Aggregate fail-closed; required check passing on prior-run evidence)?

## Options

- Full, with ADR amendment
- Router + Packs only
- Drop FR-011
- Other

## Final answer

Full, with ADR amendment: Router, Modules and Packs via one scripts/ci helper; CI Aggregate reuses the matched run's coverage artifacts; amend ADR 2026-09-23-1

## Rationale

_(none)_

## Change log

- `2026-10-01T05:47:46.915702+00:00` — opened
- `2026-10-01T05:47:48.499493+00:00` — resolved (final_answer="Full, with ADR amendment: Router, Modules and Packs via one scripts/ci helper; CI Aggregate reuses the matched run's coverage artifacts; amend ADR 2026-09-23-1")
