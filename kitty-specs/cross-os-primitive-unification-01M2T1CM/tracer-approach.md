# Tracer: Approach — Cross-OS Primitive Unification (01M2T1CM)

Seeded at planning; append during implementation.

## Sequencing thesis (from the grounding squad)

Tidy-first, dependency-ordered:

1. **WP01 — OS-detection kernel seam** (tidy-first, no lock dependency). Promote
   `kernel/paths.py::_is_windows` public; route the 4 `_is_windows` defs + the
   `os.name`/`sys.platform` zoo through it. De-noises `core/file_lock.py`
   *before* it moves to kernel.
2. **WP02 — safe-delete consolidation** (tidy-first, parallel to WP01). One C2
   util (`specify_cli/core/`), `lstat`+`S_IMODE`-masked semantics; delete the 3
   live copies; fold the campsite-matched anchor-path sha256 normalization +
   `_children_tolerated` defensive guard (both in `asset_preparation.py`).
3. **WP03 — kernel/locks.py** (the big one). Move `MachineFileLock` core to
   kernel; add the sync surface + blocking/timeout. Depends WP01.
4. **WP04 — migrate stdlib-family lock sites** onto `kernel/locks.py`.
   Depends WP03.
5. **WP05 — migrate filelock-family + retire `filelock`** (highest risk; the
   deferral seam). Red-first cross-process parity tests simulating Windows lock
   semantics on POSIX. Depends WP03.
6. **WP06 — DIRECTIVE_043 gate** (import + call ban, non-vacuous floor,
   self-mutation test, shrink-only ratchet seeded fail-closed). Terminal =
   allowlist empty.

## Deferral seam

If cross-process + blocking-timeout parity for the `filelock` sites cannot be
proven in-mission, ship WP01–04 + WP06 with the ratchet still covering the
filelock sites and burn them down in a fast follow-up. (Operator elected full
scope with this as the fallback.)

## Implementation notes

_(append as encountered)_
