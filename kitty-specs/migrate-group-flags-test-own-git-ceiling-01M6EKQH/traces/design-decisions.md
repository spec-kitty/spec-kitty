# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-11-02 · python-pedro · Kept the fix tests-only. `_flip_phase`'s PlacementMismatchError fail-close and the harness ceiling from #7022 are the correct safety properties; the defect was this module's undeclared dependency on a process-wide GIT_CEILING_DIRECTORIES. The fixture now appends its own tmp_path (append-only, monkeypatch-restored), matching tests/specify_cli/migration/test_runtime_state_cutover_placement.py.
