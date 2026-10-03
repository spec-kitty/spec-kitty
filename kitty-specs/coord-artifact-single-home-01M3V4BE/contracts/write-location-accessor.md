# Contract: write-location accessor

**Operation:** `PlacementSeam.write_dir(self, kind: MissionArtifactKind) -> WriteLocation`
**Home:** `src/mission_runtime/resolution.py`, class `PlacementSeam` (L2261), beside `write_target` (L2304) and `read_dir` (L2318). `WriteLocation` and `Establishment` live in `src/mission_runtime/write_location.py`, which is new.
**Delegate:** for a COORD kind of a coordination-routed Mission, the work is done by `specify_cli.coordination.coord_seed.establish_coord_write_location(repo_root, mission_slug, kind, *, owned) -> WriteLocation` (new). The seam reaches it through a lazy import over the existing `coordination` ledger edge.
**Public surface:** `WriteLocation` and `Establishment` are exported from the `mission_runtime` package root (`__init__.py` `__all__`, plus `_PUBLIC_SURFACE` in `tests/architectural/test_mission_runtime_surface.py`). Modules outside `mission_runtime` import only from the root (MR-1/MR-2).
**Requirements:** FR-003, FR-003a, FR-004, FR-004a, FR-004b; C-001, C-002, C-008. Research D1, D4, D22, D23.

## Signature

```python
@dataclass(frozen=True)
class WriteLocation:
    path: Path
    surface_root: Path                    # root of the checkout holding `path`: the coordination worktree root,
                                          # or the repository root checkout; consumers never guess `.parent.parent`
    surface: Literal["primary", "coordination"]
    coord_state_before: CoordState | None
    establishment: Establishment          # NONE | MATERIALIZED | SEEDED | RESTORED_FROM_BRANCH
    seed: SeedReport | None = None

class PlacementSeam:
    def write_dir(self, kind: MissionArtifactKind) -> WriteLocation: ...
```

## Preconditions

- The `PlacementSeam` was built with `placement_seam(repo_root, mission_slug, owned=...)` (`resolution.py:2835`). The partition invariant was asserted at construction.
- The Mission resolves: `meta.json` is readable on the PRIMARY partition.

## Postconditions

