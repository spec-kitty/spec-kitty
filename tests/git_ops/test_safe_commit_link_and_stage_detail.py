"""``safe_commit`` commits the link (not its target) and names a failing path (#5671, #4722)."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from mission_runtime import CommitTarget
from specify_cli.git.commit_helpers import SafeCommitError, safe_commit

pytestmark = [pytest.mark.git_repo, pytest.mark.non_sandbox, pytest.mark.regression]

BRANCH = "work"


def _git(repo: Path, *args: str, check: bool = True) -> str:
    result = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=False)
    if check and result.returncode != 0:
        raise AssertionError(f"git {args} failed: {result.stderr}")
    return result.stdout


@pytest.fixture(autouse=True)
def _hermetic_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    for key in list(os.environ):
        if key.startswith(("GIT_", "SPEC_KITTY_")):
            monkeypatch.delenv(key)
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(home / ".gitconfig"))


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    r = tmp_path / "repo"
    r.mkdir()
    _git(r, "init", "--template=", "-b", BRANCH)
    _git(r, "config", "user.email", "t@example.com")
    _git(r, "config", "user.name", "T")
    _git(r, "config", "commit.gpgsign", "false")
    (r / "real.md").write_text("base\n")
    (r / "tracked.txt").write_text("t\n")
    _git(r, "add", "-A")
    _git(r, "commit", "-m", "init")
    return r


def _commit(repo: Path, *paths: Path, **kwargs: object) -> object:
    return safe_commit(
        repo_root=repo,
        worktree_root=repo,
        target=CommitTarget(ref=BRANCH),
        message="msg",
        paths=tuple(paths),
        **kwargs,  # type: ignore[arg-type]
    )


def _symlink(link: Path, target: str) -> None:
    try:
        os.symlink(target, link)
    except (OSError, NotImplementedError):
        pytest.skip("os.symlink unavailable (Windows without developer mode)")


def test_absolute_symlink_path_commits_the_link_not_the_target(repo: Path) -> None:
    _symlink(repo / "link.md", "real.md")
    (repo / "real.md").write_text("base\nWIP\n")
    _commit(repo, repo / "link.md")
    assert _git(repo, "ls-tree", "HEAD", "link.md").startswith("120000 ")
    assert _git(repo, "show", "HEAD:link.md") == "real.md"
    assert _git(repo, "show", "HEAD", "--name-only", "--format=").split() == ["link.md"]
    assert "+WIP" in _git(repo, "diff", "HEAD", "--", "real.md")


def test_tracked_link_repointed_commits_the_new_link_target(repo: Path) -> None:
    (repo / "other.md").write_text("o\n")
    _symlink(repo / "link.md", "real.md")
    _git(repo, "add", "link.md", "other.md")
    _git(repo, "commit", "-m", "link")
    (repo / "link.md").unlink()
    _symlink(repo / "link.md", "other.md")
    (repo / "real.md").write_text("base\nWIP\n")
    _commit(repo, repo / "link.md")
    assert _git(repo, "show", "HEAD:link.md") == "other.md"
    assert _git(repo, "show", "HEAD", "--name-only", "--format=").split() == ["link.md"]
    assert "+WIP" in _git(repo, "diff", "HEAD", "--", "real.md")


def test_relative_symlink_path_commits_the_link(repo: Path) -> None:
    _symlink(repo / "link.md", "real.md")
    _commit(repo, Path("link.md"))
    assert _git(repo, "ls-tree", "HEAD", "link.md").startswith("120000 ")


def test_looping_absolute_path_is_refused_as_a_runtime_error(repo: Path) -> None:
    _symlink(repo / "a", "b")
    _symlink(repo / "b", "a")
    head = _git(repo, "rev-parse", "HEAD")
    index = _git(repo, "ls-files", "-s")
    with pytest.raises(RuntimeError) as ei:
        _commit(repo, repo / "a")
    assert isinstance(ei.value, SafeCommitError)
    assert ei.value.error_code == "SAFE_COMMIT_PATH_LOOP"
    assert str(repo / "a") in str(ei.value)
    assert _git(repo, "rev-parse", "HEAD") == head
    assert _git(repo, "ls-files", "-s") == index


def test_expected_path_bytes_accepts_a_link_path(repo: Path) -> None:
    _symlink(repo / "link.md", "real.md")
    head = _git(repo, "rev-parse", "HEAD").strip()
    _commit(
        repo,
        repo / "link.md",
        expected_parent_sha=head,
        expected_path_bytes={repo / "link.md": b"real.md"},
    )
    assert _git(repo, "ls-tree", "HEAD", "link.md").startswith("120000 ")


def test_batch_stage_failure_names_the_path_and_gits_reason(repo: Path) -> None:
    (repo / "ok.md").write_text("ok\n")
    with pytest.raises(RuntimeError) as ei:
        _commit(repo, repo / "ok.md", Path("missing.md"))
    msg = str(ei.value)
    assert msg.startswith("safe_commit: failed to stage requested files in ")
    detail = msg.split(str(repo) + ": ", 1)[1]
    assert "missing.md" in detail
    assert "did not match any files" in detail
    assert "ok.md" not in detail
    assert _git(repo, "diff", "--cached", "--name-only").strip() == ""
