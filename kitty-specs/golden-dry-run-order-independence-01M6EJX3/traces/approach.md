# Tracer: approach

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-11-02 · python-pedro · T001 red-first reproduction on main 9aed3a80: 'pytest tests/upgrade/test_upgrade_outcome_rendering.py -k golden_applied_dry_run -q' -> 1 failed, 48 deselected with '- Would repair 1 ...' vs '+ Would repair 125 ...'; whole-module run green. Confirms the golden's only environment input is the live supporting-repair preview count.
