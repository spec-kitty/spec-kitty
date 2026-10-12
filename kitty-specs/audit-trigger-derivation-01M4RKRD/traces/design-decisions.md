# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-12 · stijn-dejongh · Capture mechanism = warm, function-call-scoped sys.setprofile (co_name != '<module>') after a warm-up run. Rationale: a cold interpreter over-captures ~360 modules (whole package-init tree = the rejected whole-subpackage alternative); body-only capture is order-sensitive. Warm function-call capture is deterministic and reproduces the real 604-mission corpus footprint (33 modules) from a ~0.01s fixture. No ci-router.yml edit: all 33 executed modules already matched by existing globs.

2026-10-12 · stijn-dejongh · Post-tasks adversarial pass (capture point): profiling the FIRST run_audit is WRONG — it captures 45 modules (12 import-time-only function calls from migration/* eager __init__, core/vcs/*, git_preflight) and is non-deterministic (45 vs 33 on repeat). The warm-up run + profiled SECOND run captures 33 deterministically and equals the real 604-mission corpus footprint exactly. Conclusion: the warm-up run is load-bearing (not optional); capture only function-call frames of the second run. No audit-logic first-call-only path is missed (the 12 extras are pure import machinery).

2026-10-12 · stijn-dejongh · Faithful entry point = the CLI dispatch run_mission_state(repo_root=fixture), not raw run_audit: it captures the CLI cluster (_mission_state_doctor.py) and audit/serializer.py that the real 'doctor mission-state --audit' executes (35 deterministic modules, all covered). Three old AUDIT_INPUT_PATHS src entries an in-process function-call trace cannot observe — the typer shell doctor.py + _doctor_shared.py (above the run_mission_state entry) and core/constants.py (module-level only) — go in a small explicit NON_DERIVABLE_TRIGGER_INPUTS list with the manifests/workflow/renderer. Derived(35) ∪ explicit(8) covers all 26 old entries; the drift-prone module surface is now mechanical.
