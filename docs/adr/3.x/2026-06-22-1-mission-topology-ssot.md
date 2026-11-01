---
title: 'ADR: MissionTopology SSOT — Store the Mission Shape, Resolve It Once'
description: 'Stores the coordination-by-lanes mission shape as a `MissionTopology` value minted at creation instead of re-inferring it from disk; `flattened` stays a provenance flag.'
status: Accepted
date: '2026-06-22'
doc_status: active
kind: ADR
updated: '2026-06-22T00:00:00Z'
---

`src/runtime/next/runtime_bridge.py`, `src/specify_cli/core/mission_creation.py`,
`src/specify_cli/missions/_read_path_resolver.py`
**Design driver**: [#2069](https://github.com/Priivacy-ai/spec-kitty/issues/2069)
**Predecessor**: [ADR 2026-06-03-2 — ExecutionContext Owner and CommitTarget](2026-06-03-2-executioncontext-owner-and-committarget.md),
[ADR 2026-06-19-1 — Coord-Empty Surface Policy](2026-06-19-1-coord-empty-surface-fallback.md)

## Context

A Spec Kitty mission can take one of four shapes across the orthogonal
**coordination × lanes** grid: no-coord/no-lanes, no-coord/lanes,
coord/no-lanes, coord/lanes. That shape decides *where* a mission's planning
artifacts and status surface live — the **primary checkout**
(`kitty-specs/<slug>[-mid8]/`) versus the **coordination worktree**
(`.worktrees/<slug>-<mid8>-coord/...`).

Today **no shape is a first-class stored value.** Each consumer re-infers a
slice of it, ad-hoc, from scattered on-disk and git signals:

- `CommitTargetKind` is classified **per ref** at construction time, never read
  back as a mission shape.
- The `coordination_branch is None ⇒ FLATTENED` derivation is hand-rolled in
  **two independent places**: behind the canonical construction door at
  [`resolution.py:705-718`](../../../src/mission_runtime/resolution.py)
  (`_resolve_coordination_branch`), **and** a second, parallel disk-`stat`
  ladder at [`runtime_bridge.py:144-211`](../../../src/runtime/next/runtime_bridge.py)
  (`_mission_declares_coordination_branch` plus a `_coord_path.exists() ⇒
  COORDINATION` branch).
- The read path keys on `CoordState.MATERIALIZED` — a disk `stat` of the
  `-coord` worktree — in `_read_path_resolver._resolve_existing_for_slug`.
- `read_lanes_json(...)` re-derives the lanes axis independently.

Because the shape is re-inferred at every seam, the slices **drift**: an
artifact written through one inference is read back through another. That drift
**is** the coord/primary read/write desync class —
[#2062](https://github.com/Priivacy-ai/spec-kitty/issues/2062) (a flattened
mission with a stale `-coord` husk reads the husk and mis-reports a `planned`
lane), [#2063](https://github.com/Priivacy-ai/spec-kitty/issues/2063)
(`spec.md`/tasks written to one surface, read from another →
"not found" divergence), and
[#2064](https://github.com/Priivacy-ai/spec-kitty/issues/2064)
(`map-requirements` and `finalize-tasks` disagree about where WP
`requirement_refs` live).

Prior fixes in this family were **symptomatic**: they band-aided one read leg
(e.g. threading a `declares_coordination` signal into the disk-`stat`
heuristic) while leaving the parallel inferences alive. The operator's binding
principle for this mission: *"if storing topology re-opens #2062, that proves
our prior #2062 fix was non-structural."*

## Decision

Land the **#2069 structural design**: name the mission shape, **store** it, and
resolve it once through a pure projection over the single existing construction
door.

1. **Name the shape.** Add a mission-level enum
   `MissionTopology {SINGLE_BRANCH, LANES, COORD, LANES_WITH_COORD}` in
   `mission_runtime/context.py`, naming the coordination × lanes 2×2 grid as one
   value. **`FLATTENED` is NOT an enum member** — it is a separate
   historical/metadata *provenance flag*. A mission that *was* coord and had its
   `coordination_branch` dropped is now `SINGLE_BRANCH`/`LANES` carrying a
   `flattened` mark; the shape value never encodes history. This is the single
   place the lanes-vs-coord cross-product is named.

2. **Store it, do not guess it.** `topology` is minted into `meta.json` at
   `mission create` and **read** thereafter — never re-inferred from disk or
   from `coordination_branch is None` at resolve time. Legacy missions are
   backfilled **once** via `spec-kitty migrate backfill-topology` (mirroring the
   `backfill-identity` precedent), with a `spec-kitty doctor topology --json`
   audit. Until a mission is backfilled, the imperative shell falls back to the
   legacy derivation exactly once — to **compute and persist** the topology —
   then reads the stored value.

3. **One resolver, pure.** Add
   `resolve_context_for_mission(mission_id: str, topology: MissionTopology) ->
   MissionExecutionContext` as a **pure projection** over the existing single
   construction door `build_execution_context` (functional core / imperative
   shell). It performs **no filesystem or git I/O**; the shell parses/persists
   `meta.json` and passes `id + topology`. `topology` is an authoritative input
   (optional input-assertion: fail-closed on a supplied-vs-resolved mismatch).
   This is a second projection of the same door — "one authority, two
   projections", the way `resolve_placement_only` already is — **not** a new
   parallel resolver (C-003).

4. **Retire BOTH live derivations.** The `coordination_branch is None ⇒
   FLATTENED` inference is removed from **both** sites: (a) `resolution.py:705-718`
   behind the door, **and** (b) the independent `runtime_bridge.py:144-211`
   disk-`stat` ladder. Leaving either alive is the parallel-inference
   death-spiral; both route through the stored topology under the same live
   convergence proof.

5. **`CommitTargetKind` becomes a topology-derived predicate.** Introduce a
   `MissionTopology`-derived per-ref predicate `routes_through_coordination(target)`
   and re-express the **9** `.kind is COORDINATION` branch-decision sites
   against it, so no site re-infers the per-ref topology. The
   `CommitTargetKind` **type itself is NOT deleted here** — its ~143
   value-literal references (≈63 constructions + ≈24 imports + ≈56 test refs
   across 41 files) are behavior-neutral and **carved to Mission B**
   ([#2070](https://github.com/Priivacy-ai/spec-kitty/issues/2070)). This
   mission stops *reading* `.kind` for decisions; the constructor field stays
   vestigial until Mission B eradicates the type.

6. **Adopt structurally on the read and write paths.** The read path
   (`_read_path_resolver._resolve_existing_for_slug` and the legs it feeds)
   resolves the surface from the **stored** topology, so `CoordState.MATERIALIZED`
   (a disk `stat`) is no longer the deciding signal (FR-006). The write path —
   every planning-phase commit and every `status.emit.emit_status_transition`
   call site — resolves its destination through the seam, not from the current
   `HEAD` branch (FR-007/FR-009). `safe-commit`'s two responsibilities are
   **separated**: mission-aware planning commits resolve via the seam; generic
   operator-file commits keep their existing behavior (NFR-002).

### Binding principle — structural, not symptomatic (C-004)

The fix is structural: **the read path consults the STORED topology, never
re-inferring the shape from on-disk worktree existence.** A flattened mission
resolves PRIMARY because its *stored* topology says so — not because a band-aid
out-voted an on-disk husk. By construction, the orphaned `-coord` husk is never
consulted, so #2062/#2063/#2064 cannot re-open. If storing the topology *could*
re-open #2062, that would prove the prior fix was a symptom patch; the
resolution is to stop the read path inferring from disk, never to re-add a
band-aid.

## Consequences

### Positive

- **The mission shape is one named, stored, authoritative value.** It is
  parseable after an interruption or an agent tool-switch — no caller has to
  recompute it from `coordination_branch is None`, `lanes.json` presence, or a
  worktree `stat`.
- **The resolver is pure and isolated-testable** (NFR-005): feed
  `(mission_id, topology)`, assert the returned `MissionExecutionContext` surface
  fields — zero filesystem/git fixtures. All FS/git access lives in the
  imperative shell.
- **Both hand-rolled derivations are dead** (SC-001): a `grep` for the
  `coordination_branch is None` / `_coord_path.exists()` inference pattern finds
  zero live decision sites.
- **The #2062/#2063/#2064 desync class is closed at the root** — structurally,
  not by close-on-static (witnessed live per NFR-001).

### Negative / risks

- **Backfill sequencing is a dogfooding landmine.** This mission's *own*
  `meta.json` must be topology-backfilled **before** any caller reads the stored
  field (FR-003); flatten/coord friction is expected during implement, carried
  under the live-evidence rule.
- **Transient on-disk×git states are NOT subsumed by the enum** (C-006). The
  create→first-write window ([#1718](https://github.com/Priivacy-ai/spec-kitty/issues/1718):
  topology = COORD but the worktree is not yet materialized) and the
  coord-deleted state ([#1848](https://github.com/Priivacy-ai/spec-kitty/issues/1848):
  declared branch deleted from git → `CoordinationBranchDeleted` data-loss
  carve-out) are orthogonal to the four enum cells and **stay discriminated by
  `probe_coord_state`** (with the branch signal). A `LANES_WITH_COORD` mission
  can be MATERIALIZED/EMPTY/UNMATERIALIZED/DELETED at any instant; the stored
  topology does not encode that and must not try to.
- **The `CommitTargetKind` type lives vestigially** until Mission B (#2070). The
  9 decision sites no longer read it, but the constructor field and its ~143
  value-literal references remain until the behavior-neutral eradication lands.

## Alternatives considered

- **Derive-and-carry per call** (the #2069 ticket's original lean). Rejected:
  recomputing the shape per call is itself the drift vector this mission exists
  to remove — every recomputation is another place the slices can diverge.
- **A new unified parallel resolver.** Rejected (C-003): `build_execution_context`
  is already the single, verified construction door (per missions `01KVGCE8`/
  `01KVN754`). `resolve_context_for_mission` *projects* it; introducing a second
  resolver that re-reads `meta.json`/`lanes.json`/git independently would
  re-create the very split-brain under repair.
- **The original adopt-`resolve_placement_only` + band-aid-the-read-path plan.**
  Superseded as symptomatic (D-2/C-004): threading a `declares_coordination`
  signal into the disk-`stat` heuristic treats the symptom; it leaves the disk
  `stat` as a topology signal and is re-openable.
- **Delete the whole `CommitTargetKind` type in-mission.** Rejected: 41-file
  churn balloons a focused seam mission with zero correctness gain. Carved to
  Mission B (#2070) as principled cleanup over an already-correct door — the
  #2065 read-side strangler pattern.

## References

- Mission spec: `kitty-specs/single-planning-surface-authority-01KVPR00/spec.md`
- Phase-0 decisions (D-1..D-8): `kitty-specs/single-planning-surface-authority-01KVPR00/research.md`
- Design driver: [#2069](https://github.com/Priivacy-ai/spec-kitty/issues/2069) (MissionTopology SSOT seam)
- Closed structurally: [#2062](https://github.com/Priivacy-ai/spec-kitty/issues/2062), [#2063](https://github.com/Priivacy-ai/spec-kitty/issues/2063), [#2064](https://github.com/Priivacy-ai/spec-kitty/issues/2064)
- Mission B (behavior-neutral follow-on, blocked-by this mission): [#2070](https://github.com/Priivacy-ai/spec-kitty/issues/2070) — `CommitTargetKind` type eradication + richer-API adoption at the 14 `resolve_placement_only`/`resolve_action_context` call sites
- Write-side twin (kind-aware placement over the stored topology): [ADR 2026-06-24-1 — Kind- and topology-aware artifact placement](2026-06-24-1-kind-and-topology-aware-artifact-placement.md) ([#2090](https://github.com/Priivacy-ai/spec-kitty/issues/2090) / [#2101](https://github.com/Priivacy-ai/spec-kitty/issues/2101))
- Epics: [#1716](https://github.com/Priivacy-ai/spec-kitty/issues/1716) (single surface authority), [#2007](https://github.com/Priivacy-ai/spec-kitty/issues/2007), [#1619](https://github.com/Priivacy-ai/spec-kitty/issues/1619) (execution-context)
- Transient-state carve-outs preserved: [#1718](https://github.com/Priivacy-ai/spec-kitty/issues/1718) (create-window), [#1848](https://github.com/Priivacy-ai/spec-kitty/issues/1848) (coord-deleted)
- Canonical seams: [`src/mission_runtime/context.py`](../../../src/mission_runtime/context.py) (`MissionExecutionContext`, `CommitTargetKind`), [`src/mission_runtime/resolution.py`](../../../src/mission_runtime/resolution.py) (`build_execution_context`, retired derivation), [`src/runtime/next/runtime_bridge.py`](../../../src/runtime/next/runtime_bridge.py) (retired second derivation)
