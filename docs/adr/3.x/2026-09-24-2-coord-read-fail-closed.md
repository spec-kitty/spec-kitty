---
title: 'ADR: the placement read seam raises on an unmaterialized coordination worktree'
description: 'A coord-partition read on CoordState.UNMATERIALIZED now raises CoordinationWorktreeUnmaterialized instead of silently substituting an empty PRIMARY path.'
status: Accepted
date: '2026-09-24'
---

## Context and Problem Statement

`mission_runtime.resolution._classify_artifact_surface` is the single classifier that
turns a mission's four-state coordination probe (`specify_cli.missions._read_path_resolver
.CoordState`) into a read decision for a coord-partition artifact kind (`STATUS_STATE`,
`ISSUE_MATRIX`, `ACCEPTANCE_MATRIX`, `DECISION_LOG`, `TRACER_FILE`, `REVIEW_CYCLE`,
`DECISION_LEDGER`). Before this ADR, the classifier's tail read:

```python
if coord_state is CoordState.DELETED:
    raise CoordinationBranchDeleted.for_mission(...)
if coord_state is CoordState.MATERIALIZED:
    return TopologySurface.COORD, coord_feature_dir(...)
# EMPTY / UNMATERIALIZED / NONE -> primary + PRIMARY stamp
return TopologySurface.PRIMARY, None
```

`CoordState.UNMATERIALIZED` names the state where `meta.json` declares a
`coordination_branch` that still exists in git, but the coordination worktree itself has
never been created on disk — the fresh-clone / CI-runner / removed-worktree window between
`mission create` and the mission's first coordination-branch write. In that state the
classifier fell through to the same `TopologySurface.PRIMARY, None` answer as the
genuinely-benign `EMPTY` (coord root present, mission dir absent) and `NONE` (no
coordination topology at all) states — an **empty-PRIMARY substitution**: a coord-partition
read resolves to the primary checkout, which typically has no copy of the coord-owned
artifact, so the read comes back empty.

A caller with no special handling treats that empty result as "this document has never been
written" rather than "the authoritative surface for this document could not be reached
right now." The consequence is not merely a `None`/empty return silently absorbed
somewhere: `retrospective.tracer_writer._read_current_coord_content` catches the resulting
`StatusReadPathNotFound`-family exceptions (via `_NO_EXISTING_CONTENT_EXCEPTIONS`), maps
them to `""`, and the tracer writer then **clobbers** a real coord-side trace file's header
from that empty baseline the next time it writes — a destructive read-then-write, not
merely a stale read. Roughly two dozen other coord `STATUS_STATE` readers with no catch of
their own would, after this fix, propagate the new raise instead of quietly reading empty;
each of those is the intended "desired fail-loud" outcome this ADR names (see Consequences).

The sibling `CoordState.DELETED` state already fails closed (`CoordinationBranchDeleted`,
#4403/#1848) precisely because a deleted coord branch carrying unmerged status is data
loss. `UNMATERIALIZED` is a different failure shape — the branch is not lost, only not yet
checked out — but it shares the same defect class as `DELETED` once compared against what
`EMPTY`/`NONE` actually mean: `EMPTY` and `NONE` are declared, expected steady states (a
mission that never took the coordination branch, or one whose coord worktree the operator
legitimately flattened); `UNMATERIALIZED` is a **transitional** window where the
authoritative surface unambiguously exists but is not yet reachable from this checkout, and
substituting empty-PRIMARY silently discards that distinction.

## Decision

**The placement read seam raises a new typed error, `CoordinationWorktreeUnmaterialized`,
for a coord-partition read on `CoordState.UNMATERIALIZED`, instead of returning the
empty-PRIMARY substitution.**

- `CoordinationWorktreeUnmaterialized` is added to
  `src/specify_cli/coordination/surface_resolver.py`, as a `StatusReadPathNotFound`
  subclass sitting beside the existing `CoordinationBranchDeleted` — mirroring its shape
  (`error_code`, `next_step`, `for_mission(...)` factory) so every existing
  `except StatusReadPathNotFound` handler (the sanctioned read-only degraders in
  `mission_runtime.read_dir_degrade` and `review.cycle`, plus every other absorbing
  catcher) keeps catching it unchanged.
- Its `error_code` is `COORDINATION_WORKTREE_UNMATERIALIZED` (distinct from
  `COORDINATION_BRANCH_DELETED`) and its `next_step` names the truthful recovery —
  **materialize** the coordination worktree (it self-materializes on the mission's first
  coordination-branch write, or an operator can force it via
  `spec-kitty doctor workspaces --fix`) — and explicitly does **not** suggest flattening
  the mission, which would be a false and destructive recovery for a branch that still
  exists.
- `mission_runtime.resolution._classify_artifact_surface` gains one new branch:
  `if coord_state is CoordState.UNMATERIALIZED: raise
  CoordinationWorktreeUnmaterialized.for_mission(...)`, inserted between the existing
  `DELETED` and `MATERIALIZED`/fall-through arms. `DELETED` -> `CoordinationBranchDeleted`
  and `MATERIALIZED` -> `TopologySurface.COORD` are unchanged.
- The scope is **coord-partition reads only**. A PRIMARY-partition kind (for example
  `PRIMARY_METADATA`) short-circuits to `TopologySurface.PRIMARY` in `declared_read_surface`
  before any coordination probe runs, so this change is structurally invisible to it — no
  new raise, no behavior change, for every non-coord-routing topology and every
  PRIMARY-partition artifact.
- `EMPTY` and `NONE` are explicitly **out of scope** and keep returning the declared
  `PRIMARY` surface unchanged. They are not the reported defect (#4959): `NONE` is a
  coord-less mission that never had a coordination branch to fail to reach, and `EMPTY` is
  a materialized-but-vacant coord root the project already treats as an operator-decided,
  loud-warned degrade (`docs/adr/3.x/2026-06-19-1-coord-empty-surface-fallback.md`).
  Folding either into this raise would widen the mission beyond the audited blast radius.

## Consequences

- **Coord readers now fail loud on the transitional window.** Any coord-partition
  `read_dir` (via `mission_runtime.PlacementSeam.read_dir` /
  `resolve_artifact_surface`) issued while the coordination worktree has not yet been
  materialized now raises `CoordinationWorktreeUnmaterialized` instead of silently handing
  back an empty PRIMARY path. Callers that already catch `StatusReadPathNotFound` (or its
  known subclasses) absorb this unchanged; the roughly two dozen coord `STATUS_STATE`
  readers with no catch of their own now propagate the raise to a caller boundary, which is
  the intended fail-loud outcome — each was audited (research.md) to land at a sane
  boundary rather than a raw traceback.
- **Sanctioned read-only degraders keep degrading.** `mission_runtime.read_dir_degrade` and
  `review.cycle`'s existing `except StatusReadPathNotFound` blocks absorb the new sibling
  exception exactly as they already absorb `CoordinationBranchDeleted` — no regression for
  non-destructive reads (NFR-002).
- **The tracer-writer clobber this mission set out to close is a separate, dependent fix.**
  `retrospective.tracer_writer._read_current_coord_content`'s narrowed catch (so a
  coord-topology unresolved/unmaterialized read propagates instead of degrading to `""`) is
  scoped to a later work package in this mission, not this ADR's change alone — this ADR
  only makes the underlying seam raise; the writer must still choose to let that raise
  through rather than catch-and-clobber.
- **`_coord_branch_exists` (`surface_resolver.py`) is untouched.** The new exception class
  is a pure addition beside `CoordinationBranchDeleted`; no existing function in
  `surface_resolver.py`, including the `#4979`/`#4950` `_coord_branch_exists` surface, was
  modified.
