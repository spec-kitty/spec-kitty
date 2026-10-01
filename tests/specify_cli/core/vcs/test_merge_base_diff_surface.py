"""Direct tests for the canonical merge-base/diff surface.

Covers ``git_merge_base``, ``git_diff_names``, and ``merge_base_changed_files``
in ``specify_cli.core.vcs.git`` (mission merge-base-diff-ssot-01KX44SD).

Prefers a real temp git repo for behaviour; mocks subprocess only for the
failure-exit cases that are hard to stage with a real repo (a non-zero exit
from ``git merge-base``/``git diff`` themselves).
"""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from kernel.git import GitCommandError
from specify_cli.core.vcs.git import (
    git_diff_names,
    git_diff_names_checked,
    git_ls_tree_names_checked,
    git_merge_base,
    merge_base_changed_files,
)

pytestmark = pytest.mark.git_repo


def _run(cmd, cwd):
    subprocess.run(cmd, cwd=str(cwd), capture_output=True, check=True)


def _commit(repo, filename, content, message):
    (repo / filename).parent.mkdir(parents=True, exist_ok=True)
    (repo / filename).write_text(content)
    _run(["git", "add", filename], repo)
    _run(["git", "commit", "-m", message], repo)


def _make_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _run(["git", "init", str(repo)], tmp_path)
    _run(["git", "config", "user.email", "test@test.com"], repo)
    _run(["git", "config", "user.name", "Test"], repo)
    _commit(repo, "README.md", "init\n", "init")
    _run(["git", "branch", "-M", "main"], repo)
    return repo


class TestGitMergeBase:
    def test_normal_merge_base(self, tmp_path):
        repo = _make_repo(tmp_path)
        _run(["git", "branch", "side"], repo)
        _commit(repo, "src/a.py", "main change\n", "main change")

        mb = git_merge_base(repo, "HEAD", "side")

        assert mb is not None
        assert len(mb) == 40  # full SHA

    def test_non_zero_exit_returns_none(self, tmp_path):
        repo = _make_repo(tmp_path)

        mb = git_merge_base(repo, "HEAD", "does-not-exist")

        assert mb is None

    def test_empty_stdout_returns_none(self, tmp_path):
        repo = _make_repo(tmp_path)
        fake_result = MagicMock(returncode=0, stdout="  \n")
        with patch("specify_cli.core.vcs.git.subprocess.run", return_value=fake_result):
            mb = git_merge_base(repo, "HEAD", "HEAD")

        assert mb is None

    def test_never_raises_on_git_failure(self, tmp_path):
        repo = _make_repo(tmp_path)
        fake_result = MagicMock(returncode=128, stdout="")
        with patch("specify_cli.core.vcs.git.subprocess.run", return_value=fake_result):
            mb = git_merge_base(repo, "HEAD", "unrelated")

        assert mb is None


