# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-31 · claude:claude-opus-4-6:python-pedro · A held lock is a coded refusal, not a graceful skip: restamp_bundle_hash may skip (it runs after the command's write), but the activation RMW IS the command, so it waits the bounded 10s then refuses with CHARTER_SYNTHESIS_LOCK_HELD and writes nothing. Re-pinned the #6453 test that asserted the old unlocked save.
