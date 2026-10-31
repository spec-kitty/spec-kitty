"""#6750 WP01: ``safe_commit`` refuses a directory request before any mutation.

The commit seam's contract is "commit exactly these file paths". Git expands a
directory pathspec itself, so a directory argument produced a commit carrying
paths the caller never requested -- and the post-landing guard then blamed a
pre-commit hook for the extras (see WP02 for the caller that passed one).

These tests pin the seam invariant at the two ends it has to hold:

* a directory argument raises ``SafeCommitDirectoryArgument`` (code
  ``SAFE_COMMIT_DIRECTORY_ARGUMENT``) **before** HEAD, refs or the index move;
* the paths that are not directories -- explicit child files, a symlinked
  directory, a deleted-but-tracked file -- still commit, and the public
  ``spec-kitty safe-commit`` CLI keeps its own directory expansion (#2739 B11).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from specify_cli import app as cli_app
from specify_cli.git.commit_helpers import (
    SafeCommitDirectoryArgument,
    SafeCommitError,
    safe_commit,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_BRANCH = "kitty/mission-6750-directory-arg"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
    ).stdout


def _init_repo(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-q", "-b", _BRANCH)
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test User")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "seed.txt").write_text("seed\n", encoding="utf-8")
    _git(repo, "add", "seed.txt")
    _git(repo, "commit", "-q", "-m", "initial commit")


def _seed_untracked_directory(repo: Path) -> Path:
    """A brand-new directory of two untracked files -- ``git status`` collapses it."""
    cache = repo / ".zig-cache"
    cache.mkdir()
    (cache / "one.bin").write_text("1\n", encoding="utf-8")
    (cache / "two.bin").write_text("2\n", encoding="utf-8")
    return cache


def _repo_state(repo: Path) -> tuple[str, str, str]:
    """The three observable facts a refusal must leave untouched."""
    head = _git(repo, "rev-parse", "HEAD")
    refs = _git(repo, "for-each-ref", "--format=%(refname) %(objectname)")
    status = _git(repo, "status", "--porcelain=v1", "--untracked-files=all")
    return head, refs, status


def _committed_paths(repo: Path, sha: str) -> set[str]:
    out = _git(repo, "show", "--name-only", "--pretty=format:", sha)
    return {line for line in out.splitlines() if line.strip()}


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    _init_repo(repo)
    return repo


def test_safe_commit_refuses_directory_argument_before_mutation(repo: Path) -> None:
    """SC-003 / NFR-002: the refusal is typed, truthful and mutation-free.

    RED on the pre-fix seam: the directory is staged and committed, HEAD moves and
    no exception is raised (the post-landing guard fires later with hook wording).
    """
    cache = _seed_untracked_directory(repo)
    before = _repo_state(repo)

    with pytest.raises(SafeCommitDirectoryArgument) as excinfo:
        safe_commit(
            repo_root=repo,
            worktree_root=repo,
            destination_ref=_BRANCH,
            message="should not land",
            paths=(cache,),
        )

    err = excinfo.value
    assert isinstance(err, SafeCommitError), "callers that flatten SafeCommitError/RuntimeError must keep working"
    assert isinstance(err, RuntimeError)
    assert err.error_code == "SAFE_COMMIT_DIRECTORY_ARGUMENT"
    message = str(err)
    assert ".zig-cache" in message, f"the refusal must name the offending path; got {message!r}"
    assert "hook" not in message.lower(), f"a directory argument is the caller's request, not a hook's doing; the refusal must not blame a hook; got {message!r}"
    assert err.to_dict()["offending_path"] == ".zig-cache"

    head, refs, status = _repo_state(repo)
    assert (head, refs, status) == before, "the refusal must be total: HEAD, refs and index untouched"
    assert ".zig-cache" not in _git(repo, "ls-files", "--")


def test_safe_commit_commits_explicit_child_paths(repo: Path) -> None:
    """Positive control on the same fixture: the exact file set still commits."""
    cache = _seed_untracked_directory(repo)

    result = safe_commit(
        repo_root=repo,
        worktree_root=repo,
        destination_ref=_BRANCH,
        message="commit the exact deliverables",
        paths=(cache / "one.bin", cache / "two.bin"),
    )

    assert _committed_paths(repo, result.sha) == {".zig-cache/one.bin", ".zig-cache/two.bin"}


def test_safe_commit_does_not_refuse_symlinked_directory(repo: Path) -> None:
    """A symlinked directory is one ``120000`` entry, never a directory to refuse."""
    real = repo / "real-dir"
    real.mkdir()
    (real / "file.txt").write_text("content\n", encoding="utf-8")
    link = repo / "link-dir"
    link.symlink_to(real, target_is_directory=True)

    result = safe_commit(
        repo_root=repo,
        worktree_root=repo,
        destination_ref=_BRANCH,
        message="commit the directory symlink",
        paths=(link,),
    )

    assert _committed_paths(repo, result.sha) == {"link-dir"}
    assert _git(repo, "ls-tree", result.sha, "link-dir").startswith("120000")


def test_safe_commit_does_not_refuse_deleted_tracked_file(repo: Path) -> None:
    """A deleted tracked file is a legitimate request (it does not exist on disk)."""
    (repo / "gone.txt").write_text("bye\n", encoding="utf-8")
    _git(repo, "add", "gone.txt")
    _git(repo, "commit", "-q", "-m", "add gone")
    (repo / "gone.txt").unlink()

    result = safe_commit(
        repo_root=repo,
        worktree_root=repo,
        destination_ref=_BRANCH,
        message="record the deletion",
        paths=(repo / "gone.txt",),
    )

    assert _committed_paths(repo, result.sha) == {"gone.txt"}


def test_public_safe_commit_cli_still_expands_a_directory(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """C-001: the CLI's own expansion (#2739 B11) is unchanged by the seam refusal."""
    cache = _seed_untracked_directory(repo)
    monkeypatch.chdir(repo)

    result = CliRunner().invoke(
        cli_app,
        ["safe-commit", ".zig-cache", "-m", "cli expands the directory", "--to-branch", _BRANCH],
    )

    assert result.exit_code == 0, f"stdout={result.stdout!r} stderr={result.stderr!r} exit={result.exit_code}"
    committed = _committed_paths(repo, _git(repo, "rev-parse", "HEAD").strip())
    assert committed == {".zig-cache/one.bin", ".zig-cache/two.bin"}
    assert cache.is_dir()


