# Tracer: tooling-friction

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-09-30 · claude-orchestrator · Seed: (a) mission create on the #5420-stacked branch resolved to coord topology. Its scaffold commit put status.events.jsonl on the target branch, and the specify decision events were appended to that target copy (the coord worktree had no mission dir). Handle at consolidate by resetting the target copy per the coord status-byteset gotcha. (b) The upstream remote here is named skupstream, not upstream, so the skill's 'git fetch upstream' failed.

2026-09-30 · claude-orchestrator · spec-commit given decisions/DM-*.md and decisions/index.json among its paths reported success but silently committed only the other files (commit 83fdc20); the decision artifacts had to be committed with plain git. Expected: commit them, or refuse and name the rejected paths.

2026-09-30 · claude-orchestrator · With agents.auto_commit=false in .kittify/config.yaml, the WP01 review verdict was written to the coord worktree but not committed, and the root checkout gained untracked review-cycle-1.md; the orchestrator must batch-commit lifecycle bytes on two branches after each transition. The CLI names this ('NOT committed (--no-auto-commit)') but the implement-review skill's happy path does not mention it.

2026-09-30 · claude-orchestrator · tests/docs/test_docs_index.py::test_render_index_is_byte_stable_across_hash_seeds shells out to 'uv run --no-sync'. It fails inside a lane worktree, which has no .venv of its own, but passes in the repository root checkout (1 passed). This is an environment artifact of lane worktrees, not a pre-existing failure, so no charter issue was filed. Classified by the orchestrator, 2026-09-30.

2026-09-30 · claude-orchestrator · (1) Consolidation stopped with TARGET_BRANCH_CONTENT_CONFLICT on status.events.jsonl, and the root cause was the CLI's own scaffold and accept commits. The CLI committed the coord-owned status bytes to the target branch; the operator did not stage them. The recorded merge-base remedy worked, but only after recomputing the merge-base, which had moved to 3a448321ea because the mission branch absorbs target commits. (2) 'consolidate --resume' did not honor the original run's '--keep-branch', so the lane branches were deleted. The tips were recovered from the printed SHAs and pinned under refs/keep/5426/*. Expected: resume replays the persisted cleanup decision.
