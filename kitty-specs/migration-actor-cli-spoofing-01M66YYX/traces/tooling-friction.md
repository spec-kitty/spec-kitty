# Tracer: tooling-friction

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-30 · python-pedro · The pre-review gate's 300s review.test_timeout_seconds budget was exceeded on the first WP01 move-task (it also builds a fresh lane venv). Retry passed; the budget was NOT raised, because raising a timeout to pass a gate is gate weakening.

2026-10-30 · python-pedro · spec-kitty consolidate --strategy rebase is incompatible with the approved-commit reconciliation gate: rebasing rewrites the approved WP commit SHAs, so the gate refuses and rolls back. --strategy merge keeps them reachable; that is the only strategy that satisfies both.

2026-10-30 · python-pedro · Coord branch teardown refused because kitty-ops/lifecycle.jsonl differed between the coordination branch and the target, which is shared append-only bookkeeping that diverges by branch. Landing the union on both branches (coord commit + target already equal) cleared it; --resume then finished.
