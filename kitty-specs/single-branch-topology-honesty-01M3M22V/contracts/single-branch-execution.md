# Contract: single_branch execution

Owner: the lane manifest (`lanes.json`), read through `is_repo_root_lane`, and the workspace resolver.

## Finalize

`compute_lanes(..., topology=single_branch)` returns a manifest that holds exactly one lane:

- `lane_id`: `lane-planning`
- `wp_ids`: every work package in the mission

The manifest carries the target branch as `target_branch`. It also carries `mission_branch`, but only when `meta.json` records one.

If `assert_topology_matches_manifest(topology, manifest)` fails, the manifest write raises `SINGLE_BRANCH_CODE_LANES_UNMIGRATED`.

## Resolve

For any work package in a `single_branch` mission, `resolve_workspace_for_wp` returns:

| Field | Value |
|---|---|
| `resolution_kind` | `repo_root` |
| `worktree_path` | `effective_root` if set, otherwise the repository root checkout |
| `branch_name` | `meta.mission_branch` if set, otherwise `target_branch` |
| `lane_id` | `lane-planning` |
| `status_execution_mode` | `direct_repo` |

## Implement: refusals

Refusals are checked in this order. Each names the blocking object and a remedy (NFR-004).

1. **Unmigrated mission.** Code lanes are present, so the command raises `SINGLE_BRANCH_CODE_LANES_UNMIGRATED`.
2. **Wrong branch.** The write checkout's HEAD is not the expected write branch. The error names both branches. The command never switches branches itself.
3. **Another WP in progress.** Another work package, from any `single_branch` mission, is `in_progress` in the same write checkout. The error names that mission and WP.
   - Exception: resuming the WP that is already `in_progress` is a no-op.
4. **Dirty checkout.** The write checkout has tracked changes, or untracked files outside spec-kitty-owned paths. The error lists the paths.
   - Exception: resume.

## Claim base and for_review (post-plan fold B2)

A work package in a repo-root lane has no lane branch, so the for_review gate needs another starting point. This covers every repo-root lane WP, planning_artifact WPs included.

- **Claim**: `implement` records `refs/spec-kitty/wp-base/<mission_slug>/<WP>` as the write checkout's current HEAD. On resume, it records the ref only if it is missing.
- **for_review**: the gate requires at least one commit in `wp-base..HEAD` in the write checkout. If there are none, it refuses the move, as it does today.
- **Cleanup**: the ref is deleted when the WP reaches a terminal state.

The manifest's `mission_branch` for a single_branch mission is `meta.mission_branch` when set, otherwise `target_branch`.

## Implement: no dependency merge

Implement skips `_merge_dependency_lane_tips` for the repo-root lane. Dependency readiness (`approved` / `done`) is still enforced.

## Consolidate

| Case | Behaviour |
|---|---|
| Unprotected target, or `commit_to_target` | Bookkeeping only. No git landing and no branch deletion. |
| Protected target | Lands `mission_branch` onto `target_branch` through the mission→target phase. Authored blobs come from first-parent `base..mission_branch`. Checks out `target_branch` in the write checkout, then deletes `mission_branch`. Never removes the repository root checkout or `target_branch`. |
