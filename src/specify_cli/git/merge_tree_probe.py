"""The single ``git merge-tree --write-tree`` availability probe.

``git merge-tree --write-tree`` (the modern, ``.gitattributes``-honoring
merge simulation) only exists from git 2.38. Both the merge/terminus
attribution probes (:mod:`specify_cli.consolidation.git_probes`) and the
destroyed-lane absorption check (:mod:`specify_cli.lanes.lane_tip`) must
fail CLOSED on an older git, so they share ONE implementation of the version
check. It lives here -- a neutral, dependency-free git-plumbing module -- so
``lanes`` does not have to import ``consolidation`` (which would invert the
layering) and ``consolidation`` does not restate a second copy.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from kernel.git.read_cache import Depends, cached_git_read

__all__ = [
    "MERGE_TREE_WRITE_TREE_MIN_VERSION",
    "check_attr_source_available",
    "merge_tree_write_tree_available",
    "remerge_diff_available",
]

#: Oldest git that supports ``git merge-tree --write-tree``.
MERGE_TREE_WRITE_TREE_MIN_VERSION: tuple[int, int] = (2, 38)

#: Oldest git that supports ``git show --remerge-diff`` (#7307).
_REMERGE_DIFF_MIN_VERSION: tuple[int, int] = (2, 36)

#: Oldest git that supports ``git check-attr --source <tree-ish>`` (FR-010).
_CHECK_ATTR_SOURCE_MIN_VERSION: tuple[int, int] = (2, 40)

_GIT_VERSION_PATTERN = re.compile(r"(\d+)\.(\d+)(?:\.(\d+))?")


def merge_tree_write_tree_available(repo_root: Path) -> bool:
    """Return True iff the installed git supports ``git merge-tree --write-tree`` (git>=2.38).

    Probed via ``git --version`` rather than by invoking the flag itself, so a
    caller can gate the (more expensive) merge simulation without paying for a
    doomed invocation on old git. A failing ``git --version``, or output that
    does not contain a recognizable ``X.Y[.Z]`` version, is treated as
    unavailable -- fail-closed: the caller then refuses (or leaves the path
    unattributable) rather than attempting an unsupported flag, with no
    unsound raw-``merge-file`` fallback.
    """
    return _git_at_least(repo_root, MERGE_TREE_WRITE_TREE_MIN_VERSION)


def remerge_diff_available(repo_root: Path) -> bool:
    """Return True iff the installed git supports ``git show --remerge-diff`` (git>=2.36, #7307).

    Same fail-closed probe as :func:`merge_tree_write_tree_available`: an
    unreadable version counts as unavailable, and the caller refuses.
    """
    return _git_at_least(repo_root, _REMERGE_DIFF_MIN_VERSION)


def check_attr_source_available(repo_root: Path) -> bool:
    """Return True iff the installed git supports ``git check-attr --source`` (git>=2.40, FR-010).

    Same fail-closed probe as :func:`merge_tree_write_tree_available`.
    """
    return _git_at_least(repo_root, _CHECK_ATTR_SOURCE_MIN_VERSION)


def _read_git_version(repo_root: Path) -> tuple[int, int] | None:
    """``git --version`` as ``(major, minor)``, or ``None`` when it fails or prints no ``X.Y`` version."""
    result = subprocess.run(["git", "--version"], cwd=str(repo_root), capture_output=True, text=True, check=False)
    if result.returncode != 0:
        return None
    match = _GIT_VERSION_PATTERN.search(result.stdout or "")
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def _git_at_least(repo_root: Path, minimum: tuple[int, int]) -> bool:
    """True iff ``git --version`` reports a version at or above *minimum* (unreadable ⇒ False).

    Inside a run's git read cache scope the version is read once (NFR-001); an unreadable
    version is never stored, so it is read again and still fails closed.
    """
    version = cached_git_read(
        repo_root,
        ("git-version",),
        lambda: _read_git_version(repo_root),
        depends=Depends(),
        store_if=lambda value: value is not None,
    )
    return version is not None and version >= minimum
