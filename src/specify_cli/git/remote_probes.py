"""Single canonical tri-state remote-branch-existence primitive (#4979, C-001).

Two remote-branch probes shipped independently before this module existed:
``coordination.surface_resolver._coord_branch_exists`` (the ``refs/remotes/``
fast path only — never consulted the remote itself) and
``cli.commands.mission_type._branch_resolvable`` (a hand-rolled
``git remote`` + ``git ls-remote --heads`` loop, with no ``timeout=``, so an
unreachable/prompting remote could hang the CLI). C-001 forbids a third
parallel probe: :func:`remote_branch_lookup` is the ONE shared primitive both
sites are refactored onto (WP01 T003/T004) — any future remote-branch check
must consume it rather than hand-rolling another ``git remote`` /
``git ls-remote`` loop.

Discriminates three ``git ls-remote --heads`` outcomes across every
configured remote:

* :attr:`RemoteLookup.HIT` — at least one remote lists the branch.
* :attr:`RemoteLookup.CLEAN_MISS` — every remote answered (exit 0) with no
  match — a reachable "the branch really is not there".
* :attr:`RemoteLookup.ERROR` — at least one remote errored, timed out, or
  otherwise could not be asked cleanly — the network condition is
  inconclusive, so the caller must fail closed (NFR-002); a MISS from one
  remote never overrides an ERROR from another.
* :attr:`RemoteLookup.NO_REMOTE` — zero remotes are configured at all: there
  is no remote authority to consult, so the caller retains local-only
  authority instead of treating this as either HIT or CLEAN_MISS.

Fails closed toward :attr:`RemoteLookup.ERROR` on any git-unreadable
condition (unparseable ``git remote`` output never happens in practice, but
an ``OSError`` launching git, a non-zero ``git remote`` exit, a
``subprocess.TimeoutExpired``, or a non-zero ``ls-remote`` exit all resolve
here). ``GIT_TERMINAL_PROMPT=0`` and SSH ``BatchMode=yes`` prevent a
credential prompt from ever blocking the CLI (NFR-002); a bounded
``timeout=`` prevents an unreachable remote from hanging it.

The lookup is memoized per-process, keyed ``(repo_root, branch)`` (NFR-001):
a single-branch/CI coordination checkout never materializes the coord
worktree, so an unmemoized probe would re-fire the network arm on every coord
read within one CLI invocation. Call :func:`reset_remote_branch_lookup_cache`
between independent probes in the same process (tests only — production never
needs to invalidate the cache within one invocation).
"""

from __future__ import annotations

import enum
import os
import subprocess
from pathlib import Path

__all__ = [
    "RemoteLookup",
    "remote_branch_lookup",
    "reset_remote_branch_lookup_cache",
]

_LS_REMOTE_TIMEOUT_SECONDS = 5.0

# GIT_TERMINAL_PROMPT=0 refuses any interactive credential prompt outright;
# the SSH BatchMode mirrors that refusal for the ssh(1) transport, which does
# not honor GIT_TERMINAL_PROMPT on its own (NFR-002).
_NO_PROMPT_ENV: dict[str, str] = {
    "GIT_TERMINAL_PROMPT": "0",
    "GIT_SSH_COMMAND": "ssh -o BatchMode=yes",
}


class RemoteLookup(enum.Enum):
    """Tri-state (+ no-remote) outcome of a remote branch-existence lookup."""

    HIT = "hit"
    CLEAN_MISS = "clean_miss"
    ERROR = "error"
    NO_REMOTE = "no_remote"


_CACHE: dict[tuple[str, str], RemoteLookup] = {}


def reset_remote_branch_lookup_cache() -> None:
    """Clear the per-process memoization cache (test isolation only)."""
    _CACHE.clear()


def _configured_remotes(repo_root: Path) -> list[str] | None:
    """Return configured remote names, or ``None`` on any read failure."""
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "remote"],
            check=False,
            capture_output=True,
            text=True,
            timeout=_LS_REMOTE_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _ls_remote_heads(repo_root: Path, remote: str, branch: str) -> bool | None:
    """Probe one remote for *branch*.

    Returns ``True`` on a match, ``False`` on a clean (exit 0, empty) miss,
    and ``None`` on any error/timeout — the caller treats ``None`` as
    fail-closed ERROR, never as a vote toward absence.
    """
    env = {**os.environ, **_NO_PROMPT_ENV}
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "ls-remote", "--heads", remote, branch],
            check=False,
            capture_output=True,
            text=True,
            timeout=_LS_REMOTE_TIMEOUT_SECONDS,
            env=env,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    return bool(result.stdout.strip())


def _lookup_uncached(repo_root: Path, branch: str) -> RemoteLookup:
    remotes = _configured_remotes(repo_root)
    if remotes is None:
        return RemoteLookup.ERROR
    if not remotes:
        return RemoteLookup.NO_REMOTE

    saw_error = False
    for remote in remotes:
        outcome = _ls_remote_heads(repo_root, remote, branch)
        if outcome is None:
            saw_error = True
            continue
        if outcome:
            return RemoteLookup.HIT
    return RemoteLookup.ERROR if saw_error else RemoteLookup.CLEAN_MISS


def remote_branch_lookup(repo_root: Path, branch: str) -> RemoteLookup:
    """Return the tri-state (+ no-remote) presence of *branch* across every
    configured remote of *repo_root*.

    Iterates every remote returned by ``git remote`` (never only ``origin`` —
    the branch may live on a non-default remote) and runs
    ``git ls-remote --heads <remote> <branch>`` against each, bounded by a
    ~5s ``timeout=`` with prompting disabled (NFR-002). A single ``HIT``
    short-circuits; otherwise an ``ERROR`` from any remote wins over a
    ``CLEAN_MISS`` from another (never fabricate absence from a partial
    answer). Memoized per-process by ``(repo_root, branch)`` (NFR-001).
    """
    key = (str(repo_root), branch)
    cached = _CACHE.get(key)
    if cached is not None:
        return cached
    outcome = _lookup_uncached(repo_root, branch)
    _CACHE[key] = outcome
    return outcome
