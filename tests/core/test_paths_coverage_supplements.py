"""Coverage supplements for ``src/specify_cli/core/paths.py`` edges introduced
by WP05 (mission ``review-merge-gate-hardening-3-2-x-01KRC57C``).

The main scenario-style tests live in
``tests/status/test_status_read_worktree_resolution.py``. This file adds
narrow unit tests for the edge branches that scenario tests don't reach:

- ``get_status_read_root``: explicit-start argument, fallback branch when no
  ``.git`` marker is found anywhere.

These tests target *behavior*, not source line numbers, so refactors that
preserve the contract keep them green.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.core.paths import get_status_read_root


pytestmark = [pytest.mark.unit, pytest.mark.fast]

def _make_main_repo(root: Path) -> Path:
    """Mark *root* as a main-repo by creating a ``.git`` directory."""
    root.mkdir(parents=True, exist_ok=True)
    (root / ".git").mkdir()
    return root


def _make_worktree(root: Path, gitdir_target: Path) -> Path:
    """Mark *root* as a worktree by creating a ``.git`` file whose content
    points at *gitdir_target* (which should look like ``.../worktrees/<name>``).
    """
    root.mkdir(parents=True, exist_ok=True)
    (root / ".git").write_text(f"gitdir: {gitdir_target}\n", encoding="utf-8")
    return root


# ---------------------------------------------------------------------------
# get_status_read_root
# ---------------------------------------------------------------------------


def test_get_status_read_root_main_repo(tmp_path: Path) -> None:
    """From the main repo root, returns that root."""
    _make_main_repo(tmp_path)
    assert get_status_read_root(tmp_path).resolve() == tmp_path.resolve()


def test_get_status_read_root_from_worktree_returns_worktree(tmp_path: Path) -> None:
    """From inside a worktree, returns the worktree's own root (not main)."""
    main = tmp_path / "main"
    _make_main_repo(main)
    worktree_gitdir = main / ".git" / "worktrees" / "feat-x"
    worktree_gitdir.mkdir(parents=True)
    wt = tmp_path / "worktrees" / "feat-x"
    wt.mkdir(parents=True)
    _make_worktree(wt, worktree_gitdir)

    assert get_status_read_root(wt).resolve() == wt.resolve()


def test_get_status_read_root_does_not_crash_with_no_local_marker(
    tmp_path: Path,
) -> None:
    """When no ``.git`` marker is found in the immediate test sandbox, the
    function must complete normally — either returning a parent directory
    that has a ``.git`` marker (the upward walk found one) or falling through
    to ``get_main_repo_root``'s final ``current_path.resolve()`` clause.

    The exact result depends on the host filesystem (e.g. dev machines may
    have a stray ``.git`` marker somewhere under the system temp directory),
    so we only assert the contract: ``Path`` return, no exception. The
    malformed-marker test below covers the semantically tighter branch.
    """
    result = get_status_read_root(tmp_path)
    assert isinstance(result, Path)


def test_get_status_read_root_handles_malformed_gitfile_via_break(
    tmp_path: Path,
) -> None:
    """``.git`` file with garbage content at the immediate cwd: the walker
    detects the file, fails to parse the gitdir pointer, and ``break``s.
    The function then falls through to ``get_main_repo_root(cwd)``.

    ``get_main_repo_root`` ALSO sees the malformed ``.git`` file at the cwd
    and falls through to its final ``current_path.resolve()``. So the
    function returns the resolved cwd — environment-independent because
    the marker we placed at cwd takes precedence over any ancestor marker.
    """
    (tmp_path / ".git").write_text("not a gitdir pointer\n", encoding="utf-8")
    result = get_status_read_root(tmp_path)
    assert result == tmp_path.resolve()
