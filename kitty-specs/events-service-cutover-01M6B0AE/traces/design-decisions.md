# Design decisions — events-service cut-over

- **[2026-11-01][specify] dev-setup fetches extras only.** DM 01M6B0JYP9B0CMBWRQ7TR7GBVN; the 95 MB read-service binary is CI-only (ADR D-6).
- **[2026-11-01][plan] Unpack lives in `scripts/sync_services.py`, not `kernel`.** The dead-symbol gate needs `src/` callers for `kernel` exports; only scripts and tests unpack. Digest-keyed directories make stale trees unreachable after a pin bump.
- **[2026-11-01][plan] Tool and source-layout tests are deleted, not repointed.** They test code spec-kitty-events owns; the released tools differ and lack `tools/fixtures/`. Residual: port them to events.
- **[2026-11-01][plan] Oracle reads the bundle.** `resolve(bundle/<module>) == resolve(contracts/<module>)` for both modules, verified.
