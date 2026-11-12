# Tracer: tooling-friction

Mission: next-lifecycle-integrity-01M77BWP. Append dated entries during implementation; assess at close.

- 2026-11-12: `agent decision open` needs `--slot-key` or `--step-id` (error DECISION_MISSING_STEP_OR_SLOT); `spec-commit` refuses directories and the decisions `index.json.lock` — pass files explicitly.
- 2026-11-12: I resolved a decision with a placeholder answer ("pending research squad") because the CLI has defer but I reached for resolve; superseded by `specify.next.query_question_final`.
- 2026-11-12: Lane worktrees have no built-in pack tree; every test fails at collection with `BuiltInPackMissing` until `make sync-packs` runs in the lane, which also creates a lane-local `.venv` without `pytest_benchmark` (stale-venv category). Run from the lane before that, the root `.venv` imports the ROOT checkout's `src`, not the lane's.
- 2026-11-12: `move-task --to for_review` runs the fast tier inside the lane; it took more than 5 minutes (it overran an agent's 300s tool timeout).
- 2026-11-12: The `move-task --to approved` gate requires a verdict on EVERY issue-matrix row, including context-only citations (20, then 22 rows after prompt edits added #3407 and #7310). A reviewer cannot finish its own WP's approval; the orchestrator has to fill rows it does not own. The help text lives at `spec-kitty agent issue-verdict`, not `agent tasks issue-verdict`.
- 2026-11-12: Committing a regenerated golden help fixture (`move-task.help`) for a new flag trips the ACTIVE_WP_SCOPE_VIOLATION warning, although every new CLI option changes it.
- 2026-11-12: Dogfood observation: the WP01 rejection reset all 5 subtasks (T001-T004, T020) with no reason in the status event. That is #7582 itself, before WP04 lands.
