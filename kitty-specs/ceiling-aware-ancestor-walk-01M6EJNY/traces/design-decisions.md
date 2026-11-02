# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-11-02 · claude · Item 2 of #7056 kept the shipped ceiling reading (a ceiling directory is examined, the walk stops after it) instead of git-exact semantics, which would change resolve_canonical_root for every consumer; pinned by tests.
