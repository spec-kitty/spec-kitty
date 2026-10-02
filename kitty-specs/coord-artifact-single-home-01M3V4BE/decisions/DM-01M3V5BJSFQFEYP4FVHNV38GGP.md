# Decision Moment `01M3V5BJSFQFEYP4FVHNV38GGP`

- **Mission:** `coord-artifact-single-home-01M3V4BE`
- **Origin flow:** `specify`
- **Slot key:** `specify.design.fork-check`
- **Input key:** `fork_check`
- **Status:** `resolved`
- **Created:** `2026-10-01T07:20:12.847581+00:00`
- **Resolved:** `2026-10-01T07:20:14.671358+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

When does the fork check run and what is the exit for an already-forked Mission?

## Options

_(none)_

## Final answer

Seed-time only (EMPTY -> seed transition): carry over when one event-id sequence is a prefix of the other, refuse with a fork diagnostic when both are non-empty and neither is a prefix. Already-materialized forked Missions keep writing to the coordination surface (no lockout); doctor decisions reports the fork, decision verify is not clean, --repair never drops and prints reconcile steps; the operator's exit is following those steps.

## Rationale

_(none)_

## Change log

- `2026-10-01T07:20:12.847581+00:00` — opened
- `2026-10-01T07:20:14.671358+00:00` — resolved (final_answer="Seed-time only (EMPTY -> seed transition): carry over when one event-id sequence is a prefix of the other, refuse with a fork diagnostic when both are non-empty and neither is a prefix. Already-materialized forked Missions keep writing to the coordination surface (no lockout); doctor decisions reports the fork, decision verify is not clean, --repair never drops and prints reconcile steps; the operator's exit is following those steps.")
