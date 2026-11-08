"""Shared hooks-dir resolution for the policy layer (#5756).

The effective hooks directory of a repository is whatever
``git rev-parse --git-path hooks`` says — honoring ``core.hooksPath`` and a
linked worktree's shared common hooks dir — never a mechanical
``repo_root / ".git" / "hooks"`` join, which is wrong for every layout whose
``.git`` is a file (linked worktree, ``--separate-git-dir``) or whose hooks
live in a configured path.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

__all__ = ["resolve_hooks_dir"]


def _git_out(repo_root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def resolve_hooks_dir(repo_root: Path) -> Path:
    """Resolve the effective hooks dir via ``git rev-parse --git-path hooks``.

    Honors ``core.hooksPath`` (returned verbatim, relative to ``repo_root``,
    when set) and a linked worktree's shared common hooks dir (returned
    already absolute in that case). ``git rev-parse`` prints the path
    relative to the CURRENT directory otherwise, so a relative result is
    joined onto ``repo_root`` (the ``cwd`` this runs with) rather than the
    process's own unrelated working directory.

    Raises:
        subprocess.CalledProcessError: ``repo_root`` is not a git repository.
    """
    hooks_dir = Path(_git_out(repo_root, "rev-parse", "--git-path", "hooks"))
    if hooks_dir.is_absolute():
        return hooks_dir
    return repo_root / hooks_dir
