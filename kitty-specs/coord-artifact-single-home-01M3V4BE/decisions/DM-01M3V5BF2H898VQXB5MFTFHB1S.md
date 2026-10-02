# Decision Moment `01M3V5BF2H898VQXB5MFTFHB1S`

- **Mission:** `coord-artifact-single-home-01M3V4BE`
- **Origin flow:** `specify`
- **Slot key:** `specify.design.seed-mechanism`
- **Input key:** `seed_mechanism`
- **Status:** `resolved`
- **Created:** `2026-10-01T07:20:09.041839+00:00`
- **Resolved:** `2026-10-01T07:20:10.917237+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

How does create seed the coordination surface?

## Options

_(none)_

## Final answer

Eager materialization at create: the coordination worktree is added at create and the creation records are committed on the coordination branch through the existing coordination commit path. Direct ref commit rejected: leaves the Mission UNMATERIALIZED (reads raise under ADR 2026-09-24-2) and trips assert_coord_write_materialized.

## Rationale

_(none)_

## Change log

- `2026-10-01T07:20:09.041839+00:00` — opened
- `2026-10-01T07:20:10.917237+00:00` — resolved (final_answer="Eager materialization at create: the coordination worktree is added at create and the creation records are committed on the coordination branch through the existing coordination commit path. Direct ref commit rejected: leaves the Mission UNMATERIALIZED (reads raise under ADR 2026-09-24-2) and trips assert_coord_write_materialized.")
