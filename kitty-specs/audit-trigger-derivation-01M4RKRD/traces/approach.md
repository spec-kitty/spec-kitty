# Tracer: approach

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-12 · stijn-dejongh · Add a non-vacuous derived test in tests/ci/test_mission_state_audit_routing.py that drives doctor mission-state --audit in-process (run_audit) on a small committed git fixture, warm-captures executed src/ modules, and asserts each matches the mission_state group via gate_selection.load_router/select_gates. Remove the hand-copied AUDIT_INPUT_PATHS; re-point consumers onto the derived set + a small explicit non-executed-input list (manifests/workflow/renderer). ATDD: commit the test failing-first.

2026-10-12 · stijn-dejongh · Self-mutation witnessed RED both directions (NOT committed): (A) dropped the '**/specify_cli/status/**' glob from ci-router.yml -> test RED naming src/specify_cli/status/{reducer,store,models,identity_audit,lane_reader,lifecycle_events}.py (the #6058 drift it must catch); (B) injected a call to a planted out-of-glob module src/specify_cli/_witness_tmp.py into run_audit -> test RED naming _witness_tmp.py. Both restored. Command: .venv/bin/python -m pytest tests/ci/test_mission_state_audit_routing.py -k test_every_executed_audit_module_matches_the_group -p no:randomly. Clean run: 1 passed, setup 1.09s, total 1.60s (NFR-001 <2s holds; earlier 28s was concurrent-run machine load).
