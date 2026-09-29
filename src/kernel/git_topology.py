"""The single git-topology probe: ``git rev-parse`` common-dir / toplevel.

This module is the ONE authority for the "where is this checkout's git
common-dir / working-tree toplevel?" probe (mission
``write-path-integrity-01KZZD69`` WP01, #3373). Before it, four call sites
re-implemented the same ``git rev-parse`` shell-out with subtly different
path-canonicalization: the charter canonical-root resolver
(``charter.resolution``), the checkout-ownership classifier
(``core.checkout_ownership``), the safe-commit linkage comparator
(``git.commit_helpers``), and the workspace toplevel assertion
(``workspace.context``). Consolidating them behind one primitive gives the
whole write path a single, drift-free symlink-canonicalization contract.

Canonicalization contract (the single ``.resolve()`` rule)
----------------------------------------------------------

``git rev-parse --git-common-dir`` prints a path that is CWD-relative in the
common case (``.git`` / ``../../.git``) and absolute only for linked
worktrees. Both this primitive's outputs are resolved exactly once against the
probe directory: ``(cwd / raw).resolve()``. Because ``Path("/x") / "/abs"``
collapses to ``/abs``, that single expression correctly handles both the
relative and absolute git outputs, and ``.resolve()`` canonicalizes symlinks
(e.g. macOS ``/var`` -> ``/private/var``) so a comparison of two probe results
never yields a spurious mismatch.

Error classification (kept distinguishable so each caller can adapt)
--------------------------------------------------------------------

The probe raises one of two typed errors so a consumer can map each to its own
contract without re-classifying:

* :class:`NotAGitRepositoryError` — git reported "not a git repository", or the
  probed path is inside a ``.git`` directory itself (``git_common_dir`` only).
* :class:`GitTopologyUnavailableError` — git could not be invoked (binary
  missing) or ``rev-parse`` failed for any other reason (corrupt ``.git``,
  permission denied, empty output).

Both derive from :class:`GitTopologyError`, so a consumer that treats every
probe failure alike can catch the base class.

Caching
-------

Every probe is ``functools.lru_cache``-amortized (``maxsize=256``, mirroring
the charter resolver's historical cache) so the charter hot path (~20 callers)
pays at most one subprocess per distinct checkout and probe. The
``core.worktree`` probe (:func:`git_configured_worktree`) is only consulted for
common dirs that do not sit at ``<working tree>/.git`` (submodules). Exceptions are never cached
(``lru_cache`` re-runs after a raise), so a not-a-repo path that later becomes a
repo resolves correctly on the next call.
"""
from __future__ import annotations

import subprocess
from functools import lru_cache
from pathlib import Path

_NOT_A_REPO_MARKER = "not a git repository"


class GitTopologyError(RuntimeError):
    """Base class for git-topology probe failures.

    Consumers that treat every probe failure identically (e.g. the safe-commit
    linkage gate, which returns ``False`` on any failure) catch this base; those
    that must distinguish "not a repo" from "git unavailable" catch the two
    subclasses.
    """


