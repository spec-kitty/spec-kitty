# Tracer: approach

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-11-01 · python-pedro · Prototype of the read scanner over tests/architectural (374 files, import closure) finds 34 undeclared repo-root reads across 19 gates once code scope includes src/**, tests/architectural/** and the router's ci_config globs; only 2 are not real repository reads (synthetic .nonexistent-home probe, untracked .pytest_cache dir).
