"""Regression tests for the .worktrees/ path-policy rejection gates.

FR-005 / Issue #1887: ``feature_dir_file_paths`` in ``implement.py`` was
computing paths relative to the wrong anchor (primary checkout root), causing
``.worktrees/<coord>/…`` paths to be staged and committed to ``origin/main``.

Three defensive layers are tested here:
1. ``feature_dir_file_paths`` raises ``SafeCommitPathPolicyError`` when
   ``feature_dir`` resolves under ``.worktrees/`` relative to ``repo_root``.
2. ``safe_commit`` raises ``SafeCommitPathPolicyError`` before staging when any
   normalized path starts with ``.worktrees/``.
3. Git index stays clean — ``git ls-files .worktrees/`` returns empty after
   a rejected call.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from specify_cli.coordination.planning_commit import feature_dir_file_paths
from specify_cli.git.commit_helpers import SafeCommitPathPolicyError, safe_commit
from mission_runtime import CommitTarget

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    )


def _init_repo(repo: Path, branch: str = "kitty/mission-test-01ABCDEF") -> None:
    """Initialise a minimal git repo on ``branch`` with one commit."""
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-q", "-b", branch)
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test User")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "seed.txt").write_text("seed\n", encoding="utf-8")
    _git(repo, "add", "seed.txt")
    _git(repo, "commit", "-q", "-m", "initial commit")


# ---------------------------------------------------------------------------
# T010-a: feature_dir_file_paths raises SafeCommitPathPolicyError
# ---------------------------------------------------------------------------


def test_feature_dir_file_paths_rejects_worktrees_dir(tmp_path: Path) -> None:
    """feature_dir_file_paths raises SafeCommitPathPolicyError when feature_dir
    resolves under .worktrees/ relative to repo_root."""
    repo_root = tmp_path / "repo"
    _init_repo(repo_root)

    # Simulate a coordination worktree checkout under .worktrees/
    coord_dir = repo_root / ".worktrees" / "test-coord-01ABCDEF"
    coord_dir.mkdir(parents=True)
    dummy_file = coord_dir / "kitty-specs" / "test-mission" / "meta.json"
    dummy_file.parent.mkdir(parents=True)
    dummy_file.write_text('{"mission_id": "01ABCDEF"}', encoding="utf-8")

    with pytest.raises(SafeCommitPathPolicyError) as exc_info:
        feature_dir_file_paths(repo_root, coord_dir)

    assert ".worktrees/" in exc_info.value.offending_path
    assert "coordination worktree" in str(exc_info.value)


def test_feature_dir_file_paths_allows_kitty_specs(tmp_path: Path) -> None:
    """feature_dir_file_paths succeeds for a normal kitty-specs directory."""
    repo_root = tmp_path / "repo"
    _init_repo(repo_root)

    feature_dir = repo_root / "kitty-specs" / "test-mission"
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text('{"mission_id": "01ABCDEF"}', encoding="utf-8")

    paths = feature_dir_file_paths(repo_root, feature_dir)
    assert any("kitty-specs" in p for p in paths)
    assert all(".worktrees" not in p for p in paths)


# ---------------------------------------------------------------------------
# T010-b: safe_commit path policy check fires before git add
# ---------------------------------------------------------------------------


def test_safe_commit_rejects_worktrees_path(tmp_path: Path) -> None:
    """safe_commit raises SafeCommitPathPolicyError for a .worktrees/ path,
    and the git index remains clean (no .worktrees/ paths staged)."""
    repo_root = tmp_path / "repo"
    branch = "kitty/mission-test-01ABCDEF"
    _init_repo(repo_root, branch)

    # Create a file that looks like it is in .worktrees/
    worktrees_dir = repo_root / ".worktrees" / "some-coord"
    worktrees_dir.mkdir(parents=True)
    bad_file = worktrees_dir / "status.events.jsonl"
    bad_file.write_text("{}\n", encoding="utf-8")

    target = CommitTarget(ref=branch)

    with pytest.raises(SafeCommitPathPolicyError) as exc_info:
        safe_commit(
            repo_root=repo_root,
            worktree_root=repo_root,
            target=target,
            message="should not commit",
            paths=(bad_file,),
        )

    assert ".worktrees" in exc_info.value.offending_path

    # Verify the git index has no .worktrees/ paths
    result = subprocess.run(
        ["git", "ls-files", ".worktrees/"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    tracked = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    assert tracked == [], (
        f"git index was mutated despite SafeCommitPathPolicyError: {tracked!r}"
    )


def test_safe_commit_rejects_worktrees_path_in_primary_bundle(tmp_path: Path) -> None:
    """A PRIMARY safe_commit bundle rejects upstream #3784's mixed shape.

    ``tasks.md`` classifies as a PRIMARY artifact, but a coordination-worktree
    source path must not survive into a bundle committed from the primary
    checkout. Pair it with a genuine primary WP file so the regression covers
    the upstream mixed-bundle failure, not only a solo bad path.
    """
    repo_root = tmp_path / "repo"
    branch = "kitty/mission-test-01ABCDEF"
    _init_repo(repo_root, branch)

    primary_file = repo_root / "kitty-specs" / "test-mission" / "tasks" / "WP01-example.md"
    primary_file.parent.mkdir(parents=True)
    primary_file.write_text("# WP01\n", encoding="utf-8")

    worktree_tasks_file = (
        repo_root
        / ".worktrees"
        / "test-mission-coord"
        / "kitty-specs"
        / "test-mission"
        / "tasks.md"
    )
    worktree_tasks_file.parent.mkdir(parents=True)
    worktree_tasks_file.write_text("# Tasks\n", encoding="utf-8")

    target = CommitTarget(ref=branch)

    with pytest.raises(SafeCommitPathPolicyError) as exc_info:
        safe_commit(
            repo_root=repo_root,
            worktree_root=repo_root,
            target=target,
            message="should not commit",
            paths=(primary_file, worktree_tasks_file),
        )

    assert exc_info.value.offending_path == ".worktrees/test-mission-coord/kitty-specs/test-mission/tasks.md"

    staged = _git(repo_root, "diff", "--cached", "--name-only").stdout.splitlines()
    assert staged == [], f"git index was mutated despite SafeCommitPathPolicyError: {staged!r}"
    tracked = _git(repo_root, "ls-files", ".worktrees/").stdout.splitlines()
    assert tracked == [], f"a .worktrees path reached the git index: {tracked!r}"


def test_safe_commit_allows_normal_path(tmp_path: Path) -> None:
    """safe_commit succeeds for a normal (non-.worktrees/) path."""
    repo_root = tmp_path / "repo"
    branch = "kitty/mission-test-01ABCDEF"
    _init_repo(repo_root, branch)

    normal_file = repo_root / "kitty-specs" / "test" / "meta.json"
    normal_file.parent.mkdir(parents=True)
    normal_file.write_text('{"mission_id": "01ABCDEF"}', encoding="utf-8")

    target = CommitTarget(ref=branch)

    result = safe_commit(
        repo_root=repo_root,
        worktree_root=repo_root,
        target=target,
        message="test: add meta.json",
        paths=(normal_file,),
    )
    assert result.sha is not None
