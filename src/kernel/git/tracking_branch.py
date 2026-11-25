"""Local branches made from the owning remote's tracking ref (#5936, #7806).

A teammate's clone (``git clone`` / ``git pull``) carries a pushed branch only as
``refs/remotes/<remote>/<branch>``. That ref is the branch's shared history, so a
local branch started from it never forks from the primary branch. This module
names the owning remote's tracking ref and creates the local branch from it, with
``--track``, for every caller (the coordination branch, a lane branch, a lane's
base lookup), so the "which remote owns it" rule lives in one place.

Refs only: it reads local config and refs and writes one local branch. It never
contacts a remote, which is why it is not in :mod:`kernel.git.remote` (the owner
of every remote read). It knows refs, never Missions or lanes (C-001).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

from kernel.git.remote import resolve_remote, tracking_ref
from kernel.git.runner import GitCommandError, run_git

__all__ = [
    "ensure_local_tracking_branch",
    "is_local_head",
    "owning_tracking_ref",
]

logger = logging.getLogger(__name__)

#: ``(repo_root, branch) -> remote name or None``: who owns a branch.
RemoteResolver = Callable[[Path, str], "str | None"]
#: ``(repo_root, branch) -> tracking ref or None``: where a missing branch is created from.
StartRefResolver = Callable[[Path, str], "str | None"]
#: ``(repo_root, branch) -> bool``: whether the branch is already a local head.
LocalHeadProbe = Callable[[Path, str], bool]


def is_local_head(repo_root: Path, branch: str) -> bool:
    """Return whether *branch* is a local head (``refs/heads/<branch>``).

    Fails closed: a git that cannot run, or a foreign context, reads as ``False``
    (no local head proven).
    """
    try:
        probe = run_git(repo_root, "rev-parse", "--verify", "--quiet", "--end-of-options", f"refs/heads/{branch}", check=False)
    except GitCommandError:  # git could not run at all
        return False
    return probe.returncode == 0


def owning_tracking_ref(
    repo_root: Path,
    branch: str,
    *,
    fallback_remote: str | None = None,
    remote_resolver: RemoteResolver = resolve_remote,
) -> str | None:
    """Return the owning remote's tracking ref for *branch* when this clone holds a commit there.

    The remote is :func:`kernel.git.remote.resolve_remote` (``branch.<b>.remote``,
    then the only configured remote, then ``origin``), never a scan of every
    remote, so two remotes with different tips can never pick one silently.
    *fallback_remote* is used only when no owner resolves (``None``, the default,
    keeps an ambiguous owner unresolved). Returns ``None`` when no remote applies,
    the owner cannot be read, or ``refs/remotes/<remote>/<branch>`` holds no commit
    (never fetched, pruned). Local reads only. *remote_resolver* is the owner rule
    (a caller passes its own binding of :func:`resolve_remote` so it stays its seam).
    """
    try:
        remote = remote_resolver(repo_root, branch) or fallback_remote
    except (GitCommandError, OSError):
        return None
    if remote is None:
        return None
    ref = tracking_ref(remote, branch)
    try:
        probe = run_git(repo_root, "rev-parse", "--verify", "--quiet", "--end-of-options", f"{ref}^{{commit}}", check=False)
    except GitCommandError:  # git could not run at all
        return None
    return ref if probe.returncode == 0 else None


def ensure_local_tracking_branch(
    repo_root: Path,
    branch: str,
    *,
    start_ref: StartRefResolver = owning_tracking_ref,
    local_head: LocalHeadProbe = is_local_head,
) -> bool:
    """Make *branch* a local head, created from its owning remote's tracking ref with ``--track``.

    Returns ``True`` when *branch* is a local head afterwards (it already was, it
    was created here, or a concurrent process created it). Returns ``False`` and
    writes nothing when this clone holds no tracking ref for it
    (:func:`owning_tracking_ref`): nothing local proves the branch's content, so
    the caller keeps refusing. ``--track`` sets the upstream even when
    ``branch.autoSetupMerge`` is off. *start_ref* and *local_head* default to
    :func:`owning_tracking_ref` and :func:`is_local_head`; a caller with its own
    named wrappers of those two passes them so they stay its seams.

    Write-side only: a read path must never call this.
    """
    if local_head(repo_root, branch):
        return True
    start = start_ref(repo_root, branch)
    if start is None:
        return False
    try:
        # ``--end-of-options``: the branch name comes from pushed metadata, so it is never an option.
        created = run_git(repo_root, "branch", "--track", "--end-of-options", branch, start, check=False)
    except GitCommandError:  # git could not run at all
        return False
    if created.returncode != 0:
        # A concurrent CLI process may have created it between the probe and here.
        logger.debug("git branch --track %s %s failed: %s", branch, start, created.stderr.decode("utf-8", "replace").strip())
        return local_head(repo_root, branch)
    logger.info("created local branch %r from %r as last fetched", branch, start)
    return True
