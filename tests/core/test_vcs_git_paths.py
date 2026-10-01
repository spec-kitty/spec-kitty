"""``core.vcs.git`` reads paths from git as data (mission git-paths-are-data, WP03).

Real temporary repositories, no git mocks: a path git would quote in display text
(a space in ``git status``, a non-ASCII name everywhere) must come back exact.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from specify_cli.core.vcs.git import (
    GitVCS,
    git_diff_names,
    git_diff_names_checked,
    git_ls_tree_names_checked,
    git_merge_base,
    merge_base_changed_files,
)

pytestmark = pytest.mark.git_repo

_SPACED = "a b/f.txt"
_ACCENTED = "é/g.txt"


def _git(repo: Path, *args: str) -> str:
    done = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True)
    return done.stdout


def _write(repo: Path, rel: str, text: str) -> None:
    target = repo / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


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


def _commit_quoted(repo: Path) -> None:
    _write(repo, _SPACED, "one\n")
    _write(repo, _ACCENTED, "two\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "quoted")


class TestDiffHelpersReturnExactPaths:
    def test_merge_base_changed_files_unquotes_non_ascii_and_spaces(self, tmp_path: Path) -> None:
        repo = _repo(tmp_path)
        _git(repo, "branch", "base-branch")
        _commit_quoted(repo)

        assert set(merge_base_changed_files(repo, "base-branch")) == {_SPACED, _ACCENTED}

    def test_git_diff_names_checked_respects_a_literal_pathspec(self, tmp_path: Path) -> None:
        repo = _repo(tmp_path)
        base = git_merge_base(repo, "HEAD", "HEAD")
        assert base is not None
        _commit_quoted(repo)

        assert git_diff_names_checked(repo, base, "HEAD", pathspec="a b/") == (_SPACED,)
        assert git_diff_names_checked(repo, base, "HEAD", pathspec="é") == (_ACCENTED,)

    def test_a_rename_lists_only_the_new_path_as_before(self, tmp_path: Path) -> None:
        repo = _repo(tmp_path)
        _commit_quoted(repo)
        base = _git(repo, "rev-parse", "HEAD").strip()
        _git(repo, "mv", _SPACED, "a b/renamed.txt")
        _git(repo, "commit", "-q", "-m", "rename")

        assert git_diff_names(repo, base, "HEAD") == ("a b/renamed.txt",)

    def test_failed_diff_is_none_for_the_checked_helper_and_empty_for_the_tolerant_one(self, tmp_path: Path) -> None:
        repo = _repo(tmp_path)

        assert git_diff_names_checked(repo, "no-such-ref", "HEAD") is None
        assert git_diff_names(repo, "no-such-ref", "HEAD") == ()


class TestLsTreeHelperReturnsExactPaths:
    def test_lists_a_directory_with_a_space_recursively(self, tmp_path: Path) -> None:
        repo = _repo(tmp_path)
        _write(repo, "kitty-specs/my mission/sub/meta.json", "{}\n")
        _write(repo, "kitty-specs/my mission/é.md", "x\n")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", "mission")

        assert git_ls_tree_names_checked(repo, "HEAD", "kitty-specs/my mission/") == (
            "kitty-specs/my mission/sub/meta.json",
            "kitty-specs/my mission/é.md",
        )

    def test_unknown_revision_is_none_and_absent_directory_is_empty(self, tmp_path: Path) -> None:
        repo = _repo(tmp_path)

        assert git_ls_tree_names_checked(repo, "0" * 40, "kitty-specs/x/") is None
        assert git_ls_tree_names_checked(repo, "HEAD", "kitty-specs/x/") == ()


class TestGitVcsStatusProbes:
    def test_workspace_info_sees_a_dirty_quoted_path(self, tmp_path: Path) -> None:
        repo = _repo(tmp_path)
        _write(repo, _SPACED, "dirty\n")

        info = GitVCS().get_workspace_info(repo)

        assert info is not None
        assert info.has_uncommitted is True

    def test_workspace_info_clean_tree_has_no_uncommitted(self, tmp_path: Path) -> None:
        repo = _repo(tmp_path)

        info = GitVCS().get_workspace_info(repo)

        assert info is not None
        assert info.has_uncommitted is False

    def _conflict(self, repo: Path, rel: str) -> None:
        _write(repo, rel, "base\n")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", "base")
        _git(repo, "branch", "side")
        _write(repo, rel, "main\n")
        _git(repo, "commit", "-q", "-am", "main edit")
        _git(repo, "checkout", "-q", "side")
        _write(repo, rel, "side\n")
        _git(repo, "commit", "-q", "-am", "side edit")
        _git(repo, "checkout", "-q", "main")
        subprocess.run(["git", "merge", "side"], cwd=repo, capture_output=True, check=False)

    @pytest.mark.parametrize("rel", ["a b/c.txt", "é/c.txt"])
    def test_conflict_in_a_quoted_path_is_detected_with_its_real_name(self, tmp_path: Path, rel: str) -> None:
        repo = _repo(tmp_path)
        self._conflict(repo, rel)
        vcs = GitVCS()

        assert vcs.has_conflicts(repo) is True
        assert [conflict.file_path for conflict in vcs.detect_conflicts(repo)] == [Path(rel)]

    def test_no_conflicts_in_a_clean_repository(self, tmp_path: Path) -> None:
        repo = _repo(tmp_path)
        vcs = GitVCS()

        assert vcs.has_conflicts(repo) is False
        assert vcs.detect_conflicts(repo) == []

    def test_probes_outside_a_repository_report_nothing_instead_of_raising(self, tmp_path: Path) -> None:
        # Advisory probes: an unreadable status is "no conflicts", never a crash.
        plain = tmp_path / "plain"
        plain.mkdir()
        vcs = GitVCS()

        assert vcs.has_conflicts(plain) is False
        assert vcs.detect_conflicts(plain) == []
