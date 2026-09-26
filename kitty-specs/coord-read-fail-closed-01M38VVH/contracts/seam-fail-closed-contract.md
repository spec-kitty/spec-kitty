# Contract — placement read seam fail-closed (Finding A / #4959)

**Surface**: `src/mission_runtime/resolution.py::_classify_artifact_surface` (+ `placement_seam`/`PlacementSeam.read_dir`); new exception in `coordination/surface_resolver.py`.

## Guarantees

1. For a **coord-partition** kind on `CoordState.UNMATERIALIZED`, the seam **raises** `CoordinationWorktreeUnmaterialized` (a `StatusReadPathNotFound` subclass) instead of returning empty-PRIMARY.
2. `DELETED` still raises `CoordinationBranchDeleted` (#4403 unchanged); `MATERIALIZED` still returns the COORD surface; `EMPTY`/`NONE` unchanged (out of scope).
3. **PRIMARY-partition kinds never raise** (short-circuit before probe) — non-coord topologies (SINGLE_BRANCH/LANES/flat) and all primary reads are unaffected.
4. The new exception's `next_step` names the *materialise* recovery (the branch exists), never *flatten* (that would be false for UNMATERIALIZED).
5. Existing `StatusReadPathNotFound` / `CoordinationBranchDeleted` catchers absorb the new sibling unchanged (no regression in sanctioned read-only degraders / aggregators).

## Acceptance (red-first)

- **AC-S1**: a coord-partition `read_dir` on UNMATERIALIZED raises `CoordinationWorktreeUnmaterialized`; pre-fix it returns an empty-PRIMARY path.
- **AC-S2**: `DELETED` still raises `CoordinationBranchDeleted`; a PRIMARY-kind read on the same mission does not raise (regression pin).
- **AC-S3**: sanctioned read-only degraders (`read_dir_degrade.py`, `review/cycle.py`) still degrade (their catch absorbs the sibling); a representative no-catch coord `STATUS_STATE` reader now fails loud at a sane boundary (not a raw traceback).