class TestGitDiffNames:
    def test_normal_diff_returns_n_files(self, tmp_path):
        repo = _make_repo(tmp_path)
        base = git_merge_base(repo, "HEAD", "HEAD")
        _commit(repo, "src/a.py", "one\n", "a")
        _commit(repo, "src/b.py", "two\n", "b")

        names = git_diff_names(repo, base, "HEAD")

        assert set(names) == {"src/a.py", "src/b.py"}

    def test_non_zero_exit_returns_empty_tuple(self, tmp_path):
        # Real git: an unknown ref makes ``git diff`` exit non-zero.
        repo = _make_repo(tmp_path)

        assert git_diff_names(repo, "no-such-ref", "HEAD") == ()

    def test_pathspec_restricts_output(self, tmp_path):
        repo = _make_repo(tmp_path)
        base = git_merge_base(repo, "HEAD", "HEAD")
        _commit(repo, "kitty-specs/spec.md", "spec\n", "spec change")
        _commit(repo, "src/other.py", "other\n", "other change")

        names = git_diff_names(repo, base, "HEAD", pathspec="kitty-specs/")

        assert names == ("kitty-specs/spec.md",)

    def test_diff_filter_is_passed_through(self, tmp_path):
        # Real git: only the added file survives ``--diff-filter=A``.
        repo = _make_repo(tmp_path)
        base = git_merge_base(repo, "HEAD", "HEAD")
        _commit(repo, "src/added.py", "one\n", "add")
        (repo / "README.md").write_text("changed\n")
        _run(["git", "commit", "-q", "-am", "edit"], repo)

        assert git_diff_names(repo, base, "HEAD", diff_filter="A") == ("src/added.py",)

    def test_non_head_branch_target_fences_f1(self, tmp_path):
        """F1 fence: git_diff_names must diff an arbitrary ``head``, not HEAD.

        Builds a side branch with commits HEAD does NOT have, then diffs
        ``mb`` against that side branch (not HEAD). If a future change
        silently swapped this call to the HEAD-relative convenience, this
        test would fail red because HEAD has no changes relative to the
        merge-base.
        """
        repo = _make_repo(tmp_path)
        _run(["git", "branch", "side"], repo)
        _run(["git", "checkout", "side"], repo)
        _commit(repo, "src/side_only.py", "side\n", "side change")
        _run(["git", "checkout", "main"], repo)

        mb = git_merge_base(repo, "HEAD", "side")
        assert mb is not None

        # HEAD has no changes relative to the merge-base (side moved, not main).
        assert git_diff_names(repo, mb, "HEAD") == ()

        # Diffing against the side branch (head != HEAD) reports its file.
        names = git_diff_names(repo, mb, "side")
        assert names == ("src/side_only.py",)

    def test_two_arg_form_equivalent_to_range_form(self, tmp_path):
        """Documents the silent <mb>..HEAD -> two-arg rewrite three sites undergo."""
        repo = _make_repo(tmp_path)
        _commit(repo, "src/a.py", "one\n", "a")
        _commit(repo, "src/b.py", "two\n", "b")
        mb = git_merge_base(repo, "HEAD", "HEAD~2")
        assert mb is not None

        two_arg = git_diff_names(repo, mb, "HEAD")

        raw = subprocess.run(
            ["git", "diff", "--name-only", f"{mb}..HEAD"],
            cwd=str(repo),
            capture_output=True,
            text=True,
            check=True,
        )
        raw_names = tuple(line.strip() for line in raw.stdout.splitlines() if line.strip())

        assert set(two_arg) == set(raw_names)


class TestMergeBaseChangedFiles:
    def test_no_merge_base_returns_empty(self, tmp_path):
        repo = _make_repo(tmp_path)

        result = merge_base_changed_files(repo, "does-not-exist")

        assert result == ()

    def test_diff_failure_returns_empty(self, tmp_path):
        repo = _make_repo(tmp_path)

        # A merge-base that resolves but a diff that fails (unknown object) is ()
        with patch("specify_cli.core.vcs.git.git_merge_base", return_value="0" * 40):
            result = merge_base_changed_files(repo, "HEAD")

        assert result == ()

    def test_composes_merge_base_and_diff(self, tmp_path):
        repo = _make_repo(tmp_path)
        _run(["git", "branch", "base-branch"], repo)
        _commit(repo, "src/a.py", "one\n", "a")

        result = merge_base_changed_files(repo, "base-branch")

        assert result == ("src/a.py",)

    def test_pathspec_and_diff_filter_thread_through(self, tmp_path):
        repo = _make_repo(tmp_path)
        _run(["git", "branch", "base-branch"], repo)
        _commit(repo, ".github/workflows/ci.yml", "ci\n", "ci change")
        _commit(repo, "src/other.py", "other\n", "other change")

        result = merge_base_changed_files(
            repo,
            "base-branch",
            pathspec=".github/workflows",
            diff_filter="AMR",
        )

        assert result == (".github/workflows/ci.yml",)


