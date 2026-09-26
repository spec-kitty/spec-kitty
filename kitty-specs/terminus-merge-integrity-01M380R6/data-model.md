# Data Model — Terminus / Merge-Coord Integrity

Phase 1 output. The "entities" here are the authority objects and value objects the terminus
transaction operates on (this is developer-tooling infra, not a persistence schema).

## Value objects & authorities

### `ApprovedWpCommitSet` (the claim)
- **Fields**: `wp_id → {approved_commit_shas: list[sha]}` for every WP the manifest claims done/approved; `excluded_wp_shas: set[sha]` (canceled/removed WP commits that must NOT land).
- **Source**: the authoritative coordination surface (via `SurfaceAuthority.resolve_for_read`) + lane→branch identity (via `LaneIdentity`).
- **Invariant**: derived once per terminus transaction; the verifier compares the target tree against exactly this set.

### `MergeTarget` (single authority — C-1)
- **Fields**: `branch: str`, `source: {"cli_flag","persisted","meta"}` (provenance), `resolved_at`.
- **Precedence**: explicit `--target` > persisted MergeState.target > meta.json.
- **Invariant**: persisted into MergeState at first resolution; every phase and every `--resume` reads this, never re-derives from meta.

### `MergeLock` (owned — C-2)
- **Fields**: `owner_token` (pid + start-time or merge-state id), `target`, `acquired_at`.
- **Invariant**: `--abort` releases only a lock whose `owner_token` matches the aborting invocation; a non-owned live lock is never unlinked. Dead-owner reclaim requires an explicit liveness check.

### `CoordCheckpoint` (S-B)
- **Fields**: `coord_ref`, `tip_sha_at_checkpoint`.
- **Invariant**: teardown may proceed only if all commits after `tip_sha_at_checkpoint` have been projected onto the target AND the current coord tip advances from `tip_sha_at_checkpoint` under CAS (unchanged since checkpoint) — else abort teardown.

### `SurfaceAuthority` (S-C)
- **Operations**: `resolve_for_read() → dir` (loud-primary-fallback permitted); `resolve_for_write() → dir | Refusal` (fail-closed when the coord worktree/branch is unresolved/unmaterialized).
- **Invariant**: no terminus WRITE degrades to an empty/stale primary directory.

### `LaneIdentity` (C-4)
- **Fields**: `lane_id` (stable, minted at creation), `branch`, `base_ref` (consults `origin/<lane>`).
- **Invariant**: identity is bound to the git branch at creation and never recomputed positionally; base resolution prefers `origin/<lane>` over a fresh cut from local main.

## Behaviors / state transitions

### Terminus transaction (the ordered gate)
```
resolve MergeTarget → acquire owned MergeLock → advance target ref (CAS)
  → project all post-checkpoint coord commits → verify(target, ApprovedWpCommitSet)
     ├─ pass → gated teardown → report success (exit 0)
     └─ fail → refuse (no teardown, no mutation) → non-zero + recovery guidance
```

### Residue classification (C-3)
- Input: working-tree churn + **stored mission topology**.
- Transition: churn classified as coord-residue **only** under COORD topology; on lanes/single_branch, planning artifacts are preserved (never `reset --hard`ed).

### Legacy detection (FR-012)
- Input: MergeState/coord state lacking the post-fix schema/marker.
- Transition: refuse with recovery instruction; no auto-heal.

## Validation rules (map to FR/NFR)
- Verifier reachability check ⇒ FR-001, FR-002, SC-001, SC-003.
- CAS advance ⇒ FR-003.
- Projection + coord CAS + SHA-scoped heal ⇒ FR-004, FR-005.
- Write gate ⇒ FR-006. Target authority ⇒ FR-007. Owned lock ⇒ FR-008.
- Topology residue ⇒ FR-009. Lane identity ⇒ FR-010. Behind-HEAD ⇒ FR-011.
