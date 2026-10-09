"""The per-run-dir cursor lock — the single mutual-exclusion primitive over a
mission run's ``state.json`` read-modify-write (mission
``serialise-next-advance``, closes #5854 / #5682).

Why this module exists
----------------------
Advancing a run is a read-modify-write on ``<run_dir>/state.json``: the engine
re-reads the snapshot, validates it against the plan, appends the lifecycle
events and atomically replaces the snapshot. The writers are
:func:`engine._commit_advance` (via ``commit_advance`` and ``next_step``),
:func:`engine.provide_decision_answer`, and the retrospective-gate capture and
rollback in ``runtime_bridge``. Nothing serialised them, so two overlapping
``next`` invocations could both pass the stale check, both append events, and
let the last ``state.json`` write win (the #5854
true-concurrency TOCTOU).

This module provides the one lock resource that closes that class by
construction, mirroring the sibling run-INDEX lock
(:mod:`runtime.next.run_index`, #5389/#5390):

1. **Dedicated sidecar (lock guarantee G1).** The lock is taken on
   ``<run_dir>/state.json.lock`` -- a path that exists ONLY to be locked, never
   the ``state.json`` payload. :func:`kernel.locks.machine_file_lock` opens and
   truncates the path it is given, so a payload path would be destroyed.
2. **One canonical primitive (NFR-003, DIRECTIVE_043).** All cross-process
   locking routes through :func:`kernel.locks.machine_file_lock`; this module
   adds no raw ``fcntl``/``msvcrt``/``filelock`` of its own, so
   ``tests/architectural/test_lock_primitive_ban.py`` stays green.
3. **Commit-span hold only (NFR-001/NFR-002).** The caller acquires this lock
   around the read-validate-append-write (for ``next_step``, the plan too) and
   releases it right after the snapshot write; it is never held across
   composition executor dispatch. The hold is not always sub-second: it also
   spans emitter calls made during the commit (the decision-log emitter makes
   git commits) and the ``before_run_completed`` retrospective capture. The
   bounded ``timeout_s`` is comfortably below the 60 s stale-reclaim ceiling
   (:data:`kernel.locks.STALE_AFTER_S_DEFAULT`).

Lock ordering (C-002, no deadlock): ``get_or_start_run`` releases the run-index
lock before the bootstrap read, and this run-cursor lock is only acquired later,
during the advance -- the two are never held nested.

The lock is NON-reentrant: ``fcntl`` locks conflict across distinct open file
descriptions even within one process, so each write path acquires the lock
exactly once and the inner ``_commit_advance`` never re-acquires it.
"""

from __future__ import annotations

from pathlib import Path

from kernel.locks import SyncMachineFileLock, machine_file_lock

__all__ = [
    "run_cursor_lock",
]

_STATE_FILENAME = "state.json"
_LOCK_SUFFIX = ".lock"
#: Bounded wait for the run-cursor lock. Comfortably above the typical hold of
#: a snapshot re-read + event append + atomic replace (longer when an emitter
#: makes git commits under the lock), well under the 60 s
#: stale-lock ceiling. Matches ``run_index._LOCK_TIMEOUT_S``. Read at call time
#: so a test may monkeypatch it for a deterministic held-lock-blocks probe.
_LOCK_TIMEOUT_S = 10.0


def _run_cursor_lock_path(run_dir: Path) -> Path:
    """A DEDICATED lock-only sidecar beside ``state.json`` (never the payload — G1)."""
    return run_dir / (_STATE_FILENAME + _LOCK_SUFFIX)


def run_cursor_lock(run_dir: Path) -> SyncMachineFileLock:
    """The canonical run-cursor write lock: a bounded, blocking machine file lock.

    Blocking with a bounded ``timeout_s`` so a contended advance waits for the
    in-flight writer rather than failing immediately; a wait past the deadline
    raises :class:`kernel.locks.LockAcquireTimeout`, which the caller maps to a
    ``blocked`` Decision.
    """
    return machine_file_lock(_run_cursor_lock_path(run_dir), blocking=True, timeout_s=_LOCK_TIMEOUT_S)
