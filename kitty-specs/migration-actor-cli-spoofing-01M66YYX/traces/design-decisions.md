# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-30 · python-pedro · Option 1 (refuse at the caller boundary) over option 2 (an explicit seed field): option 2 changes the spec_kitty_events contract and the frozen Java write core (spec-kitty-events#92, ADR 2026-10-29-1), which this mission may not touch. The refusal keeps the distinction structural: no caller-facing option can produce a migration: actor, and the in-process writers bypass the emit shell.
