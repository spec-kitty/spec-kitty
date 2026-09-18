"""Shared bounded-wait lock-acquire primitive (#3773 item 4; migrated onto
``kernel.locks`` per WP05/#4714, FR-009/NFR-001).

``specify_cli.review.verdict_commit_queue`` (the checkout-wide verdict-save
queue) and ``specify_cli.status.locking`` (the per-feature status lock) each
build a lock rooted under ``<git-common-dir>/spec-kitty-locks/`` and translate
a bounded-wait timeout into a caller-specific typed exception. Before this
module, both call sites hardcoded the ``"spec-kitty-locks"`` directory name
and duplicated the "attempt a bounded acquire, translate the untyped timeout"
sequence. Before WP05, both also constructed their own ``filelock.FileLock``;
they now construct the canonical ``kernel.locks`` primitive via
:func:`kernel.locks.machine_file_lock` instead (the primitive's own G6
test-double injection seam -- see ``review.verdict_commit_queue``'s test
double, which now substitutes ``kernel.locks.SyncMachineFileLock``).

This module is the single place that shared plumbing lives. It does **not**
merge the two locks: each caller still constructs its *own* lock for its
*own* lock path, keeps its *own* re-entrancy bookkeeping (the queue's
context-local "already held" refusal vs. the status lock's per-thread
reentrant depth counter), and raises its *own* typed timeout exception. Only
the acquire/translate step around that per-lock instance -- plus the
directory constant -- is shared.
"""

from __future__ import annotations

from collections.abc import Callable

from kernel.locks import LockAcquireTimeout, LockRecord, SyncMachineFileLock

LOCK_DIRECTORY = "spec-kitty-locks"
"""Directory name, under a checkout's git common dir, holding Spec Kitty's file locks.

The single named constant for a literal that used to be hardcoded separately
in ``verdict_commit_queue.py`` and ``status/locking.py`` (Sonar S1192 across
the module boundary).
"""

__all__ = ["LOCK_DIRECTORY", "acquire_or_raise"]


def acquire_or_raise(
    lock: SyncMachineFileLock,
    *,
    build_timeout_error: Callable[[], Exception],
) -> LockRecord:
    """Enter ``lock`` (the canonical primitive), translating a bounded-wait timeout.

    ``lock`` must already be constructed by the caller -- via
    :func:`kernel.locks.machine_file_lock`, never ``SyncMachineFileLock``
    directly, so a test can substitute the whole lock behaviour by
    monkeypatching ``kernel.locks.SyncMachineFileLock`` (G6) -- with its own
    lock-file path, ``blocking``/``timeout_s`` wait mode, and any re-entrancy
    flag it wants. This helper only owns the enter-and-translate step, not
    lock construction or release. Callers remain responsible for releasing a
    lock they successfully entered (typically via ``lock.__exit__(None, None,
    None)`` in a ``try``/``finally`` around the protected section) and for any
    re-entrancy bookkeeping around the call.

    The primitive's own :func:`kernel.locks._ensure_dir` creates
    ``lock.lock_path``'s parent directory (at ``0o700`` on POSIX) as part of
    every acquire attempt, so this helper does not duplicate that step.

    Args:
        lock: An unentered lock built by :func:`kernel.locks.machine_file_lock`.
        build_timeout_error: Builds the caller's own typed exception when the
            acquire attempt exceeds the lock's own bounded wait. Called with
            no arguments; the caller's closure already has whatever context
            (lock path, mission slug, timeout) its exception needs.

    Returns:
        The :class:`~kernel.locks.LockRecord` yielded by a successful entry.

    Raises:
        Exception: Whatever ``build_timeout_error()`` returns, chained from
            the underlying :class:`kernel.locks.LockAcquireTimeout` via
            ``raise ... from exc``.
    """
    try:
        return lock.__enter__()
    except LockAcquireTimeout as exc:
        raise build_timeout_error() from exc
