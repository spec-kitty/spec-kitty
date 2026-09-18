# Contract — Canonical lock primitive (`kernel/locks.py`)

Seeded from `MachineFileLock` (`specify_cli/core/file_lock.py`, already
sidecar-safe + pure stdlib). This is a **move + sync-surface extension**.

## Public surface (illustrative — /tasks + implementer finalize signatures)

```python
# async facade (preserves current MachineFileLock behaviour)
class MachineFileLock:
    def __init__(self, lock_path: Path, *, blocking: bool = False,
                 timeout_s: float | None = None) -> None: ...
    async def __aenter__(self) -> LockRecord: ...      # yields HOLDER metadata, never a payload handle
    async def __aexit__(self, *exc) -> None: ...        # truncate, not unlink

# sync facade (new — for bootstrap, status/locking, verdict queue, checkout, tracker, windows_migrate, pre_review_gate)
class SyncMachineFileLock:                              # or a `machine_file_lock(...)` contextmanager
    def __init__(self, lock_path: Path, *, blocking: bool = False,
                 timeout_s: float | None = None, reentrant: bool = False) -> None: ...
    def __enter__(self) -> LockRecord: ...
    def __exit__(self, *exc) -> None: ...

def read_lock_record(lock_path: Path) -> LockRecord | None: ...   # reads the SIDECAR record, never a payload
def force_release(lock_path: Path) -> None: ...                   # stale-holder recovery; truncate
```

## Guarantees (map to FR-006/007, NFR-005, C-004)

- G1 — **Caller supplies a dedicated lock-only path**: caller passes `lock_path`,
  a path that exists only to be locked; this exact path is opened, OS-locked, and
  truncated directly — nothing is derived from it, and it must never be a payload
  path (passing a payload path would truncate and overwrite that payload).
- G2 — **No payload handle yielded**: the value bound by `with` is a `LockRecord`
  (holder metadata). There is no API to read the protected resource *through* the
  held lock. → #4703 impossible by construction.
- G3 — **Release truncates** (inode-stable), never unlinks.
- G4 — **Both sync + async** over one `_LockCore`; `blocking`+`timeout_s` cover
  non-blocking-retry and blocking-with-timeout.
- G5 — **Re-entrancy** available (`reentrant=True` / thread-local) for
  `status/locking.py`.
- G6 — **Test-double seam**: a supported injection point so
  `verdict_commit_queue.py`'s double survives migration.
- G7 — **Sole raw-primitive holder**: the only module allowed raw `msvcrt`/`fcntl`
  (enforced by the FR-010 gate).

## Non-goals

- Not a distributed lock. Not a datastore lock. Loopback/local filesystem only.

## Migration acceptance (per site)

Each migrated site: (a) constructs the canonical primitive, (b) no raw
`msvcrt`/`fcntl`/`filelock` remains, (c) its allowlist entry in the FR-010 gate is
removed, (d) the gate is green at that commit, (e) the site's own behaviour test
(re-entrancy / timeout / cross-process, as applicable) passes under the SC-004
parity harness.
