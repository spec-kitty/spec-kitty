"""``auto_rebase._record_review_presync`` in process (#7802): when the pre-sync tip is recorded.

Real git repository; the lane checkout is the repository itself. A sync merge is a
``--no-ff`` merge of a ``mission`` branch; a fast-forward or a plain commit is not a
sync merge and must write nothing (mutation M15).
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

import pytest

from specify_cli.lanes import auto_rebase
from specify_cli.status import review_presync_ref

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

_LANE = "kitty/mission-demo-01ABCDEF-lane-a"
_REF = review_presync_ref(_LANE)


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout.strip()


def _commit(repo: Path, name: str) -> str:
    (repo / name).write_text(f"{name}\n", encoding="utf-8")
    _git(repo, "add", name)
    _git(repo, "commit", "-qm", name)
    return _git(repo, "rev-parse", "HEAD")


def _recorded(repo: Path) -> str | None:
    found = subprocess.run(["git", "-C", str(repo), "rev-parse", "-q", "--verify", _REF], capture_output=True, text=True)
    return found.stdout.strip() if found.returncode == 0 else None


def _sync(repo: Path) -> None:
    """A sync merge: ``mission`` gains a commit and is merged ``--no-ff`` into the lane."""
    _git(repo, "checkout", "-q", "mission")
    _commit(repo, f"mission-{_git(repo, 'rev-list', '--count', 'HEAD')}.txt")
    _git(repo, "checkout", "-q", _LANE)
    _git(repo, "merge", "-q", "--no-ff", "--no-edit", "mission")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    for key, value in (("user.name", "T"), ("user.email", "t@example.com"), ("commit.gpgsign", "false")):
        _git(root, "config", key, value)
    _commit(root, "base.txt")
    _git(root, "branch", "mission")
    _git(root, "checkout", "-q", "-b", _LANE)
    _commit(root, "work.txt")
    return root


def test_a_sync_merge_records_the_pre_merge_tip(repo: Path) -> None:
    pre = _git(repo, "rev-parse", "HEAD")
    _sync(repo)

    auto_rebase._record_review_presync(repo, repo, _LANE, pre)

    assert _recorded(repo) == pre


def test_a_fast_forward_writes_no_presync_ref(repo: Path) -> None:
    """M15: HEAD moved by a non-merge commit (first parent is the pre tip, no second parent)."""
    pre = _git(repo, "rev-parse", "HEAD")
    _commit(repo, "more-work.txt")

    auto_rebase._record_review_presync(repo, repo, _LANE, pre)

    assert _recorded(repo) is None


def test_a_merge_not_on_the_pre_tip_writes_nothing(repo: Path) -> None:
    """The first parent is not the pre-merge tip: the merge is not this sync's."""
    pre = _git(repo, "rev-parse", "HEAD")
    _commit(repo, "between.txt")
    _sync(repo)

    auto_rebase._record_review_presync(repo, repo, _LANE, pre)

    assert _recorded(repo) is None


@pytest.mark.parametrize("pre", [None, "HEAD"])
def test_no_pre_tip_or_a_no_op_merge_writes_nothing(repo: Path, pre: str | None) -> None:
    sha = _git(repo, "rev-parse", "HEAD") if pre else None

    auto_rebase._record_review_presync(repo, repo, _LANE, sha)

    assert _recorded(repo) is None


def test_a_second_sync_keeps_the_first_record(repo: Path) -> None:
    first = _git(repo, "rev-parse", "HEAD")
    _sync(repo)
    auto_rebase._record_review_presync(repo, repo, _LANE, first)
    second = _git(repo, "rev-parse", "HEAD")
    _sync(repo)

    auto_rebase._record_review_presync(repo, repo, _LANE, second)

    assert _recorded(repo) == first


def test_new_work_after_the_record_replaces_it(repo: Path) -> None:
    first = _git(repo, "rev-parse", "HEAD")
    _sync(repo)
    auto_rebase._record_review_presync(repo, repo, _LANE, first)
    reworked = _commit(repo, "rework.txt")
    _sync(repo)

    auto_rebase._record_review_presync(repo, repo, _LANE, reworked)

    assert _recorded(repo) == reworked


def test_a_failed_write_is_logged_and_never_raises(repo: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    pre = _git(repo, "rev-parse", "HEAD")
    _sync(repo)
    monkeypatch.setattr(auto_rebase, "write_bookkeeping_ref", lambda *_a, **_k: False)

    with caplog.at_level(logging.DEBUG, logger=auto_rebase._LOG.name):
        auto_rebase._record_review_presync(repo, repo, _LANE, pre)

    assert _recorded(repo) is None
    assert "could not record the review pre-sync tip" in caplog.text


def test_head_sha_of_an_unborn_checkout_is_none(tmp_path: Path) -> None:
    _git(tmp_path, "init", "-q")
    assert auto_rebase._head_sha(tmp_path) is None
