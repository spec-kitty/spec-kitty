"""#5931: a ``safe_commit`` inside an advance-intent span reports its move before the ref moves.

A consolidation rollback span installs ``reporting_advance_intents``. Its own coordination
commits (the per-WP ``status transition`` commits) went through ``safe_commit``'s porcelain
``git commit``, which moved the branch with no intent, so a kill before the phase recorded its
post tip left the run's own commit unexplained. Inside a span ``safe_commit`` now commits through
its expected-parent mode against the live destination tip: the sink sees ``(branch, old, new)``
while the ref is still at ``old``, and the compare-and-swap fails closed on a concurrent move.
Outside a span nothing changes (NFR-002).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from specify_cli.git import commit_helpers
from specify_cli.git.commit_helpers import (
    SafeCommitDestinationNotFound,
    SafeCommitStagedTreeUnchanged,
    safe_commit,
)
from specify_cli.git.ref_advance import advance_intents_reported, reporting_advance_intents

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_BRANCH = "kitty/mission-5931-in-span"
_MESSAGE = "chore(spec-kitty): status transition WP01"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True).stdout.strip()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q", "-b", _BRANCH)
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "user.name", "Test User")
    _git(root, "config", "commit.gpgsign", "false")
    (root / "status.json").write_text("{}\n", encoding="utf-8")
    (root / "other.txt").write_text("other\n", encoding="utf-8")
    _git(root, "add", "status.json", "other.txt")
    _git(root, "commit", "-q", "-m", "seed")
    return root


def _tip(repo: Path) -> str:
    return _git(repo, "rev-parse", f"refs/heads/{_BRANCH}")


def _commit_status(repo: Path, content: str = '{"WP01": "done"}\n') -> commit_helpers.CommitResult:
    (repo / "status.json").write_text(content, encoding="utf-8")
    return safe_commit(repo_root=repo, worktree_root=repo, destination_ref=_BRANCH, message=_MESSAGE, paths=(repo / "status.json",))


def test_advance_intents_reported_only_inside_a_span() -> None:
    assert advance_intents_reported() is False
    with reporting_advance_intents(lambda *_: None):
        assert advance_intents_reported() is True
    assert advance_intents_reported() is False


def test_in_span_commit_reports_its_intent_before_the_ref_moves(repo: Path) -> None:
    before = _tip(repo)
    seen: list[tuple[str, str, str, str]] = []

    def sink(branch: str, old: str, new: str) -> None:
        seen.append((branch, old, new, _tip(repo)))

    with reporting_advance_intents(sink):
        result = _commit_status(repo)

    assert seen == [(_BRANCH, before, result.sha, before)]
    assert _tip(repo) == result.sha
    assert _git(repo, "rev-parse", "HEAD") == result.sha
    assert _git(repo, "rev-parse", f"{result.sha}^") == before
    assert _git(repo, "log", "-1", "--format=%s", result.sha) == _MESSAGE
    assert _git(repo, "diff", "--cached", "--name-only", "HEAD", "--", "status.json") == ""
    assert _git(repo, "status", "--porcelain") == ""


def test_in_span_commit_keeps_unrelated_staged_content_out_and_staged(repo: Path) -> None:
    (repo / "other.txt").write_text("operator edit\n", encoding="utf-8")
    _git(repo, "add", "other.txt")

    with reporting_advance_intents(lambda *_: None):
        result = _commit_status(repo)

    assert _git(repo, "show", "--name-only", "--pretty=format:", result.sha) == "status.json"
    assert _git(repo, "diff", "--cached", "--name-only") == "other.txt"


def test_in_span_commit_stays_unsigned_like_the_porcelain_path(repo: Path) -> None:
    _git(repo, "config", "commit.gpgsign", "true")
    _git(repo, "config", "gpg.program", "false")  # any signing attempt fails

    with reporting_advance_intents(lambda *_: None):
        result = _commit_status(repo)

    assert _tip(repo) == result.sha


def test_in_span_unchanged_content_is_the_benign_no_op(repo: Path) -> None:
    before = _tip(repo)
    seen: list[tuple[str, str, str]] = []

    with reporting_advance_intents(lambda *args: seen.append(args)), pytest.raises(SafeCommitStagedTreeUnchanged):
        _commit_status(repo, "{}\n")

    assert seen == []
    assert _tip(repo) == before


def test_in_span_concurrent_move_between_read_and_cas_fails_closed(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    foreign: list[str] = []
    create = commit_helpers._create_expected_parent_commit

    def create_then_race(worktree_root: Path, tree_sha: str, parent: str, message_file: Path, **kwargs: bool) -> str:
        new_sha = create(worktree_root, tree_sha, parent, message_file, **kwargs)
        racer = _git(repo, "commit-tree", f"{parent}^{{tree}}", "-p", parent, "-m", "foreign")
        _git(repo, "update-ref", f"refs/heads/{_BRANCH}", racer, parent)
        foreign.append(racer)
        return new_sha

    monkeypatch.setattr(commit_helpers, "_create_expected_parent_commit", create_then_race)

    with reporting_advance_intents(lambda *_: None), pytest.raises(RuntimeError, match="conditional advance"):
        _commit_status(repo)

    assert foreign and _tip(repo) == foreign[0]


def test_outside_a_span_the_porcelain_path_commits(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(**_: object) -> commit_helpers.CommitResult:
        raise AssertionError("the expected-parent mode must not run outside a span")

    monkeypatch.setattr(commit_helpers, "_safe_commit_with_expected_parent", forbidden)
    before = _tip(repo)

    result = _commit_status(repo)

    assert _tip(repo) == result.sha
    assert _git(repo, "rev-parse", f"{result.sha}^") == before
    assert _git(repo, "reflog", "-1", "--format=%gs", _BRANCH) == f"commit: {_MESSAGE}"


def test_in_span_parent_refuses_a_destination_that_does_not_resolve(repo: Path) -> None:
    assert commit_helpers._in_span_parent(repo, "kitty/absent") is None
    with reporting_advance_intents(lambda *_: None), pytest.raises(SafeCommitDestinationNotFound):
        commit_helpers._in_span_parent(repo, "kitty/absent")


def test_expected_path_bytes_without_a_parent_still_refuses_inside_a_span(repo: Path) -> None:
    (repo / "status.json").write_text("x\n", encoding="utf-8")
    with reporting_advance_intents(lambda *_: None), pytest.raises(ValueError, match="requires expected_parent_sha"):
        safe_commit(
            repo_root=repo,
            worktree_root=repo,
            destination_ref=_BRANCH,
            message=_MESSAGE,
            paths=(repo / "status.json",),
            expected_path_bytes={repo / "status.json": b"x\n"},
        )
