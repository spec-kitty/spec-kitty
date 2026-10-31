# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-30 · maintainer-j · Post-tasks review (reviewer-renata profile): (1) e2e regression test must commit the seeded project state before running synthesize, so promote-modified charter.yaml shows as M rather than ?? and the cleanliness assertion is meaningful; (2) resynthesize prints no commit reminder at all today — writing the record there still leaves it uncommitted; out of scope for #6631, record in PR Deferred; (3) keep warnings byte-identical through the result-shape change.

2026-10-30 · maintainer-j · Single authority for the recipe path list: the write surface (reach_only append seam) reports written_paths, the reminder renders base list + seam report, nothing restated in between (NFR-003: no literal activation path in reminder construction). Record-only runs (activated key absent, C-001) report the record path; no-op appends report none; unreadable-record appends report none and only warn. Bonus: repaid ruff-format debt for tests/agent/cli/commands/test_charter_synthesize_cli.py (was on the formatter ratchet; entry removed from pyproject.toml, shrink-only ratchet test green).
