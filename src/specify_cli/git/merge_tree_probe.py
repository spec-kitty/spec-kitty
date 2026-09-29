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

__all__ = ["MERGE_TREE_WRITE_TREE_MIN_VERSION", "merge_tree_write_tree_available"]

#: Oldest git that supports ``git merge-tree --write-tree``.
MERGE_TREE_WRITE_TREE_MIN_VERSION: tuple[int, int] = (2, 38)

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
    result = subprocess.run(["git", "--version"], cwd=str(repo_root), capture_output=True, text=True, check=False)
    if result.returncode != 0:
        return False
    match = _GIT_VERSION_PATTERN.search(result.stdout or "")
    if not match:
        return False
    return (int(match.group(1)), int(match.group(2))) >= MERGE_TREE_WRITE_TREE_MIN_VERSION
