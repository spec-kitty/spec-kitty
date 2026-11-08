"""#7372 / FR-061: the transaction's PRIMARY-target arm commits in a topic holder only for a default Mission.

``BookkeepingTransaction.acquire(commit_to_primary_target=True)`` commits a PRIMARY-partition
group on the caller's ``destination_ref``. Before a default Mission lands that ref is its topic
branch, held by the coordination worktree, so the commit must run there. For every other Mission
the commit stays in the repository root checkout, even when some other checkout (an operator's own
worktree) happens to hold the destination branch. ``primary_partition_checkout`` is stubbed; the
checkouts are a real git repository.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.coordination import planning_commit, transaction
from tests._support.git_cli import git_out

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

_SLUG = "probe-01M6XCQ7"
_TOPIC = "kitty/mission-probe-01M6XCQ7"


@pytest.fixture()
def repo_and_holder(tmp_path: Path) -> tuple[Path, Path]:
    repo = tmp_path / "repo"
    repo.mkdir()
    git_out(repo, "init", "-q", "-b", "work")
    git_out(repo, "config", "user.email", "t@example.com")
    git_out(repo, "config", "user.name", "Test")
    git_out(repo, "config", "commit.gpgsign", "false")
    (repo / "README.md").write_text("x\n", encoding="utf-8")
    git_out(repo, "add", "-A")
    git_out(repo, "commit", "-qm", "init")
    holder = repo / ".worktrees" / f"{_SLUG}-coord"
    git_out(repo, "worktree", "add", "-q", "-b", _TOPIC, str(holder))
    return repo, holder


def test_default_mission_commits_in_the_holder_of_its_topic_branch(repo_and_holder: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    repo, holder = repo_and_holder
    monkeypatch.setattr(planning_commit, "primary_partition_checkout", lambda *_a: holder)
    assert transaction._primary_partition_holder(repo, _SLUG, _TOPIC) == holder


def test_mission_that_is_not_default_keeps_the_root_even_when_another_checkout_holds_the_ref(
    repo_and_holder: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The reviewer's M2 scenario: an operator's own worktree holds the destination branch."""
    repo, _holder = repo_and_holder
    monkeypatch.setattr(planning_commit, "primary_partition_checkout", lambda *_a: None)
    assert transaction._primary_partition_holder(repo, _SLUG, _TOPIC) == repo


def test_holder_that_does_not_hold_the_destination_keeps_the_root(repo_and_holder: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    """After the landing the PRIMARY ref is the target, held by the root: the holder is never used for it."""
    repo, holder = repo_and_holder
    monkeypatch.setattr(planning_commit, "primary_partition_checkout", lambda *_a: holder)
    assert transaction._primary_partition_holder(repo, _SLUG, "work") == repo