- **A future contributor extending the UNMATERIALIZED raise to `EMPTY`/`NONE`** must revisit
  the coord-empty loud-fallback ADR (`2026-06-19-1`) first — those states carry their own,
  separately adjudicated policy and are not silently absorbed into this decision.

## Alternatives Considered

- **Reuse `CoordinationBranchDeleted` for `UNMATERIALIZED`.** Rejected — its `next_step`
  recommends flattening the mission, which is false and destructive when the coordination
  branch is fully intact and merely not yet checked out.
- **Fix at the reader level only (e.g. only `tracer_writer`).** Rejected by operator
  decision (DM-01M38VWD) — a reader-local fix closes one symptom but leaves every other
  coord-partition reader silently substituting empty-PRIMARY on the same transitional
  window, reopening the same defect class the next time a new reader is added.
- **Widen the raise to cover `EMPTY` and `NONE` as well.** Rejected as out of scope — both
  are declared, expected steady states with their own existing policy; treating them as
  errors would regress the coord-empty loud-fallback decision and the coord-less topology
  path for no reported defect.

## References

- Mission `kitty-specs/coord-read-fail-closed-01M38VVH/`: `research.md` (Finding A),
  `contracts/seam-fail-closed-contract.md`, `data-model.md`.
- `src/mission_runtime/resolution.py::_classify_artifact_surface`,
  `declared_read_surface`, `resolve_artifact_surface`, `PlacementSeam.read_dir`.
- `src/specify_cli/coordination/surface_resolver.py::CoordinationBranchDeleted`,
  `CoordinationWorktreeUnmaterialized`.
- `src/specify_cli/missions/_read_path_resolver.py::CoordState`, `probe_coord_state`.
- Sibling ADR: `docs/adr/3.x/2026-06-19-1-coord-empty-surface-fallback.md` (the `EMPTY`
  policy this ADR leaves unchanged).
- Prior fail-closed precedent: `#4403`/`#1848` (`CoordinationBranchDeleted`, `DELETED`).
- This mission: `#4959`.
- Regression coverage: `tests/mission_runtime/test_coord_read_seam.py`,
  `tests/mission_runtime/test_resolution_typed_errors.py`.
