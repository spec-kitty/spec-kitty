---
affected_files: []
cycle_number: 2
mission_slug: owned-checkout-lifecycle-authority-01M3M2ZB
reproduction_command:
reviewed_at: '2026-09-29T00:55:54Z'
reviewer_agent: claude
wp_id: WP05
---

# WP05 review feedback, cycle 2: changes requested (narrow)

Reviewer: reviewer-renata. Head reviewed: 6e1ea1c8c, plus merge a24057129 (no src/tests delta).

## Cycle-1 findings: verified

| Finding | Status | Verification |
|---|---|---|
| HIGH-1: coordination anchor | Fixed for the lane arm, the context join and planning_artifact | The red commit 9689e8e97 is red for the right reason in a detached scratch worktree: 3 failed (`[p]` lane → P/.worktrees; `[r]` planning_artifact → R; `[p]` context join → P/.worktrees) and 3 passed. |
| HIGH-2: FR-019 tests | Fixed | Cache-key mutant (`tasks_dir` → `repo_root`) turns 3 tests red: `test_editing_p_does_not_invalidate_r_cache_entry` plus both identical-snapshot collision tests. |
| MEDIUM-3: baseline-wiring fakes | Fixed | `test_status_baseline_wiring.py` is green. |
| MEDIUM-4: identity-gate pin | Fixed | Mutant that forces `get_main_repo_root` onto the owned gate turns `test_owned_identity_gate_never_calls_get_main_repo_root_or_subprocess` red. |
| LOWs | Fixed | `match="not both"`, the repo_root-exempt test, the deleted comment, and the worktree_topology inventory are all in place. |

Parallel-composer check: passes. `_lane_worktree_anchor` / `_planning_surface_root` only select the anchor. Path composition still goes through the canonical `lanes.branch_naming.worktree_path` / `worktree_dir_name`. This is the same pattern WP04 uses (`coord_feature_dir(owned.repository_root, …)`), so there is no second composer.

## BLOCKING

### [MEDIUM] 1. `src/specify_cli/workspace/context.py`: two of the four HIGH-1 anchor changes have no test

Each mutant below leaves 53/53 tests green (`test_owned_workspace_resolution.py` + `test_workspace_context_unit.py`):

- **(a) `_lanes_manifest_workspace` planning-lane sub-arm.**
  - The mutant reverts `worktree_path=_planning_surface_root(repo_root, owned)` to `worktree_path=repo_root`.
  - Nothing covers a `code_change` WP assigned to `lane-planning` in an owned coordination mission. The planning_artifact test takes the other function.
  - **Fix:** add a test parametrised over caller `repo_root` ∈ {R, P}. It builds a `lanes_with_coord` mission whose lanes.json puts a code_change WP in `lane-planning`. Assert `resolution_kind == "repo_root"` and `worktree_path == P`.
- **(b) the dispatcher's `find_context_for_wp(_lane_worktree_anchor(...))` lookup.**
  - The mutant reverts it to `find_context_for_wp(repo_root, ...)`.
  - `test_owned_coordination_topology_context_anchors_on_repository_root[p]` still passes. The lookup at P misses and falls through to the lanes.json arm, which composes the same `R/.worktrees/<slug>-lane-a`.
  - **Fix:** make the test prove the context arm was taken, for example by asserting `resolved.context is not None` and `resolved.branch_name == <the context's branch_name>`. Choose a context `branch_name` that differs from `lane_branch_name(slug, "lane-a")`.

Show both mutants go red, and record this in the Activity Log.

## NON-BLOCKING (fix in the same cycle)

- **[LOW]** `test_owned_workspace_resolution.py`, marker hygiene:
  - `test_owned_coordination_topology_anchors_lanes_on_repository_root` builds real git repos but lost its `@pytest.mark.git_repo`.
  - `test_enforce_checkout_identity_exempts_repo_root_kind_directly` and `test_owned_identity_gate_never_calls_get_main_repo_root_or_subprocess` carry no markers; they need `unit` + `fast`.
  - The WP asks for per-test markers.
- **[LOW]** The T024 section comment says reverting the key "turns every T024 test below red". Only 3 turn red, as your own Activity Log says. Correct the comment.

## Pre-existing / not yours

- `tests/specify_cli/test_meta_read_permission_denied_regression.py`: 5 failed on base 4f4e0aa18 too. The sandbox runs as uid 0, which bypasses chmod.
- `tests/specify_cli/cli/commands/agent/test_status_baseline_wiring.py` still needs reformatting, but it already did at 19e37621d. This is pre-existing format debt, not introduced here.
