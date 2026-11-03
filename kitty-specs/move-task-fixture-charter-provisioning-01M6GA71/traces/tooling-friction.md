# Tracer: tooling-friction

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-11-03 · pi:python-pedro · tests/tasks is out_of_matrix in .github/ci-module-registry.yml, so no per-PR shard runs this module; the red-first evidence is a recorded local run. Also: issue #7073 and PR #7100 (still open) touch the same helper, so the hunks were kept textually disjoint.
