"""Coordination git probes read paths as data (mission git-paths-are-data, WP03).

Real temporary repositories, no git mocks. A directory with a space makes
``git status`` print ``?? "a b/"`` and a non-ASCII name makes ``ls-tree`` print
an escaped, quoted path: both used to defeat the line-based checks.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from kernel.git import GitCommandError
from mission_runtime import MissionArtifactKind
from specify_cli.coordination.commit_router import _paths_uncommitted_in_primary
from specify_cli.coordination.surface_resolver import coord_branch_has_committed_artifact
from specify_cli.coordination.transaction import BookkeepingTransaction

pytestmark = pytest.mark.git_repo

_COORD = "kitty/mission-m-coord"


def _git(repo: Path, *args: str) -> str:
    done = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True)
    return done.stdout.strip()


def _write(repo: Path, rel: str, text: str = "x\n") -> Path:
    target = repo / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    return target


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "t")
    _write(repo, "README.md", "init\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "init")
    return repo


class TestPathsUncommittedInPrimary:
    def test_untracked_file_in_a_spaced_directory_counts_as_uncommitted(self, tmp_path: Path) -> None:
        repo = _repo(tmp_path)
        path = _write(repo, "a b/f.txt")

        assert _paths_uncommitted_in_primary(repo, (path,)) is True

    def test_modified_tracked_file_in_a_non_ascii_directory_counts_as_uncommitted(self, tmp_path: Path) -> None:
        repo = _repo(tmp_path)
        path = _write(repo, "é/g.txt", "one\n")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", "add")
        _write(repo, "é/g.txt", "two\n")

        assert _paths_uncommitted_in_primary(repo, (path,)) is True

    def test_committed_file_is_clean(self, tmp_path: Path) -> None:
        repo = _repo(tmp_path)
        path = _write(repo, "a b/f.txt")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", "add")

        assert _paths_uncommitted_in_primary(repo, (path,)) is False

    def test_a_dirty_sibling_is_not_mistaken_for_the_requested_path(self, tmp_path: Path) -> None:
        repo = _repo(tmp_path)
        clean = _write(repo, "a b/f.txt")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", "add")
        _write(repo, "a b/f.txt.bak")

        assert _paths_uncommitted_in_primary(repo, (clean,)) is False

    def test_unreadable_status_propagates_instead_of_reading_as_clean(self, tmp_path: Path) -> None:
        plain = tmp_path / "plain"
        plain.mkdir()
        path = _write(plain, "a b/f.txt")

        # Guard (FR-013): a failed probe must not let a wrong-surface no-op pass as benign.
        with pytest.raises(GitCommandError):
            _paths_uncommitted_in_primary(plain, (path,))


class TestCoordBranchHasCommittedArtifact:
    def _coord_repo(self, tmp_path: Path, rel: str) -> Path:
        repo = _repo(tmp_path)
        _git(repo, "checkout", "-q", "-b", _COORD)
        _write(repo, rel, "{}\n")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", "matrix")
        _git(repo, "checkout", "-q", "main")
        return repo

    @pytest.mark.parametrize("subdir", ["", "é dir/", "two words/"])
    def test_committed_matrix_is_found_under_a_quoted_subpath(self, tmp_path: Path, subdir: str) -> None:
        repo = self._coord_repo(tmp_path, f"kitty-specs/m/{subdir}issue-matrix.json")

        assert coord_branch_has_committed_artifact(repo, _COORD, "m", MissionArtifactKind.ISSUE_MATRIX) is True

    def test_absent_matrix_on_a_readable_branch_is_false(self, tmp_path: Path) -> None:
        repo = self._coord_repo(tmp_path, "kitty-specs/m/notes/é.md")

        assert coord_branch_has_committed_artifact(repo, _COORD, "m", MissionArtifactKind.ISSUE_MATRIX) is False

    def test_unresolvable_branch_fails_closed_as_present(self, tmp_path: Path) -> None:
        repo = _repo(tmp_path)

        assert coord_branch_has_committed_artifact(repo, "no-such-branch", "m", MissionArtifactKind.ISSUE_MATRIX) is True


class TestWorktreeHasPendingChanges:
    def _probe(self, worktree: Path, staged: list[Path]) -> bool:
        stand_in = SimpleNamespace(_staged_paths=staged, worktree_root=worktree)
        return BookkeepingTransaction._worktree_has_pending_changes(cast("BookkeepingTransaction", stand_in))

    def test_pending_change_in_a_spaced_directory_is_seen(self, tmp_path: Path) -> None:
        repo = _repo(tmp_path)
        path = _write(repo, "a b/f.txt")

        assert self._probe(repo, [path]) is True

    def test_committed_staged_path_reports_no_pending_changes(self, tmp_path: Path) -> None:
        repo = _repo(tmp_path)
        path = _write(repo, "a b/f.txt")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", "add")

        assert self._probe(repo, [path]) is False

    def test_nothing_staged_reports_no_pending_changes(self, tmp_path: Path) -> None:
        repo = _repo(tmp_path)

        assert self._probe(repo, []) is False

    def test_unreadable_status_fails_open_so_the_real_commit_surfaces_the_error(self, tmp_path: Path) -> None:
        plain = tmp_path / "plain"
        plain.mkdir()
        path = _write(plain, "a b/f.txt")

        assert self._probe(plain, [path]) is True
