# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-30 · python-pedro · Option 1 (refuse at the caller boundary) over option 2 (an explicit seed field): option 2 changes the spec_kitty_events contract and the frozen Java write core (spec-kitty-events#92, ADR 2026-10-29-1), which this mission may not touch. The refusal keeps the distinction structural: no caller-facing option can produce a migration: actor, and the in-process writers bypass the emit shell.

2026-10-30 · python-pedro · actor_from_option defaults to refusing (recorded=False) and the two recorded-identity replays opt in. That makes a future call site fail closed instead of silently re-opening the hole, and keeps the recorded-seed behaviour #6400 pinned.

2026-10-30 · python-pedro · The --agent arm stays allowed: a strict compact parse yields tool 'migration', which is_migration_actor does not classify as a seed, and the operator ruled it allowed on 2026-10-29. Refusing it too would be a second behaviour change with no security gain.