class NotAGitRepositoryError(GitTopologyError):
    """The probed path is not inside a git repository.

    Also raised by :func:`git_common_dir` when the path resolves inside a
    ``.git`` directory, which is not a valid project root.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        super().__init__(f"{path!r} is not inside a git repository.")


class GitTopologyUnavailableError(GitTopologyError):
    """``git rev-parse`` could not be invoked, or failed for a non-repo reason.

    Covers a missing/unexecutable git binary (``FileNotFoundError`` from
    :func:`subprocess.run`) and any non-"not a git repository" ``rev-parse``
    failure (corrupt ``.git``, permission denied, empty output).
    """

    def __init__(self, path: Path, detail: str) -> None:
        self.path = path
        self.detail = detail
        super().__init__(f"git topology probe failed for {path!r}: {detail}")


def _probe_dir(resolved: Path) -> Path:
    """Normalise a file input to its parent directory before invoking git."""
    return resolved.parent if resolved.is_file() else resolved


def _run_rev_parse(cwd: Path, flag: str, original: Path) -> subprocess.CompletedProcess[str]:
    """Invoke ``git rev-parse <flag>`` once in ``cwd``.

    Raises :class:`GitTopologyUnavailableError` when the git binary cannot be
    executed at all (missing binary or an unreadable working directory).
    """
    try:
        return subprocess.run(
            ["git", "rev-parse", flag],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except FileNotFoundError as exc:
        raise GitTopologyUnavailableError(original, "git binary not found on PATH") from exc


@lru_cache(maxsize=256)
def git_common_dir(path: Path) -> Path:
    """Return the canonical ``--git-common-dir`` for ``path`` (resolved once).

    ``path`` may be a file or directory, absolute or relative; a file input is
    normalised to its parent directory before the probe. The returned path is
    the shared repository ``.git`` (common) directory, resolved against the
    probe directory and canonicalized (symlinks collapsed).

    Raises:
        NotAGitRepositoryError: ``path`` is not inside a git repository, or it
            resolves inside a ``.git`` directory (not a valid project root).
        GitTopologyUnavailableError: git could not be invoked, or ``rev-parse``
            failed for any other reason.
    """
    resolved = path.resolve()
    cwd = _probe_dir(resolved)
    result = _run_rev_parse(cwd, "--git-common-dir", resolved)
    if result.returncode != 0:
        if _NOT_A_REPO_MARKER in (result.stderr or "").lower():
            raise NotAGitRepositoryError(resolved)
        raise GitTopologyUnavailableError(resolved, (result.stderr or "").strip())
    raw = result.stdout.strip()
    common_dir = (cwd / raw).resolve()
    # ``.git``-interior detection: a path that IS the common dir, or lives under
    # it, is not a valid project root.
    if resolved == common_dir or common_dir in resolved.parents:
        raise NotAGitRepositoryError(resolved)
    return common_dir


@lru_cache(maxsize=256)
def git_toplevel(path: Path) -> Path:
    """Return the canonical ``--show-toplevel`` for ``path`` (resolved once).

    ``path`` may be a file or directory; a file input is normalised to its
    parent directory before the probe. The returned path is the working-tree
    root that owns ``path``, resolved and canonicalized.

    Raises:
        NotAGitRepositoryError: ``path`` is not inside a git repository.
        GitTopologyUnavailableError: git could not be invoked, or ``rev-parse``
            failed / produced no output for any other reason.
    """
    resolved = path.resolve()
    cwd = _probe_dir(resolved)
    result = _run_rev_parse(cwd, "--show-toplevel", resolved)
    raw = result.stdout.strip()
    if result.returncode != 0 or not raw:
        stderr = (result.stderr or "").lower()
        if _NOT_A_REPO_MARKER in stderr:
            raise NotAGitRepositoryError(resolved)
        detail = (result.stderr or "").strip() or f"exit {result.returncode}"
        raise GitTopologyUnavailableError(resolved, detail)
    return (cwd / raw).resolve()


@lru_cache(maxsize=256)
def git_configured_worktree(common_dir: Path) -> Path | None:
    """Return the ``core.worktree`` configured in ``common_dir``, or ``None``.

    ``common_dir`` is a git common directory, as :func:`git_common_dir`
    returns it. Git records ``core.worktree`` when the git dir does not sit at
    ``<working tree>/.git``: most importantly for a submodule, whose git dir is
    absorbed into ``<super>/.git/modules/<name>``. A relative value is
    resolved against ``common_dir`` (git's own rule), then canonicalized.

    Raises:
        GitTopologyUnavailableError: git could not be invoked, or
            ``git config`` failed for a reason other than "key not set"
            (for example an unparsable config file).
    """
    resolved = common_dir.resolve()
    try:
        result = subprocess.run(
            ["git", "--git-dir", str(resolved), "config", "--get", "core.worktree"],
            cwd=str(resolved),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except FileNotFoundError as exc:
        raise GitTopologyUnavailableError(resolved, "git binary not found on PATH") from exc
    raw = result.stdout.strip()
    # ``git config --get`` exits 1 (with no output) when the key is unset.
    if result.returncode == 1 and not raw:
        return None
    if result.returncode != 0 or not raw:
        detail = (result.stderr or "").strip() or f"exit {result.returncode}"
        raise GitTopologyUnavailableError(resolved, detail)
    return (resolved / raw).resolve()


def clear_caches() -> None:
    """Reset every probe cache.

    Exposed for tests (and the charter resolver's public ``cache_clear``
    surface) that mutate the on-disk git layout mid-run and need the next probe
    to re-shell-out rather than return a stale cached path.
    """
    git_common_dir.cache_clear()
    git_toplevel.cache_clear()
    git_configured_worktree.cache_clear()


__all__ = [
    "GitTopologyError",
    "GitTopologyUnavailableError",
    "NotAGitRepositoryError",
    "clear_caches",
    "git_common_dir",
    "git_configured_worktree",
    "git_toplevel",
]
