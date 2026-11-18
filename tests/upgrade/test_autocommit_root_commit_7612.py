"""#7612: the upgrade committer threads the root-commit opt-in and can surface a failure.

``spec-kitty init`` reuses ``commit_touched_checkout`` for its own commit (#7555).
On an unborn branch it passes ``allow_root_commit`` so the commit becomes the root
commit, and ``raise_commit_failure`` so a refused commit is named instead of being
flattened into the generic skip warning.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from specify_cli.upgrade.autocommit import UPGRADE_COMMIT_SKIP_WARNING, capture_upgrade_baseline, commit_touched_checkout

pytestmark = [pytest.mark.git_repo]


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True).stdout


@pytest.fixture
def unborn(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "trunk")
    _git(repo, "config", "user.name", "QA")
    _git(repo, "config", "user.email", "qa@example.invalid")
    _git(repo, "config", "commit.gpgsign", "false")
    return repo


def _write_after_baseline(repo: Path) -> set[str]:
    baseline = capture_upgrade_baseline(repo)
    assert baseline is not None
    (repo / ".kittify").mkdir()
    (repo / ".kittify" / "config.yaml").write_text("vcs: {type: git}\n", encoding="utf-8")
    return baseline


def _reject_commits(repo: Path) -> None:
    hook = repo / ".git" / "hooks" / "pre-commit"
    hook.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    hook.chmod(0o755)


def test_root_commit_lands_with_the_opt_in(unborn: Path) -> None:
    baseline = _write_after_baseline(unborn)

    committed, paths, warning = commit_touched_checkout(unborn, baseline, "1", "1", message="init", allow_root_commit=True)

    assert committed is True
    assert paths == [".kittify/config.yaml"]
    assert warning is None
    assert _git(unborn, "ls-tree", "-r", "--name-only", "HEAD").split() == [".kittify/config.yaml"]


def test_without_the_opt_in_an_unborn_branch_is_skipped_with_the_generic_warning(unborn: Path) -> None:
    baseline = _write_after_baseline(unborn)

    committed, _paths, warning = commit_touched_checkout(unborn, baseline, "1", "1", message="init")

    assert committed is False
    assert warning == UPGRADE_COMMIT_SKIP_WARNING
    assert subprocess.run(["git", "rev-parse", "--verify", "-q", "HEAD"], cwd=unborn, check=False).returncode != 0


def test_raise_commit_failure_surfaces_a_rejecting_hook(unborn: Path) -> None:
    baseline = _write_after_baseline(unborn)
    _reject_commits(unborn)

    with pytest.raises(RuntimeError, match="git commit failed"):
        commit_touched_checkout(unborn, baseline, "1", "1", message="init", allow_root_commit=True, raise_commit_failure=True)


def test_a_rejecting_hook_still_flattens_without_raise_commit_failure(unborn: Path) -> None:
    baseline = _write_after_baseline(unborn)
    _reject_commits(unborn)

    committed, _paths, warning = commit_touched_checkout(unborn, baseline, "1", "1", message="init", allow_root_commit=True)

    assert committed is False
    assert warning == UPGRADE_COMMIT_SKIP_WARNING
