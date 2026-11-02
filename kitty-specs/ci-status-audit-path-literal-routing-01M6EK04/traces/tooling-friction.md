# Tracer: tooling-friction

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-11-02 · claude · tests/architectural/test_same_tier_uniqueness.py and test_gate_selection_authority.py collect the whole tree; in a fresh lane worktree their module-scoped universe fixture died at pytest-timeout (240 s) and then on missing pack assets / pytest-benchmark. Fixes: uv sync --frozen --all-extras, make sync-packs, and --timeout=1800 for the local run; it is 21 passed in 132 s afterwards, so this is local-environment cost, not a diff problem.
