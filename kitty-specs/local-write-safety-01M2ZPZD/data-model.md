# Phase 1 Data Model: Local Write-Safety Hardening

This is an infrastructure/safety mission — the "entities" are on-disk resources and
their invariants, not domain records.

## Entities & Invariants

### MachineLock (`kernel.locks`)
- **Represents**: a cross-process advisory lock file.
- **Fields**: `lock_path` (regular file under a per-user `0700` root), owning fd.
- **Invariants**:
  - I1: opened with `O_NOFOLLOW` (POSIX) — never follows a symlink at `lock_path`.
  - I2: the inode persists across acquisitions (release truncates, never unlinks) → **no `O_EXCL`** on the shared open (C-003).
  - I3: parent directory is `0700`, established by the authority's own `_ensure_dir` (C-005).
  - I4: a hijack attempt (planted symlink) fails closed — the operation raises, never exit-0.

### NoFollowOpen (`kernel.no_follow` — NEW)
- **Represents**: the single canonical symlink-safe open primitive.
- **Invariants**: I5: exactly one implementation; consumed by `kernel.locks` and all specify_cli write sites. I6: Windows degrades to a safe no-op (`getattr(os,"O_NOFOLLOW",0)`).

### DecisionIndex vs DecisionEventLog (`decisions/`)
- **Represents**: the derived `index.json` projection vs the authoritative append-only decision event log.
- **Invariants**:
  - I7: after any set of concurrent opens/resolves, `index` entries == event-log `DecisionPointOpened` records, 1:1 (no lost updates).
  - I8: the service-level read-modify-write is serialized under a sidecar `index.json.lock` (never the payload).
  - I9: the event log is authoritative — `index` is always reconstructible from it; reconcile is a safe no-op when they already agree.

### OperatorContentBackup (`.kittify/`)
- **Represents**: operator-authored `missions/` and `memory/` preserved across re-init.
- **Invariants**: I10: no destructive-removal site deletes operator content without first moving it to a timestamped `.kittify/.backup-<UTC-ts>/` and reporting the path. I11: the "already initialized" predicate recognizes operator content, not only `config.yaml`. I12: backup targets never collide (timestamp + uniqueness).

### RuntimeRoot (`~/.spec-kitty`)
- **Represents**: the per-user home for locks, cold-install sentinel, prompt temp, and credentials.
- **Invariants**: I13: created/owned `0700` by a single canonical creator (not order-dependent across callers). I14: relocated paths (sentinel, prompt dir) resolve under it, never under world-shared temp.

### CredentialFile (`*/credentials.py`)
- **Represents**: a persisted API/hosted token file.
- **Invariants**: I15: created owner-only (`≤0600`) with no world-readable window (no 0644-then-chmod). I16: symlink-safe temp write (`O_NOFOLLOW`; `O_EXCL` appropriate for a fresh temp).

## Invariant → Requirement → Success-criterion trace

| Invariant | Requirement | Success criterion |
|-----------|-------------|-------------------|
| I1, I4 | FR-001, FR-003 | SC-001 |
| I2 | C-003 | SC-004 (re-acquisition unbroken) |
| I3, I13, I14 | FR-002, FR-011 | SC-006 |
| I5, I6 | C-004 | SC-004 (Windows), SC-001 |
| I7, I8 | FR-004 | SC-002 |
| I9 | FR-005 | SC-002 (repair) |
| I10, I11, I12 | FR-006, FR-007 | SC-003 |
| I15, I16 | FR-009 | SC-005 |
