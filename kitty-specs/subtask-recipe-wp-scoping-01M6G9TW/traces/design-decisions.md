# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-11-03 · python-pedro · The byte-frozen agent tasks --help fixtures stay untouched: mark-status already documents --wp, so documenting the flag was never the gap. Fix the emitters instead of the docs. Subtask-id namespacing (WP02.T001) is explicitly out of scope (C-001): ids stay mission-scoped T###, no frontmatter migration, no event-schema change. The renderer lives in specify_cli.core rather than specify_cli.cli because the runtime layer may not import the CLI; it is pure text so the I/O-free move-task decision core can use it.

2026-11-03 · python-pedro · Wrap-up: development-assist test verdicts, both KEEP. tests/specify_cli/core/test_subtask_recipe.py is named after the renderer contract it pins (option order, keyword-only wp_id, purity) and carries no WP##/NFR labels. tests/specify_cli/cli/commands/agent/test_move_task_unchecked_recipe_scoped.py is named after the refusal/emitter contract, its behavioural test drives the real mark-status entry point rather than a stubbed or characterization oracle, and its AST census is the standing guard that stops a future emitter from hand-formatting the recipe. The two pin updates landed inside the suites that already own those assertions, so no fold was owed and no new mission-only file is left behind.
