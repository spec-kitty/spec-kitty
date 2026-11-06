"""FR-041: a status write whose target is inside a registered lane checkout refuses.

Mission ``lane-worktree-model-hardening-01M6QY1M`` WP10 (S6, restated ruling 3):
lane checkouts never show the Mission's status files, lanes never change them,
and readers never read them. The write seam classifies the target through the
git worktree registry (a registered linked checkout on a lane branch), never by
the ``.worktrees/`` path shape, so a lane checkout placed anywhere refuses with
``STATUS_WRITE_TARGETS_LANE_CHECKOUT``. Positive control: the same write to the
registered coordination worktree succeeds.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from specify_cli.coordination.status_service import (
    EventLogWriteContract,
    StatusContractError,
    append_event_stream_log,
)
from specify_cli.status.models import Lane, StatusEvent

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_MISSION = "lwr-01ABCDEF"
_MISSION_DIR = f"kitty-specs/{_MISSION}"
_LANE_CODE = "STATUS_WRITE_TARGETS_LANE_CHECKOUT"


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, check=True).stdout


def _event(event_id: str) -> StatusEvent:
    return StatusEvent(
        event_id=event_id,
        mission_slug=_MISSION,
        wp_id="WP01",
        from_lane=Lane.PLANNED,
        to_lane=Lane.CLAIMED,
        at="2026-11-06T12:00:00+00:00",
        actor="claude",
        force=False,
        execution_mode="worktree",
    )


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    mission_dir = repo / _MISSION_DIR
    mission_dir.mkdir(parents=True)
    (mission_dir / "status.events.jsonl").write_text("", encoding="utf-8")
    (mission_dir / "spec.md").write_text("# spec\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "seed")
    return repo


def _add_worktree(repo: Path, path: Path, branch: str) -> Path:
    _git(repo, "worktree", "add", "-q", "-b", branch, str(path), "main")
    return path


def test_status_write_into_lane_checkout_refuses(tmp_path: Path) -> None:
    """A lane checkout under ``.worktrees/`` and one outside it both refuse, by registry."""
    repo = _repo(tmp_path)
    under = _add_worktree(repo, repo / ".worktrees" / f"{_MISSION}-lane-a", f"kitty/mission-{_MISSION}-lane-a")
    outside = _add_worktree(repo, tmp_path / "elsewhere" / "lane-b-checkout", f"kitty/mission-{_MISSION}-lane-b")

    for checkout, contract_factory in (
        (under, EventLogWriteContract.coordination_transaction_append),
        (outside, EventLogWriteContract.primary_checkout_append),
    ):
        log = checkout / _MISSION_DIR / "status.events.jsonl"
        before = log.read_bytes()
        with pytest.raises(StatusContractError) as excinfo:
            append_event_stream_log(contract_factory(checkout / _MISSION_DIR), [_event("01M6QY1MLANEWRITE000000001")])
        assert getattr(excinfo.value, "error_code", None) == _LANE_CODE
        assert _LANE_CODE in str(excinfo.value)
        assert str(checkout.resolve()) in str(excinfo.value) or checkout.name in str(excinfo.value)
        assert log.read_bytes() == before, "a refused write never touches the lane copy"


def test_same_write_to_coord_worktree_succeeds(tmp_path: Path) -> None:
    """Positive control: the registered coordination worktree accepts the identical write."""
    repo = _repo(tmp_path)
    coord = _add_worktree(repo, repo / ".worktrees" / f"{_MISSION}-coord", f"kitty/mission-{_MISSION}-coordination")

    append_event_stream_log(
        EventLogWriteContract.coordination_transaction_append(coord / _MISSION_DIR),
        [_event("01M6QY1MLANEWRITE000000002")],
    )

    assert "01M6QY1MLANEWRITE000000002" in (coord / _MISSION_DIR / "status.events.jsonl").read_text(encoding="utf-8")


def test_repository_root_write_is_not_a_lane_write(tmp_path: Path) -> None:
    """The repository root checkout keeps its primary append, linked lanes notwithstanding."""
    repo = _repo(tmp_path)
    _add_worktree(repo, repo / ".worktrees" / f"{_MISSION}-lane-a", f"kitty/mission-{_MISSION}-lane-a")

    append_event_stream_log(
        EventLogWriteContract.primary_checkout_append(repo / _MISSION_DIR),
        [_event("01M6QY1MLANEWRITE000000003")],
    )

    assert "01M6QY1MLANEWRITE000000003" in (repo / _MISSION_DIR / "status.events.jsonl").read_text(encoding="utf-8")
