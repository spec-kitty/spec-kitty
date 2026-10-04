"""``StatusSurfaceGuard`` on a real git checkout: the branches a finalize-tasks run rarely reaches (#5641).

``test_finalize_atomicity.py`` drives the guard through the real ``finalize-tasks``
command on every topology. These tests pin the refusal and reporting branches
that a whole run reaches only under races or git failures: an unguardable
surface, a branch moved by someone else, a refused compare-and-swap, and an
index that cannot be restored.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from specify_cli.cli.commands.agent.finalize_status_surface import StatusSurfaceGuard
from specify_cli.git.ref_advance import RefRestoreError

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.non_sandbox]


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture
def checkout(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "kitty-specs" / "m").mkdir(parents=True)
    _git(repo.parent, "init", "-q", "-b", "work", str(repo))
    _git(repo, "config", "user.email", "guard@example.com")
    _git(repo, "config", "user.name", "Guard")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "kitty-specs" / "m" / "status.events.jsonl").write_text("", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "base")
    return repo


def _seed(repo: Path, message: str) -> None:
    """One status commit, shaped like the writer's: an appended event in the Mission's event log."""
    events = repo / "kitty-specs" / "m" / "status.events.jsonl"
    events.write_text(events.read_text(encoding="utf-8") + f'{{"event":"{message}"}}\n', encoding="utf-8")
    _git(repo, "commit", "-q", "-am", message)


def _captured(repo: Path) -> StatusSurfaceGuard:
    guard = StatusSurfaceGuard()
    guard.capture(repo / "kitty-specs" / "m", None)
    return guard


def test_a_detached_head_is_not_guarded_and_never_touched(checkout: Path) -> None:
    _git(checkout, "checkout", "-q", "--detach")
    guard = _captured(checkout)
    with guard.recording():
        _seed(checkout, "seed WP01")
    head = _git(checkout, "rev-parse", "HEAD")

    assert guard.restore() is None
    assert _git(checkout, "rev-parse", "HEAD") == head


def test_a_branch_moved_by_someone_else_is_left_and_only_this_runs_commits_are_named(checkout: Path) -> None:
    guard = _captured(checkout)
    with guard.recording():
        _seed(checkout, "seed WP01")
    _seed(checkout, "foreign")
    tip = _git(checkout, "rev-parse", "HEAD")

    leftover = guard.restore()

    assert leftover is not None
    assert _git(checkout, "rev-parse", "HEAD") == tip
    assert [c.split(" ", 1)[1] for c in leftover.commits] == ["seed WP01"]
    assert "work" in leftover.lines()[0]
    assert not guard.is_at_tip_before()


def test_a_refused_compare_and_swap_is_reported_not_retried(checkout: Path) -> None:
    guard = _captured(checkout)
    with guard.recording():
        _seed(checkout, "seed WP01")

    with patch(
        "specify_cli.cli.commands.agent.finalize_status_surface.restore_branch_ref",
        side_effect=RefRestoreError("ref moved under us"),
    ) as restore_branch_ref:
        leftover = guard.restore()

    assert leftover is not None
    assert leftover.reason == "ref moved under us"
    restore_branch_ref.assert_called_once()


def test_an_index_that_cannot_be_restored_names_the_repair(checkout: Path) -> None:
    before = _git(checkout, "rev-parse", "HEAD")
    guard = _captured(checkout)
    with guard.recording():
        _seed(checkout, "seed WP01")
    guard.index_tree = "0" * 40  # an object that does not exist: read-tree fails

    leftover = guard.restore()

    assert leftover is not None
    assert leftover.commits == ()
    assert f"read-tree {'0' * 40}" in leftover.reason
    assert _git(checkout, "rev-parse", "HEAD") == before
    assert guard.is_at_tip_before()


def test_an_unreadable_last_tip_is_reported_not_silently_dropped(checkout: Path) -> None:
    guard = _captured(checkout)
    with guard.recording():
        _seed(checkout, "seed WP01")
    tip = _git(checkout, "rev-parse", "HEAD")
    guard.tip_after = None  # the rev-parse that closes the window failed

    leftover = guard.restore()

    assert leftover is not None
    assert leftover.commits == ()
    assert "could not be read" in leftover.reason
    assert leftover.as_payload()["warning"] == "status_commits_not_undone"
    assert _git(checkout, "rev-parse", "HEAD") == tip
