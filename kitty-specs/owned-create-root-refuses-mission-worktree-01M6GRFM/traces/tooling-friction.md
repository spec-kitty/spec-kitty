# Tracer: tooling-friction

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-11-03 · t3-code/claude · None yet: the shared minter, the leaf predicates and the registry classifier are already in place, so no new surface was needed for this fix.

2026-11-03 · t3-code/claude · Moving a WP to in_progress with 'agent tasks move-task --to in_progress' does not record the claim base, so the later for_review gate refuses with 'no implementation commit since claim' even after the implementation is committed. The claim base is only recorded by 'agent action implement WP<n> --agent <name>' (refs/spec-kitty/wp-base/<mission>/<WP>). Recovered by resetting to the pre-implementation head, claiming through 'agent action implement', then cherry-picking the implementation commit.

2026-11-03 · t3-code/claude · check_docs_freshness --ci reports 8 warnings (docs index drift, ci-performance.md inventory, a 403 link) on pristine origin/main in a clean worktree, so this mission records them as pre-existing rather than fixing them here; errors=0.
