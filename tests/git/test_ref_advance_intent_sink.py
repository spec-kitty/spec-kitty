"""Advance-intent sink of :mod:`specify_cli.git.ref_advance` (WP06 / FR-006 / C-006).

``advance_branch_ref`` and ``advance_branch_ref_for_commit`` report every
advance they are about to write, as ``(branch, old_sha, new_sha)``, to the sink
installed with :func:`reporting_advance_intents`. The report happens after the
fast-forward, checkout and dirty checks and strictly BEFORE the compare-and-swap
``update-ref``; ``old_sha`` is the CAS old value actually handed to git. A
raising sink fails the advance closed. ``restore_branch_ref`` never reports.

Real-git tests over throwaway temp repositories; nothing in git is mocked.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from specify_cli.git.ref_advance import (
    RefAdvanceDirtyWorktreeError,
    RefAdvanceError,
    advance_branch_ref,
    advance_branch_ref_for_commit,
    reporting_advance_intents,
    restore_branch_ref,
)

pytestmark = [pytest.mark.git_repo, pytest.mark.non_sandbox]


class _SinkError(RuntimeError):
    """Raised by a test sink to prove the advance fails closed."""


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True)
    return result.stdout.strip()


def _commit(repo: Path, name: str, content: str) -> str:
    (repo / name).write_text(content, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", f"write {name}")
    return _git(repo, "rev-parse", "HEAD")


class _Repo:
    """A repository whose ``develop`` holds base -> c1 -> c2 and whose ``feat`` sits at base in a linked worktree."""

    def __init__(self, tmp_path: Path) -> None:
        self.root = tmp_path / "repo"
        self.root.mkdir()
        subprocess.run(["git", "init", "-qb", "develop", str(self.root)], check=True)
        for key, value in (("user.email", "t@t.com"), ("user.name", "T"), ("commit.gpgsign", "false")):
            _git(self.root, "config", key, value)
        self.base = _commit(self.root, "a.txt", "base\n")
        self.c1 = _commit(self.root, "a.txt", "one\n")
        self.c2 = _commit(self.root, "a.txt", "two\n")
        _git(self.root, "branch", "feat", self.base)
        self.linked = tmp_path / "linked"
        _git(self.root, "worktree", "add", "-q", str(self.linked), "feat")

    def tip(self, branch: str = "feat") -> str:
        return _git(self.root, "rev-parse", f"refs/heads/{branch}")


@pytest.fixture
def repo(tmp_path: Path) -> _Repo:
    return _Repo(tmp_path)


def test_sink_is_called_once_with_the_cas_pair_before_the_write(repo: _Repo) -> None:
    calls: list[tuple[str, str, str]] = []

    def sink(branch: str, old: str, new: str) -> None:
        assert repo.tip(branch) == old, "the sink runs strictly before the compare-and-swap write"
        calls.append((branch, old, new))

    with reporting_advance_intents(sink):
        advance_branch_ref(repo.root, "feat", repo.c1)

    assert calls == [("feat", repo.base, repo.c1)]
    assert repo.tip() == repo.c1
    assert (repo.linked / "a.txt").read_text() == "one\n"


def test_raising_sink_leaves_ref_and_checkout_unmoved(repo: _Repo) -> None:
    def sink(branch: str, old: str, new: str) -> None:
        raise _SinkError("could not persist the intent")

    with reporting_advance_intents(sink), pytest.raises(_SinkError):
        advance_branch_ref(repo.root, "feat", repo.c1)

    assert repo.tip() == repo.base
    assert _git(repo.linked, "rev-parse", "HEAD") == repo.base
    assert (repo.linked / "a.txt").read_text() == "base\n"


def test_without_a_sink_the_advance_is_unchanged(repo: _Repo) -> None:
    advance_branch_ref(repo.root, "feat", repo.c1)

    assert repo.tip() == repo.c1
    assert _git(repo.linked, "status", "--porcelain") == ""


def test_dirty_checkout_refusal_happens_before_the_sink(repo: _Repo) -> None:
    calls: list[tuple[str, str, str]] = []
    (repo.linked / "a.txt").write_text("operator edit\n", encoding="utf-8")

    with reporting_advance_intents(lambda *args: calls.append(args)), pytest.raises(RefAdvanceDirtyWorktreeError):
        advance_branch_ref(repo.root, "feat", repo.c1)

    assert calls == []
    assert repo.tip() == repo.base


def test_cas_mismatch_reports_the_intent_and_git_refuses(repo: _Repo) -> None:
    """The intent exists without a move.

    The sink sees the CAS old value the caller expected (``base``), git refuses
    because the ref is at ``c1``. A recorded intent is therefore not proof of a
    move: the rollback authority adopts an intent only when ``live == intent``.
    """
    advance_branch_ref(repo.root, "feat", repo.c1)  # the ref (and its checkout) moved on
    calls: list[tuple[str, str, str]] = []

    with reporting_advance_intents(lambda *args: calls.append(args)), pytest.raises(RefAdvanceError):
        advance_branch_ref(repo.root, "feat", repo.c2, expected_old_sha=repo.base)

    assert calls == [("feat", repo.base, repo.c2)]
    assert repo.tip() == repo.c1


def test_restore_branch_ref_never_reports(repo: _Repo) -> None:
    advance_branch_ref(repo.root, "feat", repo.c1)
    calls: list[tuple[str, str, str]] = []

    with reporting_advance_intents(lambda *args: calls.append(args)):
        restore_branch_ref(repo.root, "feat", repo.base, expected_current_sha=repo.c1, resync_checkouts=True)

    assert calls == []
    assert repo.tip() == repo.base


def test_advance_for_commit_reports_before_its_write(repo: _Repo) -> None:
    calls: list[tuple[str, str, str]] = []

    def sink(branch: str, old: str, new: str) -> None:
        assert repo.tip(branch) == old
        calls.append((branch, old, new))

    with reporting_advance_intents(sink):
        advance_branch_ref_for_commit(repo.root, repo.linked, "feat", repo.c1, expected_old_sha=repo.base, message="safe commit")

    assert calls == [("feat", repo.base, repo.c1)]
    assert repo.tip() == repo.c1


def test_advance_for_commit_raising_sink_does_not_move(repo: _Repo) -> None:
    def sink(branch: str, old: str, new: str) -> None:
        raise _SinkError("could not persist the intent")

    with reporting_advance_intents(sink), pytest.raises(_SinkError):
        advance_branch_ref_for_commit(repo.root, repo.linked, "feat", repo.c1, expected_old_sha=repo.base, message="safe commit")

    assert repo.tip() == repo.base


def test_sink_is_uninstalled_after_the_block(repo: _Repo) -> None:
    calls: list[tuple[str, str, str]] = []

    with reporting_advance_intents(lambda *args: calls.append(args)):
        pass
    advance_branch_ref(repo.root, "feat", repo.c1)

    assert calls == []


def test_sink_is_uninstalled_after_an_exception_in_the_block(repo: _Repo) -> None:
    calls: list[tuple[str, str, str]] = []

    with pytest.raises(_SinkError), reporting_advance_intents(lambda *args: calls.append(args)):
        raise _SinkError("block failed")
    advance_branch_ref(repo.root, "feat", repo.c1)

    assert calls == []


def test_nested_block_restores_the_outer_sink(repo: _Repo) -> None:
    outer: list[tuple[str, str, str]] = []
    inner: list[tuple[str, str, str]] = []

    with reporting_advance_intents(lambda *args: outer.append(args)):
        with reporting_advance_intents(lambda *args: inner.append(args)):
            advance_branch_ref(repo.root, "feat", repo.c1)
        advance_branch_ref(repo.root, "feat", repo.c2)

    assert inner == [("feat", repo.base, repo.c1)]
    assert outer == [("feat", repo.c1, repo.c2)]
