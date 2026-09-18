"""Checkout-wide serialization for automatic review evidence commits.

The queue is deliberately narrower than Spec Kitty's status locking.  It may
remain held while the governed evidence commit invokes Git, but a caller must
release the short ``feature_status_lock`` used for review-cycle allocation
before that Git invocation.  Event/status mutation does not belong here.

This module is synchronous and process-local apart from the operating-system
file lock.  It creates no worker, daemon, scheduler, or retry loop.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from math import isfinite
from pathlib import Path

from kernel.git_topology import git_common_dir
from kernel.locks import LockAcquireTimeout, machine_file_lock
from specify_cli.core.checkout_file_lock import LOCK_DIRECTORY, acquire_or_raise

DEFAULT_VERDICT_SAVE_TIMEOUT_SECONDS = 10.0
"""Default maximum wait for the checkout-wide verdict-save queue."""

_LOCK_FILENAME = "review-verdict-save.lock"
_HELD_QUEUE_PATHS: ContextVar[frozenset[Path]] = ContextVar(
    "spec_kitty_held_verdict_save_queue_paths",
    default=frozenset(),
)


class VerdictSaveBusy(RuntimeError):
    """The checkout-wide verdict-save queue was not acquired in time."""

    def __init__(self, lock_path: Path, timeout_seconds: float) -> None:
        self.lock_path = lock_path
        self.timeout_seconds = timeout_seconds
        super().__init__(f"Timed out acquiring the checkout-wide verdict-save queue after {timeout_seconds:g} seconds: {lock_path}")


class VerdictSaveReentrant(RuntimeError):
    """The current execution context tried to acquire its queue twice."""

    def __init__(self, lock_path: Path) -> None:
        self.lock_path = lock_path
        super().__init__(f"The checkout-wide verdict-save queue is already held by this execution context: {lock_path}")


def verdict_save_queue_path(repository: Path) -> Path:
    """Return the mission-independent queue path for ``repository``.

    The canonical Git common-directory resolver collapses relative common-dir
    output, linked-worktree indirection, and filesystem symlinks.  Consequently
    every worktree and Mission sharing Git state converges on this path while
    independent clones remain independent.
    """
    return git_common_dir(repository) / LOCK_DIRECTORY / _LOCK_FILENAME


def verdict_save_queue_is_held(repository: Path) -> bool:
    """Return whether the current execution context owns this checkout queue.

    Downstream integration tests can combine this observation with their
    status-lock probe to enforce the required lock ordering without adding a
    production-only test hook.
    """
    return verdict_save_queue_path(repository) in _HELD_QUEUE_PATHS.get()


@contextmanager
def acquire_verdict_save_queue(
    repository: Path,
    *,
    timeout_seconds: float = DEFAULT_VERDICT_SAVE_TIMEOUT_SECONDS,
) -> Iterator[Path]:
    """Acquire the checkout-wide verdict-save queue for a bounded interval.

    Args:
        repository: Any file or directory inside the target Git checkout.
        timeout_seconds: Positive maximum acquisition wait in seconds.

    Yields:
        The canonical lock-file path, for diagnostics and assertions.

    Raises:
        ValueError: ``timeout_seconds`` is not finite and positive.
        VerdictSaveReentrant: This execution context already owns the queue.
        VerdictSaveBusy: Another process retains ownership past the timeout.
        kernel.git_topology.GitTopologyError: ``repository`` cannot be resolved
            to a Git common directory.
    """
    if not isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be finite and positive")

    lock_path = verdict_save_queue_path(repository)
    held_paths = _HELD_QUEUE_PATHS.get()
    if lock_path in held_paths:
        raise VerdictSaveReentrant(lock_path)

    lock = machine_file_lock(lock_path, blocking=True, timeout_s=timeout_seconds)
    acquire_or_raise(
        lock,
        build_timeout_error=lambda: VerdictSaveBusy(lock_path, timeout_seconds),
    )

    token = _HELD_QUEUE_PATHS.set(held_paths | {lock_path})
    try:
        yield lock_path
    finally:
        _HELD_QUEUE_PATHS.reset(token)
        lock.__exit__(None, None, None)


__all__ = [
    # Re-exported: the shared ``acquire_or_raise`` primitive (see
    # ``specify_cli.core.checkout_file_lock``) is the only place this module's
    # own code catches ``kernel.locks.LockAcquireTimeout`` now, but the name
    # stays public here so callers (and this module's own test double for the
    # ``kernel.locks`` injection seam, G6) can still raise/reference the exact
    # type this module's lock construction site will produce on contention.
    "LockAcquireTimeout",
    "VerdictSaveBusy",
    "acquire_verdict_save_queue",
]
