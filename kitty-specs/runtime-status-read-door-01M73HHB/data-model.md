# Data Model: Runtime status readers through the read door

## BoardStatus (value object, new)

One reduced reading of a Mission's status for one `next` decision or query. It is immutable and built once.

| Field | Meaning |
|---|---|
| `lanes` | work package id -> canonical lane (genesis kept, so callers can skip unseeded WPs) |
| `wp_states` | work package id -> reduced state (lane plus provenance, for dependency readiness) |
| `has_log` | whether the declared source holds a status log at all (replaces `has_event_log` / `CanonicalStatusNotFoundError` probes) |
| `weighted_percentage` | weighted progress to 1 dp, or none when it cannot be computed (logged, as today) |
| `source` | the door's declared source (`write_checkout`, `coord_worktree`, `coord_branch_ref`, `mission_branch_ref`, `consolidated_target`) |

**Invariants**
- Built only from a door surface (a single builder). The Path adapter builds a surface-equivalent reading for a directory, for the two outside callers and tests.
- Per-WP lanes and weighted progress equal today's path for path sources (parity, NFR-001).
- A corrupt log line raises at build time for lanes, as today. Only the weighted figure degrades.

## Coordination worktree state -> `next` behaviour

| State | Door source | Query / progress | Advancing board (non-owned) | Advancing board, `--auto-remediate` | Owned query | Owned dispatch |
|---|---|---|---|---|---|---|
| materialized | `coord_worktree` | real lanes | dispatch | dispatch (no-op) | real lanes | dispatch |
| empty | `coord_branch_ref` | real lanes (**#7507 fix**) | dispatch from real lanes (**fix**) | dispatch (no-op) | real lanes (**fix**) | refuse `OWNED_COORDINATION_WORKSPACE_UNAVAILABLE` |
| unmaterialized | `coord_branch_ref` | real lanes (**fix**) | block, today's text | materialize, one line, then dispatch (**new**) | real lanes (**fix**) | refuse `OWNED_COORDINATION_WORKSPACE_UNAVAILABLE` |
| deleted, not landed | raises `CoordinationBranchDeleted` | flatten guidance (unchanged) | flatten guidance | flatten guidance, nothing remediated | flatten guidance | flatten guidance |
| landed | `consolidated_target` | landed terminal (unchanged) | landed terminal | landed terminal | landed terminal | landed terminal |

The empty-worktree advancing case reads real lanes because the operator's block (DM-2) covers only the worktree that is not checked out. An empty worktree is checked out, and the door reads its committed branch.

## Placement seam handed to artifact presence

`gather_artifact_presence` and `guard_failure_artifact_paths` take the placement seam (or `None` for "use the supplied directory") instead of a status directory to reverse-map. The reported artifact paths stay the same for every existing fixture.
