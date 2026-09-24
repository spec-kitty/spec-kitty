# Data Model — Coord Reads Fail Closed

No new persisted schema. This mission changes how the placement read seam **classifies coord-surface state → read behavior**, and how two readers **resolve to the authoritative partition**.

## 1. CoordState → read behavior (the seam contract)

`_classify_artifact_surface` (`src/mission_runtime/resolution.py`), for a **coord-partition** kind:

| CoordState | Meaning | Before | After (this mission) |
|---|---|---|---|
| `MATERIALIZED` | coord dir present | return COORD surface | unchanged (return COORD) |
| `DELETED` | coord root absent, branch gone from git | raise `CoordinationBranchDeleted` (#4403) | unchanged |
| `UNMATERIALIZED` | coord root absent, **branch still declared in git** (fresh clone / removed worktree / CI) | return empty-PRIMARY → readers clobber/act-on-empty | **raise `CoordinationWorktreeUnmaterialized`** |
| `EMPTY` | coord root exists, mission dir absent | return empty-PRIMARY | unchanged (out of scope; see Deferred) |
| `NONE` | no coord topology | return PRIMARY | unchanged |

PRIMARY-partition kinds short-circuit to `TopologySurface.PRIMARY` **before any probe** (`resolution.py:1928-1929`) and can never raise — the blast radius is coord-partition reads only.

## 2. Exception hierarchy (additive)

```
StatusReadPathNotFound                     (existing base; existing catchers absorb subclasses)
├── CoordinationBranchDeleted              (#4403, DELETED; next_step → flatten / doctor --fix)
└── CoordinationWorktreeUnmaterialized     (NEW, UNMATERIALIZED; next_step → materialise the worktree)
```

New class lives in `coordination/surface_resolver.py` (additive; does not touch `_coord_branch_exists`, C-002). Its `error_code` and `next_step` are UNMATERIALIZED-specific and truthful (the branch exists; the fix is to materialise, not flatten).

## 3. Authoritative-partition resolution (the reader contract)

| Reader | Artifact | Partition kind it MUST use |
|---|---|---|
| `decisions/service.py::_resolve_mission_id` / `_mission_dir` | `meta.json` | `PRIMARY_METADATA` (never `STATUS_STATE`/coord — meta.json lives only on PRIMARY) |
| `acceptance/__init__.py::_has_blocking_clarification_marker` | decision ledger index | PRIMARY spec dir (unchanged — the reference the service must agree with) |
| `retrospective/tracer_writer.py::_read_current_coord_content` | `traces/<cat>.md` | coord surface; on UNMATERIALIZED/undecodable → **propagate/refuse**, never `""`→clobber |

Invariant: the decision service and `accept` resolve the ledger/metadata to the **same** partition → no split-brain, no `MISSION_NOT_FOUND` husk, no permanent accept dead-end.

## 4. Tracer read outcome classification (post-fix)

| Read outcome | Before | After |
|---|---|---|
| coord surface unresolved/unmaterialised | `""` → clobber real file | **raise** (fail closed) |
| existing file, undecodable byte (`UnicodeDecodeError`) | `""` → clobber | **refuse** (corruption ≠ empty) |
| resolved surface, file genuinely absent | `""` (first write) | `""` (unchanged — legitimate) |
| resolved surface, file present | read + append | unchanged |
