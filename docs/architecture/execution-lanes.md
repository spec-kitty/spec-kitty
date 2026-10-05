---
title: Execution Lanes
description: "Spec Kitty's lane-based execution model: finalize-tasks computes lanes.json from dependencies and file ownership, giving each lane one worktree and branch to preserve parallelism."
doc_status: active
updated: '2026-10-04'
audience: docs/context/audience/internal/lead-developer.md
related:
- docs/architecture/branch-target-routing.md
- docs/migrations/mission-id-canonical-identity.md
---
# Execution Lanes

Spec Kitty uses a lane-based execution model.

- For `lanes` and `lanes_with_coord` missions, `finalize_tasks` computes `lanes.json` from dependencies, ownership, and predicted surfaces. A `single_branch` mission gets a one-lane repo-root manifest instead.
- Each code lane gets exactly one git worktree and one lane branch.
- Sequential work packages in the same lane reuse that same worktree.
- Independent lanes can run in parallel in separate worktrees.

## Core Rules

1. Planning happens in the primary repository checkout.
2. `spec-kitty agent action implement WP## --agent <name>` requires a valid `lanes.json`.
3. The runtime chooses the lane worktree. Agents do not pick a base branch manually.
4. If a `lanes` mission computes one lane, the mission uses one worktree. A `single_branch` mission uses no lane worktree at all.
5. Merge always follows `lane branches -> mission branch -> target branch`.

## Workspace Resolution Contract

`spec-kitty implement WP##` creates/reuses the execution workspace through
`resolve_workspace_for_wp` (`src/specify_cli/workspace/context.py`). For a
`code_change` WP, resolution ends at one of two places:

1. An **existing** lane workspace context (`find_context_for_wp`) — the lane
   this WP's mission already allocated a worktree for.
2. Otherwise, the mapping in `lanes.json`, read through
   `require_lanes_json` (`src/specify_cli/lanes/persistence.py`).

`require_lanes_json` is fail-closed: when `lanes.json` is absent it raises
`MissingLanesError` rather than degrading to a name-guessed path. **There is
no `-WP##` legacy worktree fallback** — `LANES` and `LANES_WITH_COORD`
missions require a computed `lanes.json`; a mission that hasn't run
`finalize-tasks` cannot resolve a workspace at all. A `SINGLE_BRANCH` mission
also needs its `lanes.json`, but that manifest is not computed from
dependencies: it is a one-lane repo-root manifest (`lane-planning`) whose WPs all
resolve to the write checkout (the repository root checkout, or a validated owned
checkout) with `execution_mode: direct_repo`. It has no lane worktree, no lane
branch and no dependency merge. See the
[topology glossary](../context/topology.md). (An earlier revision of
this repo's `AGENTS.md` claimed such a fallback existed; that claim was
false and has been corrected — see the `MissingLanesError` contract above
for the real behavior.)

## Naming

Mission and lane naming are two separate decisions, and only the Mission
decision takes the Mission identity.

**Mission branch** — unchanged. As of mission
`083-mission-id-canonical-identity-migration`, every mission carries a ULID
identity (`mission_id`), and the Mission branch embeds the first 8 characters
of that ULID (`mid8`) to guarantee collision-free naming even when two
missions share the same human slug: `kitty/mission-<human-slug>-<mid8>`.

**Lane branch and lane worktree** — keyed on the recorded Mission slug and the
lane id only. The Mission identity is never an input to lane naming (see ADR
[`2026-09-26-2`](../adr/3.x/2026-09-26-2-lane-naming-keyed-on-creation-input.md)):

- Lane branch: `kitty/mission-<slug-body>-<lane-id>`, where `<slug-body>` is
  the recorded Mission slug with a stale `NNN-` numeric prefix dropped only
  when the slug itself embeds a mid8.
- Lane worktree: `.worktrees/<slug>-<lane-id>/`, verbatim — the recorded slug,
  not recomposed.

`mid8` therefore appears in a lane name only when the Mission slug happens to
embed it — never because lane naming looked up the identity.

**Example — a modern mission** (slug embeds the mid8, so lane names look the
same as before this ADR): `mission_slug=my-feature-01J6XW9K`,
`mission_id=01J6XW9KQT7M0YB3N4R5CQZ2EX`:

