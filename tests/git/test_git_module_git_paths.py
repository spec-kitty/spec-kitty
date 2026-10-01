"""Real-git quoted / non-ASCII path cases for the ``specify_cli.git`` call sites.

Mission git-paths-are-data, WP04: each guard below used to read git's display
text (quoted, ``->``-joined) or split ``-z`` output by hand. These tests drive
the migrated sites against real temporary repositories (no git mocks) with a
path containing a space and a non-ASCII character.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from kernel.git import GitCommandError, GitPath
from specify_cli.git.commit_helpers import _unstage_requested_files
from specify_cli.git.report_transaction import _dirty_paths, _index
from specify_cli.git.sparse_checkout import SparseCheckoutScanReport, SparseCheckoutState
from specify_cli.git.sparse_checkout_remediation import _DIRTY_TREE_DETAIL, _dirty_refusal_detail, remediate

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

QUOTED = "local data/café notes.txt"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.name", "Test")
    _git(root, "config", "user.email", "test@example.invalid")
    _git(root, "config", "commit.gpgsign", "false")
    (root / "seed.txt").write_text("seed\n", encoding="utf-8")
    _git(root, "add", "seed.txt")
    _git(root, "commit", "-q", "-m", "seed")
    return root


def _write(root: Path, rel: str, text: str = "x\n") -> None:
    target = root / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


class TestSparseCheckoutDirtyRefusal:
    def test_clean_checkout_does_not_refuse(self, repo: Path) -> None:
        assert _dirty_refusal_detail(repo) is None

    def test_untracked_quoted_path_refuses_as_dirty(self, repo: Path) -> None:
        _write(repo, QUOTED)
        assert _dirty_refusal_detail(repo) == _DIRTY_TREE_DETAIL

    def test_missing_path_is_clean(self, tmp_path: Path) -> None:
        # Nothing to remediate at a path that does not exist.
        assert _dirty_refusal_detail(tmp_path / "absent") is None

    def test_existing_non_git_directory_refuses_as_unreadable(self, tmp_path: Path) -> None:
        # A failed probe cannot prove the tree clean; the destructive
        # ``git checkout HEAD -- .`` step must be refused -- and the message
        # must say the status could not be read, not that the tree is dirty.
        plain = tmp_path / "plain"
        plain.mkdir()
        detail = _dirty_refusal_detail(plain)
        assert detail is not None
        assert detail.startswith(f"could not read git status in {plain}")
        assert "dirty working tree" not in detail

    def test_status_failure_in_real_repo_refuses_as_unreadable(self, repo: Path) -> None:
        (repo / ".git" / "index").write_bytes(b"not an index")
        with pytest.raises(subprocess.CalledProcessError):
            _git(repo, "status", "--porcelain")
        detail = _dirty_refusal_detail(repo)
        assert detail is not None
        assert "could not read git status" in detail
        assert "refused" in detail

    def test_unreadable_probe_refuses_every_target_with_its_message(self, tmp_path: Path) -> None:
        plain = tmp_path / "plain"
        plain.mkdir()
        primary = SparseCheckoutState(path=plain, config_enabled=True, pattern_file_path=None, pattern_file_present=False, pattern_line_count=0, is_worktree=False)

        result = remediate(SparseCheckoutScanReport(primary=primary, worktrees=()), interactive=False)

        assert result.primary_result.success is False
        assert result.primary_result.dirty_before_remediation is True
        assert "could not read git status" in (result.primary_result.error_detail or "")


class TestReportTransactionPaths:
    def test_dirty_paths_reports_quoted_untracked_path_verbatim(self, repo: Path) -> None:
        _write(repo, QUOTED)
        assert _dirty_paths(repo) == {QUOTED}

    def test_dirty_paths_expands_untracked_directory(self, repo: Path) -> None:
        _write(repo, "a dir/é one.txt")
        _write(repo, "a dir/two.txt")
        assert _dirty_paths(repo) == {"a dir/é one.txt", "a dir/two.txt"}

    def test_dirty_paths_keeps_both_rename_endpoints(self, repo: Path) -> None:
        _write(repo, "old name é.md", "same content\n")
        _git(repo, "add", "--", "old name é.md")
        _git(repo, "commit", "-q", "-m", "add")
        _git(repo, "mv", "--", "old name é.md", "new name é.md")
        assert _dirty_paths(repo) == {"old name é.md", "new name é.md"}

    def test_index_excludes_the_quoted_report_path(self, repo: Path) -> None:
        report = "docs/my report é.md"
        _write(repo, report)
        _git(repo, "add", "--", report)
        entries = _index(repo, report)
        assert [entry.path for entry in entries] == [GitPath.parse("seed.txt")]

    def test_index_refuses_skip_worktree_entry(self, repo: Path) -> None:
        _write(repo, QUOTED)
        _git(repo, "add", "--", QUOTED)
        _git(repo, "update-index", "--skip-worktree", "--", QUOTED)
        with pytest.raises(ValueError, match="Unsupported index flags"):
            _index(repo, "analysis-report.md")


class TestUnstageRequestedFiles:
    def test_unstages_a_quoted_path_and_leaves_others_staged(self, repo: Path) -> None:
        _write(repo, QUOTED)
        _write(repo, "other é.txt")
        _git(repo, "add", "--", QUOTED, "other é.txt")
        _unstage_requested_files(repo, [QUOTED])
        staged = _git(repo, "diff", "--cached", "--name-only", "-z").split("\0")
        assert [path for path in staged if path] == ["other é.txt"]

    def test_failed_probe_unstages_nothing(self, repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        # Advisory recovery step: when the staged-paths probe fails there is
        # nothing safe to unstage, so the index must be left exactly as it was.
        _write(repo, QUOTED)
        _git(repo, "add", "--", QUOTED)
        before = _git(repo, "diff", "--cached", "--name-only", "-z")
        assert before

        def _boom(*_args: object, **_kwargs: object) -> None:
            raise GitCommandError(argv=("diff",), cwd=repo, returncode=128, stderr="boom")

        monkeypatch.setattr("specify_cli.git.commit_helpers.changed_paths", _boom)
        _unstage_requested_files(repo, [QUOTED])
        assert _git(repo, "diff", "--cached", "--name-only", "-z") == before

    def test_unstage_glob_characters_are_literal(self, repo: Path) -> None:
        _write(repo, "a*.txt")
        _write(repo, "abc.txt")
        _git(repo, "add", "-A")
        _unstage_requested_files(repo, ["a*.txt"])
        staged = [path for path in _git(repo, "diff", "--cached", "--name-only", "-z").split("\0") if path]
        assert staged == ["abc.txt"]

    def test_unstage_glob_characters_are_literal_without_head(self, tmp_path: Path) -> None:
        root = tmp_path / "unborn"
        root.mkdir()
        _git(root, "init", "-q", "-b", "main")
        _write(root, "a*.txt")
        _write(root, "abc.txt")
        _git(root, "add", "-A")
        _unstage_requested_files(root, ["a*.txt"])
        staged = [path for path in _git(root, "ls-files", "-z").split("\0") if path]
        assert staged == ["abc.txt"]
