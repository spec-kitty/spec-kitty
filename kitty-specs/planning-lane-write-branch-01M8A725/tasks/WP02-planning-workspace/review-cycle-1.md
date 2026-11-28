---
affected_files: []
cycle_number: 1
mission_slug: planning-lane-write-branch-01M8A725
reproduction_command:
reviewed_at: '2026-11-26T00:03:52Z'
reviewer_agent: claude::reviewer-renata
wp_id: WP02
---

# WP02 review feedback, cycle 1 (claude::reviewer-renata)

Reviewed commit 3bd8cddd (range 646386c6..3bd8cddd). Verdict: changes requested.

What holds: the three planning arms go through the one `_planning_workspace` helper. Explicit, landed, single_branch and owned shapes keep their pre-change values (cases 2, 3, 4 and 6 pin them field for field). C-003 holds: the only workflow.py hunk is the ancestry message near line 2036. The messages name "the Mission branch <b> (the coordination branch)" and print `cd <coordination worktree>`. All seven test cases are present, and case 5 removes the worktree with `git worktree remove`. The new file passes 22/22. ruff, `ruff format --check --force-exclude` and C901 are clean.

## Findings

1. [MEDIUM] src/specify_cli/workspace/context.py:1330 (`_refuse_if_planning_checkout_missing`). The "WP not found" probe can replace the caller's original `ValueError` with a different error, although its docstring says "Any other shape ... returns so the caller's original error stands". `_recorded_target_branch(...)` (`get_feature_target_branch`) runs inside the `try`, but only `PlanningCheckoutMissing` and `PlanningWriteRefUnavailable` are caught. Its `MissionMetaReadError`, and any other error `planning_lane_target` raises (git or topology), therefore escape.
   Evidence: a repository whose `meta.json` is corrupt, calling `resolve_workspace_for_wp(repo, slug, "WP99")`:
   - at 3bd8cddd^ it raises `ValueError: Work package WP99 was not found ...`;
   - at 3bd8cddd it raises `MissionMetaReadError` (a `RuntimeError`).

   Callers that degrade on `ValueError` now crash instead. These are tasks_move_task_gates.py:314, tasks_move_task_executor.py:230, tasks_move_task.py:1511 and :1790, tasks_parsing_validation.py:945, and orchestrator_api/wp_lifecycle.py:293.
   Recommendation: make the probe re-raise the original `ValueError` for every outcome except `PlanningCheckoutMissing`. Resolve the target branch inside the guarded block and catch `MissionMetaReadError`/`GuardedReadError` (or the probe's errors broadly). Add a test: corrupt `meta.json` plus an unknown WP id still raises the original `ValueError`.

2. [MEDIUM] T007 audit gap. `PlanningWorkspaceMissing` is a `StructuredError` (a `RuntimeError`, not a `ValueError`). The tolerant callers listed in finding 1 catch `(ValueError, FileNotFoundError, MissingLanesError, CorruptLanesError)` to degrade (for example, the emit stamp falls back to "worktree", or the pre-review path returns None). They now receive a new uncaught exception type in exactly the case where the coordination worktree is gone and the WP index is unreadable. These callers are not in the audit table.
   Recommendation: classify each one as either "fail closed with PLANNING_CHECKOUT_MISSING" (NFR-002) or "degrade", and record the result in add-history. Where degrading is correct, catch the new type. Add at least one test of a move-task path with the coordination worktree removed.

3. [LOW] src/specify_cli/cli/commands/agent/workflow_executor.py:2253. mypy reports `no-any-return` in a file this commit changes. The standing rule is zero mypy findings on changed files, and charter Standing Order 2 calls for campsite cleaning. Fix it with a typed local or a cast-free annotation, not a suppression.

4. [LOW] src/specify_cli/cli/commands/agent/tasks_dependency_graph.py:183-184. The new helper `_dependent_rebase_line` still prints "planning-lane workspace (main repo checkout) — no rebase needed; ensure main is up to date", and its comment says "up-to-date with main". The diff moved these lines, so they are its own. They break the Branch-Intent Terminology rule (never "main repository"; do not use bare "main" for the target).
   Recommendation: "planning-lane workspace (repository root checkout) — no rebase needed; ensure the target branch is up to date", and fix the comment to match.

5. [NIT] src/specify_cli/workspace/context.py:106 and :979.
   - `PlanningWorkspaceMissing.__init__(self, source: Any)` reads attributes off an untyped `Any`. Type it as `mission_runtime.PlanningCheckoutMissing`, using a TYPE_CHECKING import if layering requires it.
   - `_translate_checkout_missing(exc: Exception)` only aliases the constructor. Inline it, or type its parameter the same way.

6. [NIT] src/specify_cli/core/worktree_topology.py:341 (`_topology_note`, new code). This commit adds `REPO_ROOT_KIND`, but this line still compares against the `"repo_root"` literal. Use the constant in the code this commit adds; implement.py:364 can follow if it is touched.

## Lens limits
- The claim base and the for_review gate (WP03) and the move-task auto-commit guard (WP04) were not reviewed. The implementer's hand-off note for WP04 (`is_shared_checkout`) is correct.
- The blast-radius red `test_reassess_under_lock::test_live_upgrade_dry_run_preview_is_deterministic_across_repeats` was not re-run. Its attribution to a stale editable install is plausible: the shared .venv's editable .pth points at /home/user/spec-kitty/src, not at the lane.
