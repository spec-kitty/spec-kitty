"""Run-wide charter synthesis lock (#6453).

``charter synthesize`` and ``charter resynthesize`` write the overlay, the
synthesis manifest, the provenance record and the project directive files in
several steps. Two concurrent runs interleave those writes. This module is the
one lock a writing run holds from just after the charter soundness gate to the
end of the command, so a second run waits a bounded time and then refuses with
``CHARTER_SYNTHESIS_LOCK_HELD`` instead of writing.

Placement follows the interim event-log lock (``kernel.event_log_append``):

- Inside a git repository the lock file is
  ``<git-common-dir>/spec-kitty-locks/charter-synthesis/<digest>.lock``, where
  ``<digest>`` is the first 32 hex characters of the SHA-256 of the resolved,
  ``os.path.normcase``-d worktree root. One lock per worktree: two worktrees of
  one repository hold different locks because they write different files.
- Outside a git repository the lock is ``<root>/.kittify/runtime/locks/charter-synthesis.lock``.
- When git cannot be invoked at all, the run refuses
  (:class:`SynthesisLockUnavailableError`) rather than lock where another run
  would not.

The lock is re-entrant per thread (``kernel.locks.machine_file_lock``), so
:func:`charter.activation.bundle_restamp.restamp_bundle_hash` can take it again
inside a run. It dies with its holder: a crashed run never leaves it held.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager, nullcontext
from pathlib import Path

from kernel.content_digest import sha256_digest
from kernel.errors import KittyInternalConsistencyError
from kernel.git_topology import GitTopologyUnavailableError, NotAGitRepositoryError, git_common_dir
from kernel.locks import LOCK_DIRECTORY, LockAcquireTimeout, machine_file_lock

__all__ = [
    "NON_GIT_LOCK_PATH",
    "SYNTHESIS_LOCK_SUBDIRECTORY",
    "SYNTHESIS_LOCK_TIMEOUT_S",
    "SynthesisLockHeldError",
    "SynthesisLockUnavailableError",
    "synthesis_lock",
    "synthesis_lock_path",
    "synthesis_lock_unless",
]

#: Directory under ``<git-common-dir>/spec-kitty-locks/`` that holds the per-worktree lock files.
SYNTHESIS_LOCK_SUBDIRECTORY = "charter-synthesis"

#: Bounded wait for the lock, in seconds (operator ruling, #6453).
SYNTHESIS_LOCK_TIMEOUT_S = 10.0

#: Lock file relative to the repository root when there is no git repository.
NON_GIT_LOCK_PATH = Path(".kittify/runtime/locks/charter-synthesis.lock")

_DIGEST_LENGTH = 32
_DIGEST_PREFIX = "sha256:"


class SynthesisLockHeldError(KittyInternalConsistencyError):
    """Another synthesis run holds the lock past the bounded wait; nothing was written."""

    def __init__(self, lock_path: Path, timeout_s: float) -> None:
        super().__init__(
            "CHARTER_SYNTHESIS_LOCK_HELD",
            f"Another `spec-kitty charter synthesize` or `charter resynthesize` run in this worktree holds the "
            f"synthesis lock {lock_path} (waited {timeout_s:g}s). Nothing was written. "
            "Retry after the other run finishes.",
        )


class SynthesisLockUnavailableError(KittyInternalConsistencyError):
    """Git could not be invoked to place the lock; nothing was written."""

    def __init__(self, root: Path, reason: object) -> None:
        super().__init__(
            "CHARTER_SYNTHESIS_LOCK_UNAVAILABLE",
            f"{root}: cannot place the charter synthesis lock because git could not be invoked ({reason}). Make git runnable in this checkout, then retry.",
        )


def synthesis_lock_path(repo_root: Path) -> Path:
    """Return the synthesis lock file for the worktree rooted at *repo_root*.

    Raises:
        SynthesisLockUnavailableError: git could not be invoked.
    """
    resolved = repo_root.resolve()
    try:
        common_dir = git_common_dir(resolved)
    except NotAGitRepositoryError:
        return resolved / NON_GIT_LOCK_PATH
    except GitTopologyUnavailableError as exc:
        raise SynthesisLockUnavailableError(repo_root, exc) from exc
    digest = sha256_digest(os.path.normcase(str(resolved)).encode("utf-8")).removeprefix(_DIGEST_PREFIX)[:_DIGEST_LENGTH]
    return common_dir / LOCK_DIRECTORY / SYNTHESIS_LOCK_SUBDIRECTORY / f"{digest}.lock"


@contextmanager
def synthesis_lock(repo_root: Path, *, timeout_s: float | None = None) -> Iterator[Path]:
    """Hold the run-wide synthesis lock for *repo_root*; yield the lock file path.

    Re-entrant on the same thread. The default wait is read from
    :data:`SYNTHESIS_LOCK_TIMEOUT_S` at call time.

    Raises:
        SynthesisLockHeldError: the lock was not acquired within the wait.
        SynthesisLockUnavailableError: git could not be invoked.
    """
    wait = SYNTHESIS_LOCK_TIMEOUT_S if timeout_s is None else timeout_s
    lock_path = synthesis_lock_path(repo_root)
    try:
        with machine_file_lock(lock_path, blocking=True, timeout_s=wait, reentrant=True):
            yield lock_path
    except LockAcquireTimeout as exc:
        raise SynthesisLockHeldError(lock_path, wait) from exc


def synthesis_lock_unless(read_only: bool, repo_root: Path) -> AbstractContextManager[Path | None]:
    """Return the run-wide lock for a writing run, or a no-op context for a read-only one.

    The single owner of the "read-only runs take no lock" policy shared by ``charter synthesize``
    and ``charter resynthesize`` (#6453, FR-002).
    """
    if read_only:
        return nullcontext()
    return synthesis_lock(repo_root)
