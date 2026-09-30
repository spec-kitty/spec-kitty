"""Unit tests for :func:`mission_runtime.claim_commit_for_wp` (FR-025, T065).

Real git repositories and real ``status.events.jsonl`` files (written through
the status store), never mocks of the algorithm; the two failure-translation
rows inject the ``subprocess`` outcome because a real hung or crashing git is
not reproducible on demand.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest

from mission_runtime import ClaimCommitUnresolved, claim_commit_for_wp
from specify_cli.status.models import Lane, StatusEvent
from specify_cli.status.store import append_event

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

_SLUG = "claim-01M3M2ZB"
_EVENTS = "status.events.jsonl"


def _git(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True, encoding="utf-8").stdout.strip()


@pytest.fixture
def mission_dir(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "user.email", "test@example.invalid")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "seed.txt").write_text("seed\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "seed")
    directory = repo / "kitty-specs" / _SLUG
    directory.mkdir(parents=True)
    return directory


def _event(event_id: str, wp_id: str, to_lane: Lane, from_lane: Lane = Lane.PLANNED) -> StatusEvent:
    return StatusEvent(
        event_id=event_id,
        mission_slug=_SLUG,
        wp_id=wp_id,
        from_lane=from_lane,
        to_lane=to_lane,
        at="2026-09-29T00:00:00+00:00",
        actor="tester",
        force=True,
        execution_mode="direct_repo",
    )


def _record(directory: Path, event: StatusEvent, *, commit: bool = True) -> str | None:
    """Append ``event`` and (by default) commit it in its own event-only commit."""
    append_event(directory, event)
    if not commit:
        return None
    repo = directory.parents[1]
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", f"status {event.event_id}")
    return _git(repo, "rev-parse", "HEAD")


def test_single_claim_returns_its_commit(mission_dir: Path) -> None:
    sha = _record(mission_dir, _event("01CLAIMAAAAAAAAAAAAAAAAAA1", "WP01", Lane.CLAIMED))
    _record(mission_dir, _event("01PROGRESSAAAAAAAAAAAAAAA1", "WP01", Lane.IN_PROGRESS, Lane.CLAIMED))

    assert claim_commit_for_wp(mission_dir, "WP01") == sha


def test_last_claim_wins_after_a_rejection(mission_dir: Path) -> None:
    _record(mission_dir, _event("01CLAIMAAAAAAAAAAAAAAAAAA1", "WP01", Lane.CLAIMED))
    _record(mission_dir, _event("01PLANNEDAAAAAAAAAAAAAAAA1", "WP01", Lane.PLANNED, Lane.FOR_REVIEW))
    second = _record(mission_dir, _event("01CLAIMAAAAAAAAAAAAAAAAAA2", "WP01", Lane.CLAIMED))

    assert claim_commit_for_wp(mission_dir, "WP01") == second


def test_other_work_packages_claims_are_ignored(mission_dir: Path) -> None:
    mine = _record(mission_dir, _event("01CLAIMAAAAAAAAAAAAAAAAAA1", "WP01", Lane.CLAIMED))
    _record(mission_dir, _event("01CLAIMBBBBBBBBBBBBBBBBBB1", "WP02", Lane.CLAIMED))

    assert claim_commit_for_wp(mission_dir, "WP01") == mine


def test_no_claim_event_fails_closed(mission_dir: Path) -> None:
    _record(mission_dir, _event("01PROGRESSAAAAAAAAAAAAAAA1", "WP01", Lane.IN_PROGRESS, Lane.CLAIMED))

    with pytest.raises(ClaimCommitUnresolved) as raised:
        claim_commit_for_wp(mission_dir, "WP01")

    assert raised.value.reason == "no_claim_event"
    assert raised.value.wp_id == "WP01"


def test_claim_event_on_no_commit_fails_closed(mission_dir: Path) -> None:
    _record(mission_dir, _event("01PROGRESSAAAAAAAAAAAAAAA1", "WP01", Lane.IN_PROGRESS, Lane.CLAIMED))
    _record(mission_dir, _event("01CLAIMAAAAAAAAAAAAAAAAAA1", "WP01", Lane.CLAIMED), commit=False)

    with pytest.raises(ClaimCommitUnresolved) as raised:
        claim_commit_for_wp(mission_dir, "WP01")

    assert raised.value.reason == "no_commit"


def test_two_commits_introducing_the_claim_fail_closed(mission_dir: Path) -> None:
    claim = _event("01CLAIMAAAAAAAAAAAAAAAAAA1", "WP01", Lane.CLAIMED)
    _record(mission_dir, claim)
    events = mission_dir / _EVENTS
    original = events.read_text(encoding="utf-8")
    events.write_text("", encoding="utf-8")
    _git(mission_dir.parents[1], "commit", "-qam", "remove the claim line")
    events.write_text(original, encoding="utf-8")
    _git(mission_dir.parents[1], "commit", "-qam", "re-add the claim line")

    with pytest.raises(ClaimCommitUnresolved) as raised:
        claim_commit_for_wp(mission_dir, "WP01")

    assert raised.value.reason == "ambiguous"


def test_directory_outside_any_repository_is_git_unavailable(tmp_path: Path) -> None:
    lonely = tmp_path / "not-a-repo" / "mission"
    lonely.mkdir(parents=True)
    _record(lonely, _event("01CLAIMAAAAAAAAAAAAAAAAAA1", "WP01", Lane.CLAIMED), commit=False)

    with pytest.raises(ClaimCommitUnresolved) as raised:
        claim_commit_for_wp(lonely, "WP01")

    assert raised.value.reason == "git_unavailable"


def test_git_timeout_is_git_unavailable(mission_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _record(mission_dir, _event("01CLAIMAAAAAAAAAAAAAAAAAA1", "WP01", Lane.CLAIMED))

    def _hang(*args: object, **kwargs: object) -> object:
        raise subprocess.TimeoutExpired(cmd="git", timeout=1)

    monkeypatch.setattr(subprocess, "run", _hang)

    with pytest.raises(ClaimCommitUnresolved) as raised:
        claim_commit_for_wp(mission_dir, "WP01")

    assert raised.value.reason == "git_unavailable"


def test_missing_git_binary_is_git_unavailable(mission_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _record(mission_dir, _event("01CLAIMAAAAAAAAAAAAAAAAAA1", "WP01", Lane.CLAIMED))

    def _absent(*args: object, **kwargs: object) -> object:
        raise FileNotFoundError("git")

    monkeypatch.setattr(subprocess, "run", _absent)

    with pytest.raises(ClaimCommitUnresolved) as raised:
        claim_commit_for_wp(mission_dir, "WP01")

    assert raised.value.reason == "git_unavailable"


def _patch_merge_base(monkeypatch: pytest.MonkeyPatch, returncode: int) -> None:
    real_run: Any = subprocess.run

    def _run(command: list[str], *args: object, **kwargs: object) -> object:
        if command[:2] == ["git", "merge-base"]:
            return subprocess.CompletedProcess(command, returncode, "", "boom")
        return real_run(command, *args, **kwargs)

    monkeypatch.setattr(subprocess, "run", _run)


def test_claim_commit_that_is_not_an_ancestor_of_head_fails_closed(mission_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _record(mission_dir, _event("01CLAIMAAAAAAAAAAAAAAAAAA1", "WP01", Lane.CLAIMED))
    _patch_merge_base(monkeypatch, 1)

    with pytest.raises(ClaimCommitUnresolved) as raised:
        claim_commit_for_wp(mission_dir, "WP01")

    assert raised.value.reason == "no_commit"


def test_ancestry_probe_failure_is_git_unavailable(mission_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _record(mission_dir, _event("01CLAIMAAAAAAAAAAAAAAAAAA1", "WP01", Lane.CLAIMED))
    _patch_merge_base(monkeypatch, 128)

    with pytest.raises(ClaimCommitUnresolved) as raised:
        claim_commit_for_wp(mission_dir, "WP01")

    assert raised.value.reason == "git_unavailable"


def test_ancestry_probe_timeout_is_git_unavailable(mission_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _record(mission_dir, _event("01CLAIMAAAAAAAAAAAAAAAAAA1", "WP01", Lane.CLAIMED))
    real_run: Any = subprocess.run

    def _run(command: list[str], *args: object, **kwargs: object) -> object:
        if command[:2] == ["git", "merge-base"]:
            raise subprocess.TimeoutExpired(cmd="git", timeout=1)
        return real_run(command, *args, **kwargs)

    monkeypatch.setattr(subprocess, "run", _run)

    with pytest.raises(ClaimCommitUnresolved) as raised:
        claim_commit_for_wp(mission_dir, "WP01")

    assert raised.value.reason == "git_unavailable"


def test_unresolved_error_message_names_the_work_package_and_reason() -> None:
    error = ClaimCommitUnresolved("WP07", "ambiguous", "detail")

    assert error.wp_id == "WP07"
    assert error.reason == "ambiguous"
    assert "WP07" in str(error) and "ambiguous" in str(error) and "detail" in str(error)
    assert "detail" not in str(ClaimCommitUnresolved("WP07", "no_commit"))


def test_public_surface_carries_the_helper_and_its_error() -> None:
    import mission_runtime

    assert {"claim_commit_for_wp", "ClaimCommitUnresolved"} <= set(mission_runtime.__all__)
