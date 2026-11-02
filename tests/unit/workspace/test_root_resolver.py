"""Unit tests for ``specify_cli.workspace.root_resolver`` (WP03/T013, FR-013).

These tests exercise the canonical-root resolver in four scenarios:

* a regular git repo,
* a git worktree (``.git`` is a file),
* a subdirectory inside the worktree, and
* a directory that is not a git repo at all.

They use real ``git worktree add`` so the ``commondir`` parsing path is
covered, not just mocked-out file layouts.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from specify_cli.workspace.root_resolver import (
    WorkspaceRootNotFound,
    _reset_cache,
    canonicalize_feature_dir,
    resolve_canonical_root,
)


pytestmark = [pytest.mark.unit, pytest.mark.git_repo]


@pytest.fixture(autouse=True)
def _clear_cache():
    """Ensure the module-level cache is empty for each test."""
    _reset_cache()
    yield
    _reset_cache()


def _git(cwd: Path, *args: str) -> str:
    """Run a git command, returning stdout. Fails the test on nonzero exit."""
    result = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _init_repo(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    _git(path, "init", "--initial-branch=main")
    _git(path, "config", "user.email", "test@example.com")
    _git(path, "config", "user.name", "Test")
    _git(path, "config", "commit.gpgsign", "false")
    (path / "README.md").write_text("hi\n", encoding="utf-8")
    _git(path, "add", "README.md")
    _git(path, "commit", "-m", "init")
    return path.resolve()


@pytest.mark.git_repo
def test_regular_repo_root(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")

    assert resolve_canonical_root(repo) == repo


@pytest.mark.git_repo
def test_subdirectory_of_regular_repo_walks_up(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")
    sub = repo / "src" / "deep"
    sub.mkdir(parents=True)

    assert resolve_canonical_root(sub) == repo


@pytest.mark.git_repo
def test_worktree_returns_canonical_main_repo(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")
    worktree = tmp_path / "wt-feature"
    _git(repo, "worktree", "add", "-b", "feature", str(worktree))

    resolved = resolve_canonical_root(worktree)

    assert resolved == repo
    assert resolved != worktree.resolve()


@pytest.mark.git_repo
def test_subdirectory_inside_worktree_returns_canonical(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")
    worktree = tmp_path / "wt-deep"
    _git(repo, "worktree", "add", "-b", "deep", str(worktree))

    nested = worktree / "src" / "nested" / "deeper"
    nested.mkdir(parents=True)

    assert resolve_canonical_root(nested) == repo


@pytest.mark.git_repo
def test_coord_worktree_feature_dir_is_not_rewritten_to_primary(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")
    mission_slug = "demo-feature-01ABCDEF"
    primary_feature_dir = repo / "kitty-specs" / mission_slug
    primary_feature_dir.mkdir(parents=True)
    coord_worktree = repo / ".worktrees" / f"{mission_slug}-coord"
    _git(repo, "worktree", "add", "-b", "coord", str(coord_worktree))
    coord_feature_dir = coord_worktree / "kitty-specs" / mission_slug
    coord_feature_dir.mkdir(parents=True)

    assert canonicalize_feature_dir(coord_feature_dir) == coord_feature_dir
    assert canonicalize_feature_dir(coord_feature_dir) != primary_feature_dir


def test_non_git_directory_raises(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A plain directory is not a repo, even when some checkout encloses the temp root.

    This used to wrap ``resolve_canonical_root`` in a monkeypatched copy that refused
    any answer outside ``tmp_path`` — a second, test-only hermeticity mechanism. The
    harness's ``GIT_CEILING_DIRECTORIES`` entry for the run's basetemp (and #7022's
    support for it in the resolver) is the one mechanism now; the local override here is
    the only per-test narrowing left (#7056).
    """
    plain = tmp_path / "no-git"
    plain.mkdir()
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))

    with pytest.raises(WorkspaceRootNotFound) as exc_info:
        resolve_canonical_root(plain)

    assert plain.resolve() == exc_info.value.cwd


@pytest.mark.git_repo
def test_cache_returns_same_object_for_repeated_calls(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")
    first = resolve_canonical_root(repo)
    second = resolve_canonical_root(repo)

    assert first == second == repo
