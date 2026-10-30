# Tracer: tooling-friction

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-30 · maintainer-agent P19 (pi/deepseek-v4.1-flash-1017) · The issue asks for the gap table (G-15) and the migration-ledger writer row to be corrected, but docs/architecture/event-ledger-writers-and-readers.md is pinned by tests/architectural/test_events_import_frozen.py (blob c2943d49, ADR 2026-10-29-1 D-9). Editing it fails an always-on gate; re-pinning needs operator approval. Same blocker hit #6611. G-15 closure is deferred and the wording kept in the mission record.

2026-10-30 · pi (deepseek-v4.1-flash-1017) · Red-first proof for WP01 captured in two stages: (1) module import failed on the missing seam (MigrationLedgerLockTimeoutError/ledger_lock_path); (2) with the names stubbed but the lock unwired, test_concurrent_appends_keep_both_records failed with assert {'m_beta'} == {'m_alpha','m_beta'} (one record lost) and the wait/give-up tests failed. Both stages are the issue reproduced.