| Case | Result |
|------|--------|
| `kind` is a PRIMARY-partition kind | `surface="primary"`, `path` = the declared PRIMARY dir (identical to `read_dir(kind)` today), `establishment=NONE`. No side effects. |
| COORD kind, topology `lanes` or `single_branch` | the PRIMARY dir, as today (C-008). No side effects. |
| E2-eligible COORD kind (`REVIEW_CYCLE`, `TRACER_FILE`, `ISSUE_MATRIX`, `ACCEPTANCE_MATRIX`) of a **PUBLISHED** (post-consolidation) Mission (`resolution.py:191-199`, E2 short-circuit L1961-1963) | `surface="primary"`, the PRIMARY Mission dir, `surface_root` = the repository root checkout, `establishment=NONE`. This is checked **before** any coordination probe, so it never raises `CoordinationBranchDeleted` and never writes into a torn-down worktree (D23). |
| COORD kind, coordination-routed, state `MATERIALIZED` | the coordination Mission dir. No side effects **unless a seed commit is pending**: a seed commit is **pending** iff the coordination branch history has no `Spec-Kitty-Coordination-Seed: <mission_id>` trailer **and** the coordination tip has no COORD-kind blob under the Mission dir, i.e. the Mission dir is wholly untracked, which only a refused seed leaves. A never-seeded pre-fix MATERIALIZED Mission (#5519 shape) has committed COORD blobs at the tip, so it never matches. When it is pending, the next seed attempt re-commits the dir with the trailer before the write (contracts/seed.md). |
| COORD kind, coordination-routed, state `UNMATERIALIZED` with a local branch (whether or not the branch already carries artifacts of this kind; D22) | the worktree is materialized via `CoordinationWorkspace.resolve`; then the `MATERIALIZED` or `EMPTY` row applies |
| COORD kind, coordination-routed, state `EMPTY`, **no** seed marker on the coordination branch (pre-fix Mission, D4) | seeded (`contracts/seed.md`); `establishment=SEEDED` |
| COORD kind, coordination-routed, state `EMPTY`, seed marker present (post-fix Mission; a regression) | loud `WARNING`, then COORD-kind paths only are restored from the branch tip (never PRIMARY files), then any root-only records are seeded; `establishment=RESTORED_FROM_BRANCH` |

The following hold in every case:
- `write_dir(kind).surface` matches the partition of `write_target(kind).ref`: the coordination worktree's branch is `write_target(kind).ref`. A property test over every `MissionArtifactKind` pins this.
- The returned `path` exists on return for COORD kinds of a coordination-routed Mission.
- A seed is logged at `WARNING` with its `SeedReport`, so callers that do not render it still surface it.

## Errors (raised; nothing is written)

| Code | When | Exception (existing unless marked) |
|------|------|------------------------------------|
| `COORDINATION_BRANCH_DELETED` | `meta.json` declares a coordination branch that does not exist | `CoordinationBranchDeleted` |
| `COORDINATION_WORKTREE_UNMATERIALIZED` | branch is remote-only (#4970 parity), or materialization failed after one re-probe | `CoordinationWorktreeUnmaterialized` via `_raise_unmaterialized` (`surface_resolver.py:877`) |
| `COORD_SEED_FORK_REFUSED` (new) | seed found a true fork (`contracts/seed.md`) | `CoordSeedForkRefused(ActionContextError)` (new) |
| `STATUS_LOCK_HELD` (new code on an existing exception) | status lock timeout during the seed | `FeatureStatusLockTimeoutError` (`status/locking.py:59`); the `error_code` attribute is added |
| `OWNED_COORDINATION_WORKSPACE_UNAVAILABLE` | owned checkout whose coordination workspace cannot be established | existing `OwnedRefusalCode` |

Every error message names the Mission, the coordination branch, and a recovery command.

## Relationship to existing seams

- **`assert_coord_write_materialized`** (`write_target_degrade.py:157-261`, formerly "the single decision locus for S-C"): absorbed (D22). It becomes a thin delegate to this accessor.
  - MATERIALIZED/EMPTY: no-op, except that a MATERIALIZED Mission with a pending seed commit (see the `MATERIALIZED` row above) gets its seed re-committed, as through `write_dir`.
  - UNMATERIALIZED with a local head: delegates to `write_dir(kind)`, which materializes and then restores or seeds, instead of refusing when the branch already carries the kind.
  - Remote-only: still refuses with `COORDINATION_WORKTREE_UNMATERIALIZED`.

  Its callers (`resolve_write_target_or_degrade(..., terminus_write=True)`, `write_seam.write_artifact`) are unchanged. Its old local-head refusal pins are re-pinned deliberately.

- **`resolve_placement_only` / `write_target`:** unchanged. They give the commit ref and are materialization-blind. `write_dir` gives the directory.
- **`read_dir`:** unchanged. It keeps the `EMPTY` → PRIMARY read fallback (C-002). It is never a write location for a COORD kind; the FR-014 gate enforces that.
- **`materialize_coord_surface_for_write`** (`surface_resolver.py:903`): becomes step 1 of `establish_coord_write_location`. Its two writer callers (`decisions/service.py:501,696`) switch to `write_dir`. The `doctor coordination` caller (`_coordination_doctor.py:1424`) keeps calling it, because it repairs a worktree and is not a writer.
- **`resolve_status_surface_with_anchor(for_write=True)`:** unchanged, and documented as "commit-ref oriented, not a write location". The read-side `EMPTY` warning goes loud for post-fix Missions in both coordination topologies.
- **`status_transition._coord_feature_dir`** (L400) and `transaction.py:490`'s inline composition: both are replaced by `write_dir(STATUS_STATE).path`. No second composer remains.

## Compatibility

- Additive API. No existing signature changes.
- Writers migrate call by call (IC-04). The FR-014 gate ratchets the migration.
- `lanes` and `single_branch` Missions: byte-identical behaviour (C-008).
