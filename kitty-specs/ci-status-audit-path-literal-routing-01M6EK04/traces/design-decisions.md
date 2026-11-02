# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-11-02 · claude · First wiring made path_literal_audit src-backed; tests/architectural/test_gate_selection_authority.py::test_select_modules_full_mode_selects_all_registry_modules rejects it (every src-backed group is a module-registry row) and naming src/specify_cli/paths/** would have turned the FR-004 catch-all off for an unmapped directory. Switched to **/-spelled non-src globs (the mission_state precedent) and pinned the unmapped-keystone behaviour (C-005).