def test_safe_commit_does_not_refuse_a_submodule_gitlink(repo: Path) -> None:
    """A submodule path IS a directory, but it is committed as one 160000 gitlink.

    Refusing it would block every repo that carries submodules, for a path the
    exact-file comparison already handles (git reports the gitlink itself). The
    fixture is a real submodule shape without needing submodule config: a nested
    git repository plus a gitlink index entry pointing at its commit.
    """
    nested = repo / "vendor-lib"
    nested.mkdir()
    _git(nested, "init", "-q", "-b", "main")
    _git(nested, "config", "user.email", "test@example.com")
    _git(nested, "config", "user.name", "Test")
    (nested / "contents.txt").write_text("nested repo content\n", encoding="utf-8")
    _git(nested, "add", "contents.txt")
    _git(nested, "commit", "-q", "-m", "nested seed")
    nested_sha = _git(nested, "rev-parse", "HEAD").strip()
    _git(repo, "update-index", "--add", "--cacheinfo", f"160000,{nested_sha},vendor-lib")

    result = safe_commit(
        repo_root=repo,
        worktree_root=repo,
        destination_ref=_BRANCH,
        message="commit the submodule pointer",
        paths=(nested,),
    )

    assert _committed_paths(repo, result.sha) == {"vendor-lib"}
    assert _git(repo, "ls-tree", result.sha, "vendor-lib").startswith("160000")
