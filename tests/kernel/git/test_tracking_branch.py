"""Unit tests for ``kernel.git.tracking_branch`` (#7806): one owning-remote rule, refs only.

Real git repositories, no network: a tracking ref is planted with ``update-ref``
so every arm is a local read or a local branch write.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from kernel.git import tracking_branch
from kernel.git.runner import GitCommandError
from kernel.git.tracking_branch import ensure_local_tracking_branch, is_local_head, owning_tracking_ref

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

_BRANCH = "kitty/mission-demo-lane-a"


def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(repo), *args], check=check, capture_output=True, text=True)


def _plant(repo: Path, remote: str, branch: str = _BRANCH) -> str:
    """Add *remote* (unreachable URL, never contacted) and point its tracking ref at HEAD."""
    _git(repo, "remote", "add", remote, str(repo.parent / f"{remote}.git"))
    head = _git(repo, "rev-parse", "HEAD").stdout.strip()
    _git(repo, "update-ref", f"refs/remotes/{remote}/{branch}", head)
    return head


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    for key, value in (("user.name", "T"), ("user.email", "t@example.com"), ("commit.gpgsign", "false")):
        _git(root, "config", key, value)
    (root / "a.txt").write_text("a\n", encoding="utf-8")
    _git(root, "add", "a.txt")
    _git(root, "commit", "-q", "-m", "base")
    return root


def _upstream(repo: Path) -> str:
    return _git(repo, "rev-parse", "--abbrev-ref", f"{_BRANCH}@{{upstream}}", check=False).stdout.strip()


# --- owning_tracking_ref ---------------------------------------------------------


def test_no_remote_resolves_nothing(repo: Path) -> None:
    assert owning_tracking_ref(repo, _BRANCH) is None


def test_single_remote_owns_the_branch(repo: Path) -> None:
    _plant(repo, "upstream")
    assert owning_tracking_ref(repo, _BRANCH) == f"refs/remotes/upstream/{_BRANCH}"


def test_branch_remote_config_wins_over_origin(repo: Path) -> None:
    _plant(repo, "origin")
    _plant(repo, "fork")
    _git(repo, "config", f"branch.{_BRANCH}.remote", "fork")
    assert owning_tracking_ref(repo, _BRANCH) == f"refs/remotes/fork/{_BRANCH}"


def test_several_remotes_without_origin_resolve_none(repo: Path) -> None:
    _plant(repo, "alpha")
    _plant(repo, "beta")
    assert owning_tracking_ref(repo, _BRANCH) is None


def test_fallback_remote_applies_only_without_an_owner(repo: Path) -> None:
    _plant(repo, "alpha")
    _plant(repo, "beta")
    _git(repo, "update-ref", f"refs/remotes/origin/{_BRANCH}", "HEAD")
    assert owning_tracking_ref(repo, _BRANCH, fallback_remote="origin") == f"refs/remotes/origin/{_BRANCH}"


def test_owner_without_a_tracking_ref_is_none(repo: Path) -> None:
    _plant(repo, "origin", branch="other")
    assert owning_tracking_ref(repo, _BRANCH) is None


def test_unreadable_owner_is_none(repo: Path) -> None:
    def _boom(*_a: object) -> str:
        raise OSError("git missing")

    assert owning_tracking_ref(repo, _BRANCH, remote_resolver=_boom) is None


def test_probe_that_cannot_run_is_none(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def _no_git(*_a: object, **_k: object) -> object:
        raise GitCommandError(argv=("rev-parse",), cwd=repo, returncode=-1, stderr="git missing")

    monkeypatch.setattr(tracking_branch, "run_git", _no_git)
    assert owning_tracking_ref(repo, _BRANCH, remote_resolver=lambda *_a: "origin") is None


# --- is_local_head ---------------------------------------------------------------


def test_is_local_head(repo: Path) -> None:
    assert is_local_head(repo, "main") is True
    assert is_local_head(repo, _BRANCH) is False


def test_is_local_head_fails_closed_outside_a_repository(tmp_path: Path) -> None:
    assert is_local_head(tmp_path / "missing", "main") is False


# --- ensure_local_tracking_branch ------------------------------------------------


def test_ensure_creates_a_tracking_branch_from_the_owning_remote(repo: Path) -> None:
    head = _plant(repo, "origin")

    assert ensure_local_tracking_branch(repo, _BRANCH) is True

    assert _git(repo, "rev-parse", f"refs/heads/{_BRANCH}").stdout.strip() == head
    assert _upstream(repo) == f"origin/{_BRANCH}"


def test_ensure_sets_upstream_without_git_autosetup(repo: Path) -> None:
    _plant(repo, "origin")
    _git(repo, "config", "branch.autoSetupMerge", "false")

    assert ensure_local_tracking_branch(repo, _BRANCH) is True
    assert _upstream(repo) == f"origin/{_BRANCH}"


def test_ensure_leaves_an_existing_local_head_alone(repo: Path) -> None:
    _plant(repo, "origin")
    _git(repo, "branch", "--no-track", _BRANCH, "main")

    assert ensure_local_tracking_branch(repo, _BRANCH) is True
    assert _git(repo, "config", f"branch.{_BRANCH}.remote", check=False).returncode != 0


def test_ensure_writes_nothing_without_a_tracking_ref(repo: Path) -> None:
    assert ensure_local_tracking_branch(repo, _BRANCH) is False
    assert is_local_head(repo, _BRANCH) is False


def test_ensure_never_picks_a_remote_for_an_ambiguous_owner(repo: Path) -> None:
    _plant(repo, "alpha")
    _plant(repo, "beta")

    assert ensure_local_tracking_branch(repo, _BRANCH) is False
    assert is_local_head(repo, _BRANCH) is False


def test_ensure_tolerates_a_concurrent_creation(repo: Path) -> None:
    _plant(repo, "origin")
    calls = {"n": 0}

    def _first_miss(root: Path, branch: str) -> bool:
        calls["n"] += 1
        if calls["n"] == 1:
            _git(root, "branch", "--no-track", branch, f"refs/remotes/origin/{branch}")  # the concurrent writer
            return False
        return is_local_head(root, branch)

    assert ensure_local_tracking_branch(repo, _BRANCH, local_head=_first_miss) is True
    assert calls["n"] == 2


def test_ensure_false_when_the_branch_command_cannot_run(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def _no_git(*_a: object, **_k: object) -> object:
        raise GitCommandError(argv=("branch",), cwd=repo, returncode=-1, stderr="git missing")

    monkeypatch.setattr(tracking_branch, "run_git", _no_git)
    assert ensure_local_tracking_branch(repo, _BRANCH, start_ref=lambda *_a: "refs/remotes/origin/x", local_head=lambda *_a: False) is False
