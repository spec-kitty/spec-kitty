# Data Model: Gates that work in teammate clones and ephemeral reviewers

## Approval stamp (status event `policy_metadata`)

| Key | Type | When written | Meaning |
|-----|------|--------------|---------|
| `lane_head` | SHA (existing) | every lifecycle transition of a lane-mapped WP | local lane head at the transition |
| `lane_head_presync` | SHA (new, optional) | the same transition, only when the lane head sits on top of the review's own sync merge(s) | the lane tip before the review sync merged the coordination branch in |

Invariant: when `lane_head_presync` is present, it is a first-parent ancestor of `lane_head`, and every commit between them is a merge commit.

Effective stamp (consolidation): the newest recorded stamp the lane contains. That is `lane_head` when the lane reaches it, else `lane_head_presync` when the lane reaches that. When neither is reached, the refusal is `APPROVAL_STAMP_NOT_ON_LANE`, with detail `absent_from_clone` or `not_on_lane`.

## Review pre-sync record (local ref)

`refs/spec-kitty/review-presync/<lane-branch>` holds the lane tip before the last review sync merge. It is clone-local, never pushed, and overwritten by each sync that creates a merge.

## Work package kind normalisation (finalize-tasks)

| Input kind | Owned paths | Topology | Started? | Result |
|------------|-------------|----------|----------|--------|
| planning_artifact | all under `kitty-specs/` | any | any | unchanged (planning lane) |
| planning_artifact | none under `kitty-specs/`, at least one other | lane topology | no | `code_change` (own lane), notice |
| planning_artifact | mix of `kitty-specs/` and other | lane topology | no | `code_change`, then refused `INVALID_WP_OWNED_FILES_KITTY_SPECS` with split remedy |
| planning_artifact | any | single_branch | any | unchanged |
| any | any | any | yes | unchanged (frozen membership) |

The settlement size count uses the normalised kinds.

## Owning tracking ref

`owning_tracking_ref(repo, branch)` returns `refs/remotes/<owner>/<branch>`, where `<owner>` comes from `kernel.git.remote.resolve_remote`. It returns that ref only when it resolves to a commit locally. `None` otherwise.