- Mission branch: `kitty/mission-my-feature-01J6XW9K`
- Lane branch: `kitty/mission-my-feature-01J6XW9K-lane-a`
- Lane worktree: `.worktrees/my-feature-01J6XW9K-lane-a/`

**Example — a legacy mission** whose recorded slug is `057-foo` and whose
identity was later backfilled to a *different* mid8 (`01KV6510`): lane naming
never sees the identity, so lane names are unaffected by the backfill:

- Mission branch (recomposed only on first finalize; preserved after):
  `kitty/mission-057-foo` (pre-backfill) — see the
  [mission identity migration runbook](../migrations/mission-id-canonical-identity.md)
  for what backfill does and does not change.
- Lane branch: `kitty/mission-057-foo-lane-a`
- Lane worktree: `.worktrees/057-foo-lane-a/`

Legacy (pre-083) lane forms such as `kitty/mission-001-my-feature-lane-a` and
`.worktrees/001-my-feature-lane-a/` remain readable by current tooling.

## Why This Replaced Per-WP Worktrees

Per-work-package worktrees allowed overlapping work packages to run in parallel and collide at merge time. Execution lanes eliminate that by forcing dependent or overlapping work packages into the same lane, branch, and worktree.

## Parallelism Preservation

`finalize-tasks` groups WPs into lanes with a union-find over three rules
(`compute_lanes`, `src/specify_cli/lanes/compute.py`):

