# Data Model — Verdict-matrix RMW preservation

No schema changes. This documents the entities and invariants the fixes must preserve.

## Entities

### Acceptance matrix (`acceptance-matrix.json`)
- **Fields**: `criteria[]` (each: criterion id, result, evidence), `negative_invariants[]` (each:
  invariant id, result e.g. `still_present`, evidence), `overall_verdict` (computed).
- **Read/write surface**: resolved by the placement seam — coordination surface for
  coord/lanes-with-coord topologies (materialized worktree), else primary.
- **Invariant (INV-A1)**: `overall_verdict` is a pure function of the current rows; it is `fail`
  whenever any row failed. A write must not change it except as a consequence of the single owned
  row it merges.
- **Invariant (INV-A2)**: a verdict write mutates exactly one row (its `entry_id`); all sibling
  rows are exactly those on disk at write time.

### Issue matrix (`issue-matrix.json`, legacy `issue-matrix.md`)
- **Fields**: issue rows (issue ref, verdict e.g. `fixed`, evidence ref, provenance).
- **Migration**: legacy `.md` → canonical `.json` on first JSON write; `.md` bytes retained.
- **Invariant (INV-B1)**: the first JSON write must contain every row from the authoritative
  (coord-aware) matrix that was read for this mission, plus the upserted row — never fewer.
- **Invariant (INV-B2)**: the write is staged on the primary copy and routed through the
  write-seam (which materializes coord + cleans primary residue); the read source being
  coord-aware must not move the write staging off primary.

### Entry / row
- Identified by an **entry_id** (criterion id, invariant id, or issue ref) with a result and
  evidence. Ownership: a verdict invocation owns exactly one entry_id for its write.

### Lock (reused, not modeled new)
- `feature_status_lock` — file lock keyed on `(git common dir, matrix_dir.name)`; one file
  coordinates all worktrees of a mission. Used only by #4858.

## State transitions

- **Acceptance verdict (#4858 fixed)**: read (pre-check) → run slow check (unlocked) → **acquire
  lock** → re-read on-disk matrix → splice owned row (insert-if-absent) → atomic write → commit →
  **release lock**.
- **Issue verdict (#4868 fixed)**: resolve coord-aware `read_dir` → if coord `.json` exists,
  short-circuit (already correct) → else migrate from `read_dir` legacy `.md` (preserving rows) →
  load rows → upsert requested issue → write (staged primary → seam materializes coord).

## Externally visible events / outputs

- Both commands emit their existing JSON result (`ok`/`status`/`migrated`/`write_status`). No new
  event types. The fix changes the *content correctness* of the committed matrix and (for #4868)
  the value of `migrated`, not the output schema.
