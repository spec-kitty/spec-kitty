"""The coordination-branch ref reader is typed (FR-004, ADR 2026-11-06-2 "Ref reader").

An absent file on a readable ref is an empty history (``RefRead.ABSENT``); a missing or
unreadable ref, a missing object or any git failure raises ``StatusSurfaceRefUnreadable``
(``STATUS_SURFACE_REF_UNREADABLE``). Before this, ``read_event_log`` returned ``[]`` on any
``git show`` failure, so a broken ref read as genesis.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from specify_cli.coordination import status_service
from specify_cli.coordination.status_service import (
    STATUS_SURFACE_REF_UNREADABLE,
    EventLogReadContract,
    RefRead,
    StatusSurfaceRefUnreadable,
    read_event_log,
    read_event_stream_log,
    read_status_ref,
    ref_names_object,
)

pytestmark = [pytest.mark.git_repo]

MISSION = "refread-01KXREFR"
BRANCH = "kitty/mission-refread-01KXREFR"
BRANCH_REF = f"refs/heads/{BRANCH}"
LOG_PATH = f"kitty-specs/{MISSION}/status.events.jsonl"

_EVENT = {
    "actor": "ref-reader",
    "at": "2026-11-06T00:00:00+00:00",
    "event_id": "01KXREFR0000000000000000001",
    "evidence": None,
    "execution_mode": "worktree",
    "feature_slug": MISSION,
    "force": False,
    "from_lane": "planned",
    "reason": None,
    "review_ref": None,
    "to_lane": "claimed",
    "wp_id": "WP01",
}


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    """A repository whose coordination branch holds one committed status event."""
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "ref@example.invalid")
    _git(root, "config", "user.name", "Ref")
    _git(root, "config", "commit.gpgsign", "false")
    (root / "README.md").write_text("ref reader\n", encoding="utf-8")
    _git(root, "add", ".")
    _git(root, "commit", "-q", "-m", "root")
    _git(root, "checkout", "-q", "-b", BRANCH)
    log = root / LOG_PATH
    log.parent.mkdir(parents=True)
    log.write_text(json.dumps(_EVENT, sort_keys=True) + "\n", encoding="utf-8")
    _git(root, "add", ".")
    _git(root, "commit", "-q", "-m", "coordination log")
    _git(root, "checkout", "-q", "main")
    return root


def _contract(repo: Path, ref: str, mission: str = MISSION) -> EventLogReadContract:
    mission_dir = repo / "kitty-specs" / mission
    return EventLogReadContract.coordination_branch_ref(
        repo_root=repo,
        destination_ref=ref,
        feature_dir=mission_dir,
        parser_feature_dir=mission_dir,
    )


def test_ref_reader_present_file_reads_its_bytes(repo: Path) -> None:
    """Positive control: a readable ref with the log returns its bytes and its events."""
    result = read_status_ref(repo, BRANCH_REF, LOG_PATH)

    assert not result.absent
    assert result.data is not None
    assert b"01KXREFR0000000000000000001" in result.data
    assert [event.event_id for event in read_event_log(_contract(repo, BRANCH_REF))] == ["01KXREFR0000000000000000001"]
    assert len(read_event_stream_log(_contract(repo, BRANCH)).transitions) == 1


def test_ref_reader_absent_file_reads_empty(repo: Path) -> None:
    """A readable ref without the log is ABSENT, which reads as an empty history."""
    absent_path = "kitty-specs/other-01KXREFR/status.events.jsonl"

    assert read_status_ref(repo, BRANCH_REF, absent_path) is RefRead.ABSENT
    assert read_event_log(_contract(repo, BRANCH_REF, mission="other-01KXREFR")) == []
    assert read_event_stream_log(_contract(repo, BRANCH_REF, mission="other-01KXREFR")).transitions == []


@pytest.mark.parametrize("ref", ["refs/heads/kitty/mission-deleted", "no-such-branch", "--output=injected.txt"])
def test_ref_reader_bad_ref_raises_typed_error(repo: Path, ref: str) -> None:
    """A missing ref (and a ``-``-prefixed name, which is never an option) raises the typed error."""
    with pytest.raises(StatusSurfaceRefUnreadable) as excinfo:
        read_status_ref(repo, ref, LOG_PATH)
    assert excinfo.value.error_code == STATUS_SURFACE_REF_UNREADABLE == "STATUS_SURFACE_REF_UNREADABLE"

    with pytest.raises(StatusSurfaceRefUnreadable):
        read_event_log(_contract(repo, ref))
    with pytest.raises(StatusSurfaceRefUnreadable):
        read_event_stream_log(_contract(repo, ref))


def test_ref_reader_corrupt_ref_raises_typed_error(repo: Path) -> None:
    """A ref that points at an object the repository does not have raises, never reads as genesis."""
    corrupt = repo / ".git" / "refs" / "heads" / "kitty" / "mission-corrupt"
    corrupt.parent.mkdir(parents=True, exist_ok=True)
    corrupt.write_text("0123456789abcdef0123456789abcdef01234567\n", encoding="utf-8")

    with pytest.raises(StatusSurfaceRefUnreadable):
        read_event_log(_contract(repo, "refs/heads/kitty/mission-corrupt"))


def test_ref_reader_git_failure_raises(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A git failure (non-zero exit, or git missing) raises the typed error."""

    def _failing(*_args: Any, **_kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        return subprocess.CompletedProcess(args=["git"], returncode=128, stdout=b"", stderr=b"fatal: broken")

    monkeypatch.setattr(status_service.subprocess, "run", _failing)
    with pytest.raises(StatusSurfaceRefUnreadable):
        read_event_log(_contract(repo, BRANCH_REF))

    def _missing_git(*_args: Any, **_kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        raise FileNotFoundError("git")

    monkeypatch.setattr(status_service.subprocess, "run", _missing_git)
    with pytest.raises(StatusSurfaceRefUnreadable):
        read_status_ref(repo, BRANCH_REF, LOG_PATH)


def test_ref_reader_spawns_one_subprocess_per_read(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """NFR-001: a ref read costs one batched object-read subprocess."""
    calls: list[list[str]] = []
    real_run = subprocess.run

    def _counting(cmd: list[str], *args: Any, **kwargs: Any) -> Any:
        calls.append(cmd)
        return real_run(cmd, *args, **kwargs)

    monkeypatch.setattr(status_service.subprocess, "run", _counting)

    read_event_log(_contract(repo, BRANCH_REF))

    assert len(calls) == 1
    assert "cat-file" in calls[0]


def test_ref_exists_distinguishes_missing_from_unreadable(repo: Path, tmp_path: Path) -> None:
    """``ref_names_object`` is the one home of the declared ref-missing arm (coherence, done bookkeeping).

    It answers only "does the ref resolve to an object name": a corrupt ref still exists (so its
    read raises), while a missing ref or a non-repository root does not.
    """
    corrupt = repo / ".git" / "refs" / "heads" / "kitty" / "mission-corrupt"
    corrupt.parent.mkdir(parents=True, exist_ok=True)
    corrupt.write_text("0123456789abcdef0123456789abcdef01234567\n", encoding="utf-8")
    not_a_repo = tmp_path / "plain"
    not_a_repo.mkdir()

    assert ref_names_object(repo, BRANCH_REF) is True
    assert ref_names_object(repo, "refs/heads/kitty/mission-corrupt") is True
    assert ref_names_object(repo, "refs/heads/kitty/mission-deleted") is False
    assert ref_names_object(repo, "--output=injected.txt") is False
    assert ref_names_object(not_a_repo, BRANCH_REF) is False