1. **File ownership overlap** (`write_scope_overlap`) — WPs whose `owned_files` overlap share a lane.
2. **Shared surface** (`surface_heuristic`) — WPs that share a predicted surface keyword share a lane unless their ownership is provably disjoint (see below).
3. **Frozen lane membership** (`frozen_lane_membership`) — on a re-finalize, started WPs that were recorded in the same lane stay together (see [Re-finalizing an active Mission](#re-finalizing-an-active-mission)).

Dependency edges do not merge lanes by themselves. They become lane-level dependencies, so disjoint upstream lanes run in parallel and the WP that depends on them is the synchronization point. Inside one lane, WPs run in dependency order.

When no rule forces a merge, WPs stay in separate lanes to maximise parallelism. Every merge is recorded in `lanes.json` under `collapse_report`:

```json
{
  "collapse_report": {
    "events": [
      {
        "wp_a": "WP02",
        "wp_b": "WP03",
        "rule": "write_scope_overlap",
        "evidence": "overlapping globs: 'src/foo.py' vs 'src/foo.py'"
      }
    ],
    "total_merges": 1,
    "independent_wps_collapsed": 1,
    "by_rule": {"write_scope_overlap": 1}
  }
}
```

Each event names the two WPs merged, the rule and its evidence. `independent_wps_collapsed` counts merges of WPs with no direct or transitive dependency between them; `frozen_lane_membership` merges are never counted there, because those WPs already shared a lane. Inspect this field after `finalize-tasks` to understand why two WPs share a lane.

### Disjoint Ownership vs. the Surface Heuristic (bulk-edit missions)

`compute_lanes` (`src/specify_cli/lanes/compute.py`) has a second collapse
rule beyond file-overlap: two WPs that share an inferred *surface* keyword
(e.g. both bodies mention "legacy" or "cleanup", matching the
`legacy-cleanup` tag in `_SURFACE_KEYWORDS`) are also candidates for merging
into one lane — **unless their `owned_files` are provably disjoint**
(`_are_disjoint`), in which case the merge is skipped.

This matters most for bulk-edit missions (see the [bulk-edit occurrence
classification guardrail
ADR](../adr/3.x/2026-04-14-1-bulk-edit-occurrence-classification-guardrail.md)):
a rename/replace mission routinely produces many WPs whose bodies all
describe the *same* edit applied to *different* files, so they trip the
same surface keyword nearly every time. Without the disjoint-ownership
check, the surface heuristic alone would collapse every one of those WPs
into a single giant lane, discarding the parallel partition the
occurrence-map classification was built to produce. The disjoint check is
what lets bulk-edit WPs with non-overlapping file scopes stay in separate
lanes and run in parallel.

It also keeps the lane dependency graph (`lane_deps`) well-formed. Lane
depth is computed by `_compute_lane_depths`, which treats a self-loop or
cycle as a best-effort depth-0 anchor rather than crashing — see
[`finalize-tasks internals`](../api/finalize-tasks-internals.md#2-lane-depth-cycle-safety)
for why that fallback exists and why it is *not* a substitute for a clean
input graph. An over-aggressive surface-only merge across many
similarly-worded bulk-edit WPs is exactly the kind of input that could
otherwise produce a lane graph the depth function has to paper over instead
of compute correctly; skipping the merge when ownership is disjoint avoids
manufacturing that situation in the first place.

## Re-finalizing an active Mission

Re-running `spec-kitty agent mission finalize-tasks --mission <handle>` on a Mission that already has a `lanes.json` is supported: you can amend work packages mid-execution and re-finalize. Lanes are recomputed, but **a started work package keeps its recorded lane** (ADR [4.x `2026-10-04-2`](../adr/4.x/2026-10-04-2-started-work-package-lane-membership-is-frozen.md), #5573).

**Why.** A started work package has commits on its lane branch and a [lane work tip](../context/topology.md#lane-work-tip). Moving it to another lane would strand that work: the next `implement` on it fails with `LANE_WORK_TIP_UNKNOWN`, and a lane-mate could be bound to a branch that carries foreign commits.

**What counts as started.** A [started work package](../context/topology.md#started-work-package) is one whose status history has ever recorded a move into `claimed`, `in_progress`, `for_review`, `in_review`, `approved` or `done`. A later reset to `planned`, or a cancellation, does not unstart it. As fallback evidence, a prior code lane with no such work package but a recorded lane work tip counts as wholly started.

**How lane ids are assigned on a re-finalize.**

1. A group that contains started work packages takes their recorded lane id.
2. Every other group that shares at least one member with an unused prior lane reads back the one it shares the most members with. A tie goes to the lowest prior lane id.
3. A group that shares no member with any unused prior lane gets the next free lane id. Lane ids that held started work are never handed to a new group.

Started work packages recorded in the same lane are kept in one group even when their ownership no longer overlaps. An unstarted work package can still move: if an amendment makes a planned WP01 overlap an in-progress WP02, WP01 joins WP02's lane.

**When finalize refuses.** If an amendment cannot keep every started work package on its recorded lane, `finalize-tasks` refuses with `LANE_MEMBERSHIP_FROZEN` before it writes anything (no status event, no `lanes.json`, work package files restored). The cases are:

- the amendment would put started work packages from two lanes into one lane;
- a started work package's task file was removed without canceling it;
- a started work package changed `execution_mode`, so it would cross the `lane-planning` boundary;
- the status log cannot be read.

`--validate-only` reports the same refusal, and its lane preview now shows the lane ids a real run would write. `single_branch` Missions are not affected: their one repo-root lane has nothing to move. The JSON envelope and the remedy for each case are in [finalize-tasks internals §5](../api/finalize-tasks-internals.md#5-started-work-packages-keep-their-lane-lane_membership_frozen).

## See Also

- [Branch-Target Routing](branch-target-routing.md) — where each diff type lands, decided
  per artifact kind (`src/mission_runtime/artifacts.py`): planning + identity artifacts
  (spec, plan, tasks, work-package files, `data-model.md`, `lanes.json`, `meta.json`) go to
  the primary target branch for every topology; coordination-owned artifacts (status events,
  `acceptance-matrix.json`, `issue-matrix.md`, `analysis-report.md`) go to the coordination
  branch; code changes go to the lane branch; shared documentation and the merge target go
  to the base branch. Also explains the simple-case flat-topology collapse when no
  coordination branch or lane worktrees are configured.

## Lane-Specific Test Database Isolation (FR-006)

Two parallel SaaS / Django lanes used to share a single test database when their per-lane test runners booted concurrently, which produced flaky failures. Each lane workspace now exposes a lane-suffixed identifier via `LaneWorkspaceResult.lane_test_env`, which sets `SPEC_KITTY_TEST_DB_NAME=test_<safe-mission>_<safe-lane>`. Test settings modules (Django and otherwise) should read that env var when constructing their per-lane test database name; the helpers `lane_test_db_name()` and `lane_test_env()` in `specify_cli.lanes.lane_env` are the canonical entry points and guarantee distinct DB names for distinct `(mission_slug, lane_id)` pairs.
