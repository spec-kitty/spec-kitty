"""Unit tests for ``CoordinationWorkspace``.

These cover the FR-024 / FR-018 lifecycle contract:

* :meth:`CoordinationWorkspace.resolve` creates the worktree on first
  call and is idempotent on subsequent calls.
* A mismatched HEAD raises :class:`CoordinationWorkspaceBranchMismatch`
  with the stable ``error_code = "COORDINATION_WORKTREE_BRANCH_MISMATCH"``.
* :meth:`CoordinationWorkspace.teardown` is idempotent (safe to call on
  an absent worktree).
* :meth:`CoordinationWorkspace.is_present` reflects on-disk state.
"""

from __future__ import annotations

import subprocess
import shutil
from pathlib import Path

import pytest

from specify_cli.coordination import (
    CoordinationWorkspace,
    CoordinationWorkspaceBranchMismatch,
)

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

MISSION_SLUG = "demo-feature"
MID8 = "01J6XW9K"
COORD_BRANCH = f"kitty/mission-{MISSION_SLUG}-{MID8}"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def _worktree_list(repo: Path) -> str:
    return subprocess.check_output(
        ["git", "-C", str(repo), "worktree", "list", "--porcelain"],
        text=True,
    )


@pytest.fixture
def repo_with_coord_branch(tmp_path: Path) -> Path:
    """A tmp git repo with the coordination branch already created.

    Mirrors the post-WP03 state: ``mission create`` created the branch
    but not yet a coordination worktree.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "seed.txt").write_text("seed\n")
    _git(repo, "add", "seed.txt")
    _git(repo, "commit", "-q", "-m", "initial")
    _git(repo, "branch", COORD_BRANCH)
    return repo


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_worktree_path_is_pure(tmp_path: Path) -> None:
    path = CoordinationWorkspace.worktree_path(tmp_path, MISSION_SLUG, MID8)
    assert path == tmp_path / ".worktrees" / f"{MISSION_SLUG}-{MID8}-coord"
    # Pure: no filesystem effect.
    assert not path.exists()


def test_branch_name_is_pure() -> None:
    assert CoordinationWorkspace.branch_name(MISSION_SLUG, MID8) == COORD_BRANCH


def test_resolve_creates_worktree(repo_with_coord_branch: Path) -> None:
    path = CoordinationWorkspace.resolve(
        repo_with_coord_branch, MISSION_SLUG, MID8,
    )
    assert path.exists()
    assert path.is_dir()
    # HEAD should be on the coord branch.
    head = subprocess.check_output(
        ["git", "-C", str(path), "symbolic-ref", "HEAD"], text=True,
    ).strip()
    assert head == f"refs/heads/{COORD_BRANCH}"


def test_resolve_reuses_existing(repo_with_coord_branch: Path) -> None:
    first = CoordinationWorkspace.resolve(
        repo_with_coord_branch, MISSION_SLUG, MID8,
    )
    # Touch a file so we can verify the worktree wasn't recreated.
    marker = first / "MARKER"
    marker.write_text("preserved\n")

    second = CoordinationWorkspace.resolve(
        repo_with_coord_branch, MISSION_SLUG, MID8,
    )
    assert first == second
    assert marker.exists()
    assert marker.read_text() == "preserved\n"


def test_resolve_recovers_stale_prunable_registration(
    repo_with_coord_branch: Path,
) -> None:
    path = CoordinationWorkspace.resolve(
        repo_with_coord_branch, MISSION_SLUG, MID8,
    )
    shutil.rmtree(path)
    assert not path.exists()
    assert "prunable" in _worktree_list(repo_with_coord_branch)

    recovered = CoordinationWorkspace.resolve(
        repo_with_coord_branch, MISSION_SLUG, MID8,
    )

    assert recovered == path
    assert recovered.exists()
    assert "prunable" not in _worktree_list(repo_with_coord_branch)


def test_resolve_branch_mismatch_raises(repo_with_coord_branch: Path) -> None:
    path = CoordinationWorkspace.resolve(
        repo_with_coord_branch, MISSION_SLUG, MID8,
    )
    # Switch the worktree to a different branch.
    _git(path, "checkout", "-q", "-b", "interloper")

    with pytest.raises(CoordinationWorkspaceBranchMismatch) as exc:
        CoordinationWorkspace.resolve(
            repo_with_coord_branch, MISSION_SLUG, MID8,
        )

    err = exc.value
    assert err.error_code == "COORDINATION_WORKTREE_BRANCH_MISMATCH"
    assert err.expected_ref == COORD_BRANCH
    assert "interloper" in err.actual_ref
    assert err.worktree_path == path


def test_teardown_idempotent(repo_with_coord_branch: Path) -> None:
    path = CoordinationWorkspace.resolve(
        repo_with_coord_branch, MISSION_SLUG, MID8,
    )
    assert path.exists()

    CoordinationWorkspace.teardown(
        repo_with_coord_branch, MISSION_SLUG, MID8,
    )
    assert not path.exists()

    # Second call is a no-op.
    CoordinationWorkspace.teardown(
        repo_with_coord_branch, MISSION_SLUG, MID8,
    )
    assert not path.exists()


def test_teardown_prunes_stale_missing_registration(
    repo_with_coord_branch: Path,
) -> None:
    path = CoordinationWorkspace.resolve(
        repo_with_coord_branch, MISSION_SLUG, MID8,
    )
    shutil.rmtree(path)
    assert not path.exists()
    assert "prunable" in _worktree_list(repo_with_coord_branch)

    CoordinationWorkspace.teardown(
        repo_with_coord_branch, MISSION_SLUG, MID8,
    )

    worktree_list = _worktree_list(repo_with_coord_branch)
    assert str(path) not in worktree_list
    assert "prunable" not in worktree_list


def test_teardown_does_not_delete_branch(
    repo_with_coord_branch: Path,
) -> None:
    def head() -> str:
        return subprocess.run(
            ["git", "-C", str(repo_with_coord_branch), "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()

    head_before = head()
    CoordinationWorkspace.resolve(
        repo_with_coord_branch, MISSION_SLUG, MID8,
    )
    CoordinationWorkspace.teardown(
        repo_with_coord_branch, MISSION_SLUG, MID8,
    )
    # The branch must still exist; deletion is the merge command's job.
    result = subprocess.run(
        ["git", "-C", str(repo_with_coord_branch), "rev-parse",
         "--verify", f"refs/heads/{COORD_BRANCH}"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    # Tearing the coordination worktree down never moves the primary checkout's branch.
    assert head() == head_before


def test_is_present(repo_with_coord_branch: Path) -> None:
    assert not CoordinationWorkspace.is_present(
        repo_with_coord_branch, MISSION_SLUG, MID8,
    )
    CoordinationWorkspace.resolve(
        repo_with_coord_branch, MISSION_SLUG, MID8,
    )
    assert CoordinationWorkspace.is_present(
        repo_with_coord_branch, MISSION_SLUG, MID8,
    )
    CoordinationWorkspace.teardown(
        repo_with_coord_branch, MISSION_SLUG, MID8,
    )
    assert not CoordinationWorkspace.is_present(
        repo_with_coord_branch, MISSION_SLUG, MID8,
    )