class TestGitLsTreeNamesChecked:
    """Fail-distinguishing base-tree listing: ``None`` on git failure vs ``()`` on nothing recorded."""

    def test_non_zero_exit_returns_none(self, tmp_path):
        _run(["git", "init", "-q", "-b", "main"], tmp_path)
        assert git_ls_tree_names_checked(tmp_path, "0" * 40, "kitty-specs/x/") is None

    def test_timeout_is_passed_through(self, tmp_path):
        with patch("specify_cli.core.vcs.git.tree_paths", return_value=frozenset()) as mock_tree:
            assert git_ls_tree_names_checked(tmp_path, "HEAD", "kitty-specs/x/", timeout=7) == ()
        assert mock_tree.call_args.kwargs["timeout"] == 7
        assert mock_tree.call_args.kwargs["pathspecs"] == ("kitty-specs/x/",)

    def test_timeout_propagates_as_timeout_expired(self, tmp_path):
        timed_out = GitCommandError(argv=("ls-tree",), cwd=tmp_path, returncode=-1, stderr="", timed_out=True)
        with (
            patch("specify_cli.core.vcs.git.tree_paths", side_effect=timed_out),
            pytest.raises(subprocess.TimeoutExpired),
        ):
            git_ls_tree_names_checked(tmp_path, "HEAD", "kitty-specs/x/", timeout=7)

    def test_real_repo_lists_recursively_and_scopes_to_path(self, tmp_path):
        _run(["git", "init", "-q", "-b", "main"], tmp_path)
        _run(["git", "config", "user.email", "t@example.com"], tmp_path)
        _run(["git", "config", "user.name", "t"], tmp_path)
        (tmp_path / "kitty-specs" / "x" / "sub").mkdir(parents=True)
        (tmp_path / "kitty-specs" / "x" / "a.md").write_text("a\n")
        (tmp_path / "kitty-specs" / "x" / "sub" / "meta.json").write_text("{}\n")
        (tmp_path / "kitty-specs" / "y.md").write_text("y\n")
        _run(["git", "add", "-A"], tmp_path)
        _run(["git", "commit", "-q", "-m", "base"], tmp_path)

        assert git_ls_tree_names_checked(tmp_path, "HEAD", "kitty-specs/x/") == (
            "kitty-specs/x/a.md",
            "kitty-specs/x/sub/meta.json",
        )
        assert git_ls_tree_names_checked(tmp_path, "HEAD", "kitty-specs/nope/") == ()
        assert git_ls_tree_names_checked(tmp_path, "0" * 40, "kitty-specs/x/") is None


class TestGitDiffNamesChecked:
    """Fail-distinguishing variant: ``None`` on git failure vs ``()`` on empty diff."""

    def test_non_zero_exit_returns_none(self, tmp_path):
        repo = _make_repo(tmp_path)
        assert git_diff_names_checked(repo, "no-such-ref", "HEAD") is None

    def test_empty_diff_returns_empty_tuple_not_none(self, tmp_path):
        # The load-bearing distinction: a genuinely-empty diff is () (success),
        # NOT None (failure). Fail-closed callers rely on this.
        repo = _make_repo(tmp_path)
        assert git_diff_names_checked(repo, "HEAD", "HEAD") == ()

    def test_success_returns_paths(self, tmp_path):
        repo = _make_repo(tmp_path)
        base = git_merge_base(repo, "HEAD", "HEAD")
        _commit(repo, "a.py", "a\n", "a")
        _commit(repo, "b.py", "b\n", "b")
        assert git_diff_names_checked(repo, base, "HEAD") == ("a.py", "b.py")

    def test_pathspec_and_diff_filter_passthrough(self, tmp_path):
        with patch("specify_cli.core.vcs.git.changed_paths", return_value=()) as mock_changed:
            git_diff_names_checked(tmp_path, "base", "head", pathspec="x/", diff_filter="AMR")
        assert mock_changed.call_args.kwargs["pathspecs"] == ("x/",)
        assert mock_changed.call_args.kwargs["diff_filter"] == "AMR"
        assert mock_changed.call_args.kwargs["renames"] is True

    def test_git_diff_names_maps_none_to_empty_tuple(self, tmp_path):
        # The fail-open wrapper collapses the checked variant's None to ().
        repo = _make_repo(tmp_path)
        assert git_diff_names_checked(repo, "no-such-ref", "HEAD") is None
        assert git_diff_names(repo, "no-such-ref", "HEAD") == ()
