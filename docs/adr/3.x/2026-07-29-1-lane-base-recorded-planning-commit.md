---
title: 'ADR: Lane Base Merges the Recorded Planning-Artifact Commit (FR-009)'
description: 'Each lane gains the planning-artifact commit recorded at finalize-tasks as an extra ancestor, leaving its git parentage intact and never reading a live branch tip.'
status: Accepted
date: '2026-07-29'
updated: '2026-10-04'
---

## Context

ADR [2026-04-03-1](./2026-04-03-1-execution-lanes-own-worktrees-and-mission-branches.md)
made the execution lane the git branch/worktree unit and required "every mission gets
one integration branch." WP04 (#1348) extended lane parenting so a coordination-topology
mission's lanes branch from `coordination_branch` (`meta.json`), not the legacy
`mission_branch` field, and registered the status-files sparse-checkout exclusion so a
lane worktree cannot see `status.events.jsonl` / `status.json`.

`coordination_branch` is minted at `mission create` — **before** `spec.md` / `plan.md`
/ `tasks.md` / `tasks/WP*.md` exist. Those planning artifacts are PRIMARY-partition kinds
(`SPEC`, `FINALIZED_EXECUTION_PLAN`, `TASKS_INDEX`, `WORK_PACKAGE_TASK`, `LANE_STATE`,
`PRIMARY_METADATA`) and commit to `target_branch` for every topology (ADR
[2026-06-24-1](./2026-06-24-1-kind-and-topology-aware-artifact-placement.md)). A lane
branched purely from `coordination_branch`'s pre-planning mint point therefore has **no
common ancestor containing the planning artifacts** with the primary `target_branch`
tip the mission later consolidates against. This is issue
[#2993](https://github.com/Priivacy-ai/spec-kitty/issues/2993): the pinned regression
`tests/regression/test_issue_2993_lane_planning_ancestry.py` demonstrates the lane's
tree carries no `spec.md` / `tasks.md` at all, so a later 3-way merge between the lane
and an amended/retracted planning artifact fabricates a stale or resurrected result
instead of the planning branch's real content — a silent revert, not a conflict, so
nothing prompts a human to notice.

The same pinned regression fixes the **shape** the fix must take: Assert A requires the
lane branch to descend from the planning-artifact commit; Assert A' (the "coord-descent
guard") requires the lane branch to **still** descend from `coordination_branch` —
because a fix that satisfies Assert A by branching lanes off `target_branch` instead
would silently discard coordination-branch lifecycle state (status events, WP claim
history) the coord/primary partition depends on. Both must hold simultaneously.

## Decision

**Merge the recorded finalize-tasks planning-artifact commit into the lane on top of its
existing `coordination_branch` / `mission_branch` parentage.** The lane's primary git
parent is unchanged; the recorded commit becomes an additional ancestor via one
idempotent, per-lane merge — never a mutation of the shared `coordination_branch` ref
itself, and never a base derived from a *live* read of `target_branch`'s tip.

### 1. The recorded SHA is captured once, at `finalize-tasks`, and is immutable thereafter

`spec-kitty agent mission finalize-tasks` is the single write authority for
`lanes.json` (`LANE_STATE`, PRIMARY-partition — `mission_finalize.py:
_compute_and_write_lanes`). Immediately after `compute_lanes` returns and before
`write_lanes_json` persists the manifest, the command captures `target_branch`'s
**current** tip (`git rev-parse --verify <target_branch>` in the primary checkout) and
sets it as `LanesManifest.planning_commit_sha`. At this point in the finalize-tasks
pipeline, `target_branch` already carries every planning-artifact commit
(`spec-commit`, `setup-plan`, `tasks-commit` all land before `finalize-tasks` runs) —
so the captured value is, by construction, the recorded planning-artifact tip, not a
value that could still move. The field is written into the SAME `lanes.json` write that
already lands in the finalize-tasks commit — no second commit, no read-back, no
chicken-and-egg with the finalize-tasks commit's own hash. `LanesManifest` gained the
field (`str | None = None`, backward-compatible default for pre-fix `lanes.json`).

**Never re-derive it live.** The allocator MUST NOT call `git rev-parse target_branch`
(or read `coordination_branch`'s tip) at allocate time to answer "what should the lane
descend from" — that is the moving-tip trap this ADR exists to close: the tip depends on
when `implement` happens to run, and a mission's `target_branch` may legitimately advance
for reasons unrelated to this mission between `finalize-tasks` and `implement`. Only the
value frozen in `lanes.json` at finalize-tasks time is used.

### 2. The lane's git parent (`coordination_branch` / `mission_branch`) does not change

`allocate_lane_worktree` (`worktree_allocator.py`) still creates the lane branch from
`coordination_branch` (new-topology missions) or the legacy `mission_branch` field
(no-coordination missions), exactly as WP04 established. This preserves the
coord-descent guard (Assert A') by construction — there is no behavior to regress
because the parent selection is untouched.

### 3. The recorded commit is merged into the lane immediately after creation — idempotent, per-lane, non-mutating

A new helper (`_merge_recorded_planning_commit`) runs `git merge-base --is-ancestor
<planning_commit_sha> HEAD` inside the freshly created (or reused / crash-recovered)
lane worktree; if not already an ancestor, it runs `git merge --no-edit -m "..."
<planning_commit_sha>`. This:

- satisfies Assert A: the lane branch now descends from the planning-artifact commit;
- leaves Assert A' untouched: `coordination_branch` is still the lane's direct parent,
  so `git merge-base --is-ancestor coordination_branch <lane>` still holds trivially;
- is scoped to the ONE lane branch being created — `coordination_branch`'s own history
  is never mutated, so no other lane, no status-write machinery, and no
  `_refuse_preexisting_lane_status_deletions` merge-base computed against
  `coordination_branch` is affected (§5);
- is idempotent (ancestor-check short-circuits), so it runs safely on the
  worktree-reuse path, the crash-recovery path, and the fresh-create path alike — an
  existing lane created before `planning_commit_sha` existed self-heals the next time
  any WP in that lane is (re-)allocated, and a lane re-entered after a
  `finalize-tasks` re-run (e.g. a later WP added) picks up the newer recorded value;
- is `None`-safe: a `lanes.json` written before this fix has no
  `planning_commit_sha`, and the merge step no-ops, reproducing pre-fix behavior
  byte-for-byte (`tests/specify_cli/lanes/test_worktree_allocator_coord.py` is
  unaffected — its hand-built manifests never set the field);
- fails **closed**, not silently: a genuine conflict (expected to be rare to
  non-existent in practice, because `coordination_branch`'s own commits are
  COORD-partition status/matrix files, disjoint from the PRIMARY-partition planning
  files the recorded commit carries) aborts the merge and raises a structured
  `PlanningCommitMergeConflictError` with an operator-actionable `next_step`, mirroring
  the existing `DependencyLaneMergeConflictError` (#1684) shape. The half-merged state
  is never left on disk.

### 4. Resolving the coord-status-lineage question (FR-007 / ADR 2026-06-24-1 §5)

ADR 2026-06-24-1 §5 partitions PRIMARY (planning) writes from COORD (status/matrix/
tracer) writes, and this mission's FR-007 routes matrix/tracer/status writes off the
lane onto the coordination surface entirely — a lane never authors or commits a COORD-
partition artifact. Combined with §2 above (the lane's `coordination_branch` parentage
is untouched by this fix), the coord-status-lineage question resolves as follows:

**Decision: no change to coord-status lineage is required or made.** The lane's
relationship to `coordination_branch` — and therefore
`auto_rebase._refuse_preexisting_lane_status_deletions`'s `git merge-base HEAD
<mission_branch-or-coordination_branch>` reasoning — is exactly what WP04 established.
This fix is strictly additive: it gives the lane a **second**, disjoint ancestry line
(the planning commit) without touching the first (coordination_branch). Since
`coordination_branch` and `lanes_manifest.mission_branch` are the SAME branch for
coordination-topology missions (both composed by the identical
`branch_naming.mission_branch_name` grammar — `coord_branch_name` delegates to it
verbatim), this holds for both call shapes of `attempt_auto_rebase`'s `mission_branch`
parameter (`lifecycle_sync.py` passes `coordination_branch`; `lanes/merge.py`'s
`consolidate_lane_into_mission` passes `lanes_manifest.mission_branch` — the same ref).

FR-009 ancestry (this ADR, PRIMARY partition) and FR-008 row-aware-merge durability
(COORD partition, matrix/tracer) are hereby explicitly disentangled: FR-009 governs only
whether a lane's `git log` contains the planning-artifact commit; it says nothing about,
and does not gate, how the FR-008 merge driver resolves `%O` for `ISSUE_MATRIX` /
`ACCEPTANCE_MATRIX` conflicts (§5).

### 5. The FR-008 merge-driver `%O` partition is orthogonal to this ADR (E-B, adjudicated 2026-07-29)

`ISSUE_MATRIX` / `ACCEPTANCE_MATRIX` are COORD-partition kinds
(`mission_runtime/artifacts.py:172-183`) that `resolve_placement_only` /
`declared_read_surface` place topology-dependently
(`resolution.py:1602-1607`, `:1211-1217`). Under coordination topology they serialize
onto the single coordination worktree (`commit_router.py:248-306`) and **never diverge
on lane branches** — a lane worktree never holds a divergent copy of `issue-matrix.json`
/ `acceptance-matrix.json` to merge in the first place. The FR-008 row-aware merge
driver's `%O` (common ancestor) therefore comes from the **seam-resolved matrix surface
for the active topology** (coord lineage under coordination topology, primary /
`target_branch` lineage under flat), never from this WP's recorded `planning_commit_sha`.
There is no hard FR-008↔FR-009 coupling; WP11-T045 seeds `%O` from the resolved matrix
surface, not from the lane base this ADR governs.

### 6. No consolidation abort path

Consistent with ADR [2026-07-23-2](./2026-07-23-2-post-consolidation-deferral-and-external-enforcement.md),
this fix introduces no new abort trigger into lane consolidation or mission-branch
integration. A merge conflict while incorporating the recorded planning commit is
surfaced at **lane-allocation time** (`spec-kitty implement`), before any consolidation
begins, as a normal fail-closed allocator error the operator resolves like any other
`allocate_lane_worktree` failure (e.g. `DependencyLaneMergeConflictError`) — it is not a
new consolidation-time or post-consolidation gate.

## Consequences

### Positive

- #2993 is closed at the root: a lane's own `git log` contains the mission's
  planning-artifact commit, so a later amendment or retraction of `spec.md` / `tasks.md`
  on the primary checkout unions or deletes correctly against the lane instead of
  fabricating stale/resurrected content at consolidation.
- Zero regression to the WP04 (#1348) coordination-branch contract: `coordination_branch`
  remains the lane's direct git parent; every test asserting
  `merge-base --is-ancestor coordination_branch <lane>` keeps passing unmodified.
- The fix self-heals: because the merge step is idempotent and runs on every allocate
  path (fresh-create, reuse, crash-recovery), a lane created by pre-fix tooling, or a
  lane re-entered after a later `finalize-tasks` run recorded a newer SHA, picks up the
  correct ancestry the next time it is touched — no one-shot migration is required.
- `merge/ordering.py`'s topological sort is confirmed untouched (D-5): it is a pure
  frontmatter-dependency sort with no git-ancestry input, so this base change cannot
  perturb merge order.

### Negative / accepted trade-offs

- Every freshly created (or first-touched) lane worktree gains one extra merge commit.
  This is judged acceptable: it is a single, deterministic, disjoint-file-set merge
  (COORD-partition status files vs. PRIMARY-partition planning files essentially never
  overlap), and the alternative (no merge, the pre-fix state) is the #2993 defect itself.
- `planning_commit_sha` is captured once per `finalize-tasks` invocation and can advance
  on a re-finalize (e.g. after a later WP or dependency edit); an **already-allocated**
  lane does not retroactively rewrite its own history when this happens — it only picks
  up the newer value the next time that lane is allocated/recovered. This is judged
  correct, not a violation of "immutable once recorded": the field's *value* at any
  given finalize-tasks run is frozen and auditable; a later run recording a *new* value
  is a fresh, equally-frozen snapshot, not a mutation of the old one.

### Neutral

- Legacy (no-`coordination_branch`) missions already lazily create `mission_branch` from
  `target_branch`'s tip at first-lane-allocation time, which in practice already
  postdates `finalize-tasks`. The merge step still runs there (idempotent, uniform code
  path) but is expected to be a no-op in the common case.

## Alternatives considered

- **Branch the lane directly from `planning_commit_sha`, dropping `coordination_branch`
  as the parent entirely.** Rejected: this is exactly the shape the pinned regression's
  Assert A' (coord-descent guard) forbids — it would silently sever the lane from
  coordination-branch lifecycle state (status events, WP claim history) to fix #2993,
  trading one defect for another.
- **Fast-forward or merge `planning_commit_sha` into the shared `coordination_branch`
  ref itself before branching lanes from it.** Rejected: this mutates a branch shared by
  every lane and by the status-write machinery for a single lane's benefit, widening the
  blast radius far beyond what #2993 requires, and would need its own conflict/locking
  story across concurrently-allocating lanes. The per-lane merge achieves the same
  ancestry outcome with a strictly smaller footprint.
- **Re-derive the base live at allocate time (`git rev-parse target_branch`).** Rejected
  as the moving-tip trap this ADR exists to close (see the WP01 Reviewer guidance): the
  value would depend on unrelated activity landing on `target_branch` between
  `finalize-tasks` and whenever `implement` happens to run for a given WP.
- **Give the base full coord-status lineage parity (e.g., re-derive `coordination_branch`
  from a common synchronized point).** Rejected: unnecessary — §4/§5 above show FR-009
  ancestry and FR-008 matrix-merge durability are orthogonal; conflating them would
  reintroduce the SC-003 bundling risk research.md's D-5 explicitly warns against.
- **Fix the root cause upstream, in `implement.py`'s `_ensure_planning_artifacts_committed_git`
  / `resolve_placement_only` auto-commit no-op (Cause A/B per the #2993 regression
  triage), instead of the allocator.** Not rejected as wrong, but out of this WP's scope
  (`worktree_allocator.py` is WP01's authoritative surface): the allocator-level merge
  closes the defect regardless of whether that upstream no-op is ever separately fixed,
  and is the mechanism `lanes.json`/`meta.json` (this WP's `create_intent`) already
  points at.

## More Information

**Amends:** [2026-04-03-1 — Execution Lanes Own Worktrees and Mission Branches](./2026-04-03-1-execution-lanes-own-worktrees-and-mission-branches.md)
(extends the Lane Computation Contract: the lane base is now the recorded
`planning_commit_sha`, merged onto the existing `coordination_branch` / `mission_branch`
parent, not a bare branch pointer).

**Cites:**
- [2026-06-24-1 — Kind- and Topology-Aware Artifact Placement](./2026-06-24-1-kind-and-topology-aware-artifact-placement.md)
  (§5 partition: planning on PRIMARY for every topology; status/matrix/tracer on COORD
  under coordination topology).
- [2026-06-24-2 — Write-Branch Resolution Anchors `meta.json` on the PRIMARY Surface](./2026-06-24-2-write-branch-resolution-primary-anchor.md)
  (the write-branch/`target_branch` resolution this ADR's SHA capture reuses).
- [2026-07-23-2 — Post-Consolidation Deferral and External Enforcement of Negative Invariants](./2026-07-23-2-post-consolidation-deferral-and-external-enforcement.md)
  (no new consolidation abort path — §6 above).

**Issues:** [#2993](https://github.com/Priivacy-ai/spec-kitty/issues/2993) (lane lacks
common ancestor with planning artifacts — closed by this ADR),
[#1684](https://github.com/Priivacy-ai/spec-kitty/issues/1684) (dependent-lane
cross-lane-tip propagation invariant — preserved unchanged, §3),
[#2274](https://github.com/Priivacy-ai/spec-kitty/issues/2274) (lane-hygiene guard
compares `kitty-specs/` by commit-history, not content — **noted, not fixed, here**: the
extra planning-commit merge this ADR introduces changes a lane's commit history under
`kitty-specs/<slug>/` without changing its *content* relative to the planning branch, so
a commit-history-based hygiene check can false-positive immediately after this fix ships
on any mission whose lanes predate it. Coordinate the actual fix with
[#2273](https://github.com/Priivacy-ai/spec-kitty/issues/2273),
[#2626](https://github.com/Priivacy-ai/spec-kitty/issues/2626),
[#2570](https://github.com/Priivacy-ai/spec-kitty/issues/2570) — out of WP01's scope).

**Mission:** `kitty-specs/write-side-seam-matrix-tracer-01KYP3MH/` (WP01, FR-009,
NFR-005). Research: `research.md` D-5. Plan: `plan.md` (Risks). Tasks: `tasks.md` T001-T005.

**Regression pin:** `tests/regression/test_issue_2993_lane_planning_ancestry.py`
(Assert A / Assert A' shape this ADR's decision satisfies).

**Canonical seams:** [`src/specify_cli/lanes/worktree_allocator.py`](../../../src/specify_cli/lanes/worktree_allocator.py)
(`_merge_recorded_planning_commit`, `allocate_lane_worktree`),
[`src/specify_cli/lanes/models.py`](../../../src/specify_cli/lanes/models.py)
(`LanesManifest.planning_commit_sha`),
[`src/specify_cli/cli/commands/agent/mission_finalize.py`](../../../src/specify_cli/cli/commands/agent/mission_finalize.py)
(`_compute_and_write_lanes`, the SHA-capture producer),
[`src/specify_cli/lanes/auto_rebase.py`](../../../src/specify_cli/lanes/auto_rebase.py)
(`_refuse_preexisting_lane_status_deletions` — reconciled, unchanged, §4).

## Erratum (2026-10-04, #5627)

The `mission_finalize.py: _compute_and_write_lanes` citations above (the producer reference in section 1 and the canonical-seams list) point to that file as it was when this ADR was written. Mission `mission-finalize-degod-01M43EW2` later split it into phase modules, with bodies moved verbatim. `_compute_and_write_lanes` now lives in `src/specify_cli/cli/commands/agent/mission_finalize_lanes.py`, and `mission_finalize` still re-exports it. The decision is unchanged.
