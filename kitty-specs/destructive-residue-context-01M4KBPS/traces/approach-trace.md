# Approach trace

- [2026-10-10][pre-spec] Three-lens research squad (researcher, architect, pattern scout) on the four consolidate data-loss bugs; converged on one root cause for #5965/#5966 and split #5967/#5968 off. Grounding squad of the mission skill satisfied by this squad (same day, same main SHA).
- [2026-10-10][post-spec] reviewer-renata: CHANGES REQUESTED, 9 findings, all accepted; the biggest one (refused teardown after landing) became an operator decision.
- [2026-10-10][plan] Brownfield find: `tests/architectural/test_destructive_op_routing.py` already exists with a 22-entry allowlist; plan widens and drains it rather than adding a second gate.
- [2026-10-10][WP01 review] LOW: move `_run_hard_killed` into tests/terminus/rollback_harness.py and reuse `rollback_harness.flat` instead of local `_flat` — fold during WP08 repro conversion.
- [2026-10-10][WP04 review] LOW: consolidation/workspace.py discard_scratch_tree deletes a .git file after a guard refusal without proving the gitlink dangles; check the gitdir is missing first — pre-PR fold candidate.
- [2026-10-10][WP06 review] LOW: template/manager.py copy_package_tree — add a docstring note that preserve_existing=False is only for tool-created trees (owned_root==target reduces the helper to the .git check) — pre-PR fold candidate.
- [2026-10-10][WP07 review] LOW: init.py resolver-scratch best_effort cleanup untested; init.py _discard_failed_project_scaffold lets ToolOwnedPathUnproven surface as a raw traceback in the failure path — render it — pre-PR fold candidates.
- [2026-10-10][WP03 review] MEDIUM: orchestrator_api/consolidation.py lane branch delete passes creation_base=None, so squash-landed lane branches are kept with a warning and accumulate; pass the snapshotted lane tip like consolidate does — pre-PR fold. Unverified (for pre-PR squad): entry preflight coord-as-MISSION is check-only; _unlanded_paths_outside_mission_dir false refusals; mid-abort refusal resumability.
- [2026-10-10][WP09 review] LOW: mission_type --discard drops coordination-kind history (review-cycle, traces, issue matrix) when nothing else is unique; make the discard confirmation/output say so — pre-PR fold candidate.
# Approach trace

- [2026-10-10][pre-spec] Three-lens research squad (researcher, architect, pattern scout) on the four consolidate data-loss bugs; converged on one root cause for #5965/#5966 and split #5967/#5968 off. Grounding squad of the mission skill satisfied by this squad (same day, same main SHA).
- [2026-10-10][post-spec] reviewer-renata: CHANGES REQUESTED, 9 findings, all accepted; the biggest one (refused teardown after landing) became an operator decision.
- [2026-10-10][plan] Brownfield find: `tests/architectural/test_destructive_op_routing.py` already exists with a 22-entry allowlist; plan widens and drains it rather than adding a second gate.

## WP09 (misc site routing)

- `GitVCS.remove_workspace` and `VcsProvider.remove_workspace` had zero production callers (codegraph + grep); deleted both, plus their two tests. The `tests/architectural/test_destructive_op_routing.py` allowlist entry for it is now stale (WP08 empties the allowlist).
- `mission_type` discard: lane branches are guarded against the Mission branch (or target) as creation base. The coordination/mission branch of a coordination Mission is status-only by design, and `--discard` is operator-confirmed abandonment, so `_bookkeeping_branch_base` lets it go only when every added/modified path beyond the target is a coordination-kind file (a deletion loses nothing). Any other commit leaves `target` as the base and the guard refuses.
- `mission_type` option-injection hardening (S6350) moved from a `--` separator to a leading-dash refusal in `_force_delete_branch_if_exists`; `guarded_branch_delete` runs `branch -D <name>` without a separator.
- `doctor_husks`: a husk belongs to no known Mission, so it uses a private classifier that disposes of nothing. **Finding for WP02/WP08**: `guarded_tree_delete` relies on `git status --ignored`, where ignored entries are obstruction-gated and never count as dirty. A husk under an ignored `.worktrees/` therefore holds its files invisibly and is deleted (reproduced: ignored `.worktrees/h/work.py` is removed). The guard should treat any file under `path` as local state when `path` is not itself a checkout root. Husks are only protected today when `.worktrees/` is not ignored.
- `git_source`: the pack cache is a `TOOL_OWNED` context. Clones carry `.git`, which `remove_tool_owned_tree` refuses by design, so scratch clones go through `guarded_tree_delete(TOOL_OWNED)` and `.git`-less scratch through `remove_tool_owned_tree`.
