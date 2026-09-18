# Quickstart — using the canonical primitives

After this mission, a developer uses one door per concern.

## Lock a resource (sync)

```python
from kernel.locks import SyncMachineFileLock   # or machine_file_lock(...)

with SyncMachineFileLock(runtime_root / "cache" / ".update.lock", blocking=True, timeout_s=30) as holder:
    # 'holder' is holder METADATA (LockRecord) — there is no handle to the payload.
    # Do the guarded work. NEVER read the resource "through" the lock — the API
    # doesn't let you, which is the #4703 fix by construction.
    ...
```

## Lock a resource (async)

```python
from kernel.locks import MachineFileLock

async with MachineFileLock(resource, blocking=False) as holder:
    ...
```

## Delete a managed (possibly read-only) asset

```python
from specify_cli.core.safe_delete import safe_unlink, safe_rmtree

safe_unlink(managed_file)     # clears the read-only bit (no-follow) then unlinks
safe_rmtree(managed_dir)      # rmtree with the force-writable onerror shim
```

## Check the platform

```python
from kernel.paths import is_windows

if is_windows():
    ...
# In tests: monkeypatch.setattr("kernel.paths.is_windows", lambda: True)
#           (never set os.name — it flips pathlib and crashes pytest)
```

## What the gates enforce

- Import or call raw `msvcrt`/`fcntl`/`filelock` outside `kernel/locks.py`
  → `tests/architectural/test_lock_primitive_ban.py` fails, naming your file.
- Inline `os.name == "nt"` / `sys.platform == "win32"` outside `kernel/paths.py`
  (except a documented C-module import guard)
  → `tests/architectural/test_os_detection_ban.py` fails.

Add a new locking or platform-branching site → route it through the canonical
door, or the gate stops the PR.
