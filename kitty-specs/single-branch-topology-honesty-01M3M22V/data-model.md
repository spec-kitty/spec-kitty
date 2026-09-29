# Data Model: Single-branch topology honesty and destroyed-lane tip guard

## `meta.json` (mission metadata)

This mission adds or changes the following fields.

| Field | Type | Presence | Written by | Rule |
|---|---|---|---|---|
| `topology` | enum `single_branch \| lanes \| coord \| lanes_with_coord` | always (new missions) | mission create; the re-stamp migration | Single authority for the execution surface. The re-stamp migration changes `single_branch` → `lanes` only when `lanes.json` has code lanes. |
| `commit_to_target` | `bool` | absent by default; written only as `true` | mission create (`--commit-to-target`) | A non-boolean value fails closed and is never truthiness-coerced. It mirrors the pattern in `read_retention_from_meta`. |
| `mission_branch` | `str` | only for a protected-target `single_branch` mission without `commit_to_target` | mission create | Set to `kitty/mission-<slug>-<mid8>`. Create refuses if the branch already exists. Readers key on `topology` and this field, never on ref shape. |

**Invariant T-1:** `topology == single_branch` implies `lanes.json` has no code lane. A violation fails closed at the writers with `SINGLE_BRANCH_CODE_LANES_UNMIGRATED`.

## `lanes.json` (lane manifest)

- **`single_branch`:**
  - `lanes` holds exactly one lane, `lane_id = "lane-planning"`, and its `wp_ids` is every work package in the mission.
  - `is_repo_root_lane(lane)` is true for it.
  - `is_planning_artifact_only(manifest)` is true only when every work package is a `planning_artifact`.
- **`lanes` / flat:** unchanged.
- **`has_code_lanes(manifest)`:** true when any lane is not the repo-root lane. The topology derivation reads only this.

## Lane work-tip record

- **Name:** `refs/spec-kitty/lane-tip/<lane-branch>`, where `<lane-branch>` is the full branch name, for example `kitty/mission-foo-01ABCDEF-lane-a`.
- **Value:** the SHA of the last observed commit on that lane branch.
- **Writers:**
  - the post-commit recorder, for any commit whose HEAD is a `kitty/mission-*-lane-*` branch;
  - spec-kitty lane advances: allocation, reuse, dependency merge, auto-rebase, for_review, and `safe_commit`;
  - backfill on touch.
- **Deleters:** a work package reaching a terminal state (`done`, `canceled`) with no other non-terminal work package in the lane; consolidation teardown of the lane.
- **Local only:** the ref is never pushed.

### Guard decision table

The guard runs at `implement` when neither the lane branch nor its worktree exists.

| WP state | Tip ref | Absorbed? | Result |
|---|---|---|---|
| any other state | any | — | proceed (FRESH) |
| trigger state† | absent, no context | — | proceed (a genuinely fresh lane) |
| trigger state† | absent, context present | — | refuse `LANE_WORK_TIP_UNKNOWN` |
| trigger state† | present | yes (ancestor, equals base, or merge-tree no-op) | proceed |
| trigger state† | present | no | refuse `DESTROYED_LANE`, naming the SHA and `git branch <b> refs/spec-kitty/lane-tip/<b>` |
| trigger state† | present | cannot evaluate (git < 2.38) | refuse (fail closed) |

† **Trigger state** means `{in_progress, blocked, for_review, in_review}` (plan fold M7; analysis finding T1). Every other state proceeds (FRESH).

Coord topology keeps its existing #4889 behaviour: its check on the unreachable base still fires first.

## `ResolvedWorkspace`

- New property `status_execution_mode`: `"direct_repo"` when `resolution_kind == "repo_root"`, else `"worktree"`.
- New input `effective_root: Path | None`, taken from PR #5009. For `single_branch`, `worktree_path` is `effective_root` or, when that is absent, the repository root.

## `WorkspaceContext` (`.kittify/workspaces/*.json`)

- The schema is unchanged.
- Writes are centralised in `allocate_lane_worktree` (FR-022).

## Status event

- `execution_mode` is taken from `ResolvedWorkspace.status_execution_mode` on every transition path.

## Doctor findings (topology audit)

| Code | When | Remedy |
|---|---|---|
| `SINGLE_BRANCH_CODE_LANES_UNMIGRATED` | `topology == single_branch` and `has_code_lanes(lanes.json)` | `spec-kitty upgrade` (runs the re-stamp) or `spec-kitty migrate backfill-topology --restamp-single-branch` |
