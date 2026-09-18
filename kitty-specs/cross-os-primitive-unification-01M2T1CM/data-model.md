# Data Model — Cross-OS Primitive Unification (Phase 1)

This mission has no persistent datastore; the "entities" are the canonical
primitives and their invariants.

## E-01 — Canonical lock (`kernel/locks.py`)

**Represents**: mutual exclusion over a resource, cross-process, on Windows
(mandatory `msvcrt`) and POSIX (`fcntl`) alike.

**Structure**:
- `LockRecord` (holder metadata): `schema`, `pid`, `started_at` (via
  `kernel.clock`), `host`, `version`. Written to the *sidecar*, never the payload.
- Two facades over one `_LockCore` (open / os-lock / write-record / truncate /
  unlock): an **async** context manager and a **sync** context manager.
- Parameters: `blocking: bool`, `timeout_s: float | None` — cover both
  non-blocking-retry-until-deadline (current) and blocking-with-timeout (filelock/bootstrap).

**Invariants**:
1. **Sidecar derivation is owned by the primitive.** Caller passes the *resource*
   path; the primitive derives `resource.parent / f".{resource.name}.lock"`. A
   caller cannot point the lock at the payload. (FR-007)
2. **No payload handle is ever yielded.** Both context managers yield a
   `LockRecord`, never a file handle to the protected resource → a held lock can
   never be read as a payload (the #4703 footgun structurally impossible). (FR-007)
3. **Release truncates, never unlinks** (preserves inode identity so a contender's
   `O_CREAT` cannot mint a rival inode). (NFR-005)
4. **Re-entrancy preserved** where callers relied on it (`status/locking.py`
   thread-local counts). (NFR-005)
5. **Sole sanctioned holder** of raw `msvcrt`/`fcntl` (FR-010 gate).

## E-02 — Canonical safe-delete (`specify_cli/core/safe_delete.py`)

**Represents**: removal of managed, possibly-read-only assets on both OS.

**Operations**: `force_writable(path)`, `safe_unlink(path)`, `safe_rmdir(path)`,
`safe_rmtree(path)` (+ an `rmtree` onerror shim).

**Invariants**:
1. **No-follow (`lstat`) + masked (`S_IMODE`)**: clears the write bit on the
   entry itself, never a symlink target outside the managed tree. (FR-002, SC-006)
2. **Windows read-only refusal handled**: clear the write bit, then unlink/rmdir. (FR-001)
3. **One implementation**; the 3 live copies removed, the frozen migration copy
   untouched. (FR-003, C-002)

## E-03 — OS-detection seam (`kernel/paths.py::is_windows`)

**Represents**: the single "is this Windows?" answer.

**Invariants**:
1. **Patchable via module attribute** — overridable in tests without faking
   `os.name` (which flips `pathlib`→`WindowsPath` and crashes pytest). (C-003)
2. **One definition**; the 3 `_is_windows` defs + the inline `file_lock.py` check
   route through it; only C-module import guards stay raw. (FR-005, FR-012)

## E-04 — DIRECTIVE_043 gates (`tests/architectural/`)

**Represents**: by-construction bans that keep E-01/E-03 canonical.

**Invariants (non-vacuity, NFR-003)**:
1. **Concrete floor**: fails if the sanctioned module no longer *contains* the
   primitive (deleting the door must not trivially pass).
2. **Self-mutation**: a synthetic injected violation must be flagged.
3. **Shrink-only allowlist**: seeded fail-closed with all current sites; fails on
   growth; terminal = empty (lock) / import-guards-only (OS). Excludes
   `upgrade/migrations/` (C-002).
4. **Predicate honours the holder** (C-004): permits the canonical module's own
   raw calls + sidecar-record read.

## State transitions (lock lifecycle)

```
idle → acquire(blocking?, timeout?) → held(yields LockRecord)
held → release → idle           (truncate, not unlink)
held → force_release → idle     (stale-holder recovery; truncate)
acquire (contended, non-blocking) → NotAcquired
acquire (contended, blocking, deadline) → TimeoutError
```

No transition exposes the protected payload's bytes to the holder while `held`.
