"""The one remedy for a branch that exists only on a remote (#5287).

A fresh clone, a CI checkout or a pruned local branch can leave a Mission's
coordination branch (or its Mission topic branch) with no local head while a
remote still holds it. Every command that meets that state prints the same
ordered steps, composed here:

1. ``git -C <root> fetch <remote> <branch>:refs/remotes/<remote>/<branch>``
   (omitted when this clone already holds that remote-tracking ref; the
   explicit destination makes it work in a single-branch or shallow clone);
2. ``git -C <root> branch <branch> refs/remotes/<remote>/<branch>``;
3. a caller-supplied follow-up (the coordination doctor, or "re-run").

The remote is the one that owns the branch, resolved from local configuration
(:func:`kernel.git.remote.resolve_remote`), never a hard-coded ``origin``.
Nothing here contacts a remote (ADR 2026-10-06-3): it reads git config and
local refs only.

This module lives in ``mission_runtime`` so both ``mission_runtime`` and
``specify_cli`` can use it; it imports ``kernel`` and the standard library only.
"""

from __future__ import annotations

import shlex
from dataclasses import dataclass
from pathlib import Path

from kernel.git.remote import configured_remotes, resolve_remote, tracking_ref
from kernel.git.runner import GitCommandError, run_git

__all__ = [
    "coordination_doctor_command",
    "remote_only_branch",
    "remote_only_steps",
]

#: Not ``<remote>``: a pasted ``<`` is a shell redirect.
_REMOTE_PLACEHOLDER = "REMOTE"


@dataclass(frozen=True)
class RemoteOnlyBranch:
    """What this clone knows, locally, about a branch with no local head.

    ``remote`` is the remote judged to own the branch, or ``None`` when local
    configuration cannot tell (several remotes, none named ``origin``, none
    configured for the branch). ``tracking_ref_present`` says this clone already
    holds ``refs/remotes/<remote>/<branch>``, so no fetch is needed; it implies
    ``remote`` is set. ``remotes_readable`` is ``False`` when git could not read
    this checkout's configuration at all, which is not the same as "no remote".
    """

    branch: str
    remote: str | None
    tracking_ref_present: bool
    remotes: tuple[str, ...] = ()
    remotes_readable: bool = True

    def __post_init__(self) -> None:
        if self.tracking_ref_present and self.remote is None:
            raise ValueError("a present tracking ref names its remote")


def _has_tracking_ref(repo_root: Path, remote: str, branch: str) -> bool:
    """True when ``refs/remotes/<remote>/<branch>`` resolves to a commit (local read; unreadable answers False)."""
    try:
        result = run_git(repo_root, "rev-parse", "--verify", "--quiet", "--end-of-options", f"{tracking_ref(remote, branch)}^{{commit}}", check=False)
    except GitCommandError:
        return False
    return result.returncode == 0


def remote_only_branch(repo_root: Path, branch: str) -> RemoteOnlyBranch:
    """Resolve the local facts the remedy needs for *branch* (no network).

    The owning remote is :func:`~kernel.git.remote.resolve_remote`'s answer. When
    that remote holds no tracking ref for the branch but exactly one configured
    remote does, the clone has already fetched the branch from that remote, so
    it is the one named (and no fetch is needed).
    """
    try:
        remotes = tuple(configured_remotes(repo_root))
        remote = resolve_remote(repo_root, branch)
    except GitCommandError:
        # git could not run here (e.g. the root does not exist): nothing is known locally.
        return RemoteOnlyBranch(branch=branch, remote=None, tracking_ref_present=False, remotes_readable=False)
    if remote is not None and remote not in remotes:
        # ``branch.<b>.remote`` may hold a URL: there is no ``refs/remotes/<url>/<b>``.
        # Fall back to the same default ``resolve_remote`` applies without that key.
        remote = _default_remote(remotes)
    if remote is not None and _has_tracking_ref(repo_root, remote, branch):
        return RemoteOnlyBranch(branch=branch, remote=remote, tracking_ref_present=True, remotes=remotes)
    holders = [name for name in remotes if name != remote and _has_tracking_ref(repo_root, name, branch)]
    if len(holders) == 1:
        return RemoteOnlyBranch(branch=branch, remote=holders[0], tracking_ref_present=True, remotes=remotes)
    return RemoteOnlyBranch(branch=branch, remote=remote, tracking_ref_present=False, remotes=remotes)


def _default_remote(remotes: tuple[str, ...]) -> str | None:
    """The only configured remote, else ``origin`` when configured, else ``None``."""
    if len(remotes) == 1:
        return remotes[0]
    return "origin" if "origin" in remotes else None


def coordination_doctor_command(mission_slug: str) -> str:
    """The follow-up step that materializes a Mission's coordination worktree once its branch is local."""
    return f"`spec-kitty doctor coordination --mission {mission_slug} --fix`"


def _remote_note(facts: RemoteOnlyBranch) -> str:
    """Say what local configuration cannot settle about the remote, or nothing."""
    if facts.remote is None:
        if not facts.remotes_readable:
            return f" (git could not read this checkout's remotes: {_REMOTE_PLACEHOLDER} is the remote that holds the branch)"
        if facts.remotes:
            return f" ({_REMOTE_PLACEHOLDER} is the remote that holds the branch, one of: {', '.join(facts.remotes)})"
        return " (no remote is configured: add one with `git remote add NAME URL`)"
    others = [name for name in facts.remotes if name != facts.remote]
    if facts.tracking_ref_present or not others:
        return ""
    # Several remotes and no tracking ref anywhere: the default remote is a
    # guess no local read can confirm, and asking the remotes is a network call.
    return f" (if {facts.remote} does not hold the branch, use the remote that does: {', '.join(others)})"


def remote_only_steps(facts: RemoteOnlyBranch, repo_root: Path, follow_up: str) -> str:
    """The ordered recovery steps for a remote-only branch (pure; no git).

    *follow_up* is the last step, used verbatim and phrased so it reads after
    "then" (a command in backticks, or a short clause such as "re-run the
    command").
    """
    remote = facts.remote or _REMOTE_PLACEHOLDER
    branch = facts.branch
    root = shlex.quote(str(repo_root))
    steps: list[str] = []
    if not facts.tracking_ref_present:
        # An explicit destination: a single-branch (or shallow) clone's fetch
        # refspec does not cover the branch, so a bare `fetch <remote> <b>` would
        # write only FETCH_HEAD and the next step could not name <remote>/<b>.
        steps.append(f"`git -C {root} fetch {remote} {branch}:refs/remotes/{remote}/{branch}`")
    # The full remote-tracking ref, so a local branch or tag named <remote>/<b> cannot shadow it.
    steps.append(f"`git -C {root} branch {branch} refs/remotes/{remote}/{branch}`")
    steps.append(follow_up)
    return f"Run in order: {', then '.join(steps)}.{_remote_note(facts)}"
