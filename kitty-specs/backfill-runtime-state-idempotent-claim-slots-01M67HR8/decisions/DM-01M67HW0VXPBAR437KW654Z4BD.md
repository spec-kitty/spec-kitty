# Decision Moment `01M67HW0VXPBAR437KW654Z4BD`

- **Mission:** `backfill-runtime-state-idempotent-claim-slots-01M67HR8`
- **Origin flow:** `plan`
- **Slot key:** `plan.fix.backward-compat`
- **Input key:** `prefix_row_compat`
- **Status:** `resolved`
- **Created:** `2026-10-30T23:21:11.293763+00:00`
- **Resolved:** `2026-10-30T23:21:15.194246+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

A project may already carry a pre-fix seed row whose persisted JSON has no mission_id key. Once the writer emits the declared id, that old row still reads back AS the declared id, so payload parity holds without a rewrite. Do we (a) rely on that read-back equivalence (events are immutable; no rewrite possible), or (b) add a repair path that rewrites old seed rows?

## Options

- a: rely on read-back equivalence, no rewrite
- b: add a seed-row repair/rewrite path

## Final answer

a: rely on read-back equivalence. Event rows are immutable and deduplicated on first write; the module's existing tolerance already accepts an old at / pre-#2985 payload, and an old row without mission_id reads back as the declared id, so parity holds with no rewrite. A rewrite path would be unreachable and would violate the append-only seam.

## Rationale

_(none)_

## Change log

- `2026-10-30T23:21:11.293763+00:00` — opened
- `2026-10-30T23:21:15.194246+00:00` — resolved (final_answer="a: rely on read-back equivalence. Event rows are immutable and deduplicated on first write; the module's existing tolerance already accepts an old at / pre-#2985 payload, and an old row without mission_id reads back as the declared id, so parity holds with no rewrite. A rewrite path would be unreachable and would violate the append-only seam.")
