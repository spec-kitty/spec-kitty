# Data Model: Host-aware mode predicate

## FileState (existing, `tool_surface/operations.py`)
Fields: `kind` (absent | file | directory | symlink), `sha256` (files), `target` (symlinks), `mode` (0..0o7777, required unless absent), `mtime_ns`.

## Mode equivalence (new; pure functions beside FileState)

| Function | Inputs | POSIX | Windows |
|---|---|---|---|
| `modes_equivalent(kind, observed, planned)` | kind, two ints or None | `observed == planned` | directory or symlink: True; file: `bool(o & 0o200) == bool(p & 0o200)`; any None: `observed == planned` |
| `mode_equivalent(observed, planned)` | two FileStates | kinds equal and `modes_equivalent` | same |
| `state_equivalent(observed, planned, *, ignore_mtime=True)` | two FileStates | kind/sha256/target equal (mtime too unless ignored) and `mode_equivalent` | same |
| `effect_action(before, after)` | two FileStates | create/delete/replace/update/retarget/chmod/None, with chmod iff not `mode_equivalent` | same |

Invariants:
- On POSIX, `effect_action` is byte-for-byte today's `_action`.
- `effect_action(x, x)` is None on both hosts.
- `mode_equivalent` is symmetric.
- The host is read via `kernel.paths.is_windows()` at call time.

## PhysicalEffect (existing)
The validator now checks `action == effect_action(before, after)`, so on Windows a chmod between equivalent modes is refused.
