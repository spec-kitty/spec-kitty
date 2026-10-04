"""#5572 — the status write door refuses a coordination worktree whose log lost committed events."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

import specify_cli.status  # noqa: F401  # import-order guard (coordination -> transaction -> status)
from kernel.git import GitCommandError
from specify_cli.coordination import status_surface_guard
from specify_cli.coordination.status_surface_guard import committed_events_missing_from_worktree
from specify_cli.coordination.transaction_errors import (
    BookkeepingError,
    BookkeepingStatusSurfaceDiverged,
    BookkeepingStatusSurfaceUnreadable,
)

pytestmark = [pytest.mark.git_repo, pytest.mark.non_sandbox]

_REL = "kitty-specs/m-01KXTM73/status.events.jsonl"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def _line(event_id: str) -> str:
    return json.dumps({"event_id": event_id, "wp_id": "WP01", "to_lane": "done"}) + "\n"


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "wt"
    root.mkdir()
    subprocess.run(["git", "init", "-qb", "main", str(root)], check=True, capture_output=True)
    for key, value in (("user.email", "t@t.com"), ("user.name", "T"), ("commit.gpgsign", "false")):
        _git(root, "config", key, value)
    return root


def _commit_log(repo: Path, *ids: str) -> Path:
    path = repo / _REL
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(_line(i) for i in ids), encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "seed")
    return path


def test_clean_tree_has_nothing_missing(repo: Path) -> None:
    path = _commit_log(repo, "A", "B")

    assert committed_events_missing_from_worktree(repo, path) == []


def test_extra_uncommitted_lines_are_not_a_divergence(repo: Path) -> None:
    path = _commit_log(repo, "A")
    path.write_text(path.read_text(encoding="utf-8") + _line("NEW"), encoding="utf-8")

    assert committed_events_missing_from_worktree(repo, path) == []


def test_events_dropped_from_the_working_tree_are_reported_in_order(repo: Path) -> None:
    path = _commit_log(repo, "A", "B", "C")
    path.write_text(_line("A"), encoding="utf-8")

    assert committed_events_missing_from_worktree(repo, path) == ["B", "C"]


def test_a_deleted_log_drops_every_committed_event(repo: Path) -> None:
    path = _commit_log(repo, "A", "B")
    path.unlink()

    assert committed_events_missing_from_worktree(repo, path) == ["A", "B"]


def test_a_log_absent_at_head_has_nothing_to_lose(repo: Path) -> None:
    _git(repo, "commit", "-q", "--allow-empty", "-m", "empty")

    assert committed_events_missing_from_worktree(repo, repo / _REL) == []


def test_a_path_outside_the_worktree_is_ignored(repo: Path, tmp_path: Path) -> None:
    _commit_log(repo, "A")

    assert committed_events_missing_from_worktree(repo, tmp_path / "elsewhere.jsonl") == []


def test_a_torn_trailing_line_in_the_working_tree_is_tolerated(repo: Path) -> None:
    """An interrupted append leaves a partial last line; the truncate rollback owns it, not this guard."""
    path = _commit_log(repo, "A", "B")
    path.write_text(path.read_text(encoding="utf-8") + '{"event_id": "C", "wp_', encoding="utf-8")

    assert committed_events_missing_from_worktree(repo, path) == []


def test_noise_in_the_working_tree_never_hides_a_dropped_event(repo: Path) -> None:
    path = _commit_log(repo, "A", "B")
    path.write_text("not json\n[1]\n" + _line("A"), encoding="utf-8")

    assert committed_events_missing_from_worktree(repo, path) == ["B"]


@pytest.mark.parametrize(
    "committed, reason",
    [
        pytest.param(_line("A") + '{"event_id": "B", "wp_\n', "malformed event-log line 2", id="torn-line"),
        pytest.param(_line("A") + "[1]\n", "malformed event-log line 2", id="non-event-line"),
        pytest.param(_line("A") + _line("A"), "duplicate event_id", id="duplicate-id"),
    ],
)
def test_a_malformed_committed_log_is_refused_not_read_as_nothing_missing(repo: Path, committed: str, reason: str) -> None:
    path = repo / _REL
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(committed, encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "garbled")
    path.write_text(_line("A"), encoding="utf-8")

    with pytest.raises(BookkeepingStatusSurfaceUnreadable) as refused:
        committed_events_missing_from_worktree(repo, path)

    assert isinstance(refused.value, BookkeepingError) and refused.value.error_code == "COORD_STATUS_SURFACE_UNREADABLE"
    assert reason in str(refused.value) and "nothing was written" in str(refused.value)


def test_an_unreadable_head_is_refused_not_read_as_an_absent_log(repo: Path) -> None:
    path = _commit_log(repo, "A", "B")
    (repo / ".git" / "refs" / "heads" / "main").write_text("0123456789abcdef0123456789abcdef01234567\n", encoding="utf-8")
    path.write_text(_line("A"), encoding="utf-8")

    with pytest.raises(BookkeepingStatusSurfaceUnreadable) as refused:
        committed_events_missing_from_worktree(repo, path)

    assert "HEAD" in str(refused.value)


def test_a_git_failure_surfaces_as_a_bookkeeping_error(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = _commit_log(repo, "A")

    def _timed_out(cwd: Path, *args: str, **_kwargs: object) -> None:
        raise GitCommandError(argv=args, cwd=cwd, returncode=-1, stderr="timed out after 30 seconds", timed_out=True)

    monkeypatch.setattr(status_surface_guard, "run_git", _timed_out)

    with pytest.raises(BookkeepingStatusSurfaceUnreadable) as refused:
        committed_events_missing_from_worktree(repo, path)

    assert "timed out after 30 seconds" in str(refused.value)
    assert isinstance(refused.value.__cause__, GitCommandError)


def test_the_refusal_names_the_code_the_events_and_the_remedy(repo: Path) -> None:
    path = repo / _REL
    error = BookkeepingStatusSurfaceDiverged(worktree_root=repo, events_path=path, missing_event_ids=["A", "B", "C", "D", "E"])

    text = str(error)
    assert isinstance(error, BookkeepingError) and error.error_code == "COORD_STATUS_SURFACE_DIVERGED"
    assert text.startswith("COORD_STATUS_SURFACE_DIVERGED") and "A, B, C (+2 more)" in text
    assert "doctor coordination --fix" in text
    assert "checkout HEAD -- kitty-specs/m-01KXTM73/status.events.jsonl kitty-specs/m-01KXTM73/status.json" in text
    # WP04 review follow-up: the two remedies are NOT interchangeable -- say which one reverts the strand.
    heals = text[text.index("doctor coordination --fix") :]
    assert "heals the strand AWAY" in text and "reverts the stranded `done`" in text
    assert "KEEPS the committed events" in heals and "stranded `done` stays recorded" in text
