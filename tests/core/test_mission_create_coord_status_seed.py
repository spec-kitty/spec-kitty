"""Coordination-routed create seeds the status log on the coordination branch (#5440).

Companion to the red-first reproduction
``tests/core/test_mission_create_coord_status_placement.py`` (PR #5518). These
tests pin the paths around the fix through the real ``create_mission_core``
entry point over real temporary git repositories (no commit mocks):

* ``lanes_with_coord`` seeds the coordination branch exactly like ``coord``;
* with no local coordination branch to hold it, the log keeps its primary home;
* a late create failure removes the coordination worktree and the orphan
  coordination branch, and keeps the status log next to the retained scaffold.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from mission_runtime import MissionTopology
from specify_cli.core import mission_creation
from specify_cli.core.mission_creation import create_mission_core

from tests.core.test_mission_create_scaffold_rollback import _init_git_repo, _mission_summary

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_STATUS_LOG = "status.events.jsonl"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True).stdout


def _tree(repo: Path, ref: str) -> list[str]:
    return _git(repo, "ls-tree", "-r", "--name-only", ref).splitlines()


def _event_types(log_path: Path) -> list[str]:
    return [json.loads(line).get("event_type") for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]


@pytest.fixture(autouse=True)
def _not_a_worktree(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("specify_cli.core.mission_creation.is_worktree_context", lambda cwd: False)


def test_lanes_with_coord_create_seeds_the_coordination_branch(tmp_path: Path) -> None:
    _init_git_repo(tmp_path)

    result = create_mission_core(
        tmp_path,
        "lanes-coord",
        topology=MissionTopology.LANES_WITH_COORD,
        **_mission_summary("lanes-coord"),
    )

    slug = result.mission_slug
    assert result.coordination_branch is not None
    assert f"kitty-specs/{slug}/status.events.jsonl" not in _tree(tmp_path, "HEAD")
    assert f"kitty-specs/{slug}/status.events.jsonl" in _tree(tmp_path, result.coordination_branch)
    assert not (result.feature_dir / _STATUS_LOG).exists()


def test_coord_create_without_a_coordination_branch_keeps_the_primary_home(tmp_path: Path) -> None:
    """A target that does not resolve to a ref skips the coordination mint; with no
    coordination surface to hold it, the log keeps its primary home and stays in
    the (disclosed, skipped) scaffold set."""
    _init_git_repo(tmp_path)

    result = create_mission_core(
        tmp_path,
        "no-coord-branch",
        topology=MissionTopology.COORD,
        target_branch="does-not-exist",
        **_mission_summary("no-coord-branch"),
    )

    primary_log = result.feature_dir / _STATUS_LOG
    assert primary_log.exists()
    assert _event_types(primary_log).count("MissionCreated") == 1
    assert primary_log in result.uncommitted_files
    assert not (tmp_path / ".worktrees").exists()


def test_failed_create_removes_the_coordination_worktree_and_keeps_the_log(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _init_git_repo(tmp_path)
    branches_before = _git(tmp_path, "branch", "--list", "kitty/mission-*")

    def _refuse(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("injected coordination commit failure")

    monkeypatch.setattr(mission_creation, "_commit_coordination_status_seed", _refuse)

    with pytest.raises(RuntimeError, match="status log commit on the coordination branch failed"):
        create_mission_core(tmp_path, "late-failure", **_mission_summary("late-failure"))

    # No orphan coordination branch, and no worktree left registered on it.
    assert _git(tmp_path, "branch", "--list", "kitty/mission-*") == branches_before
    assert "-coord" not in _git(tmp_path, "worktree", "list")
    # The retained partial scaffold carries the status log for diagnosis.
    (primary_log,) = (tmp_path / "kitty-specs").glob(f"*/{_STATUS_LOG}")
    assert _event_types(primary_log).count("MissionCreated") == 1


def test_salvage_never_overwrites_an_existing_primary_log(tmp_path: Path) -> None:
    coord_dir = tmp_path / "coord" / "kitty-specs" / "m-01ABCDEF"
    primary_dir = tmp_path / "primary" / "kitty-specs" / "m-01ABCDEF"
    coord_dir.mkdir(parents=True)
    primary_dir.mkdir(parents=True)
    (coord_dir / _STATUS_LOG).write_text("coord\n", encoding="utf-8")
    (primary_dir / _STATUS_LOG).write_text("primary\n", encoding="utf-8")
    missing_primary = tmp_path / "coord" / "kitty-specs" / "other-01ABCDEF"
    missing_primary.mkdir()
    (missing_primary / _STATUS_LOG).write_text("orphan\n", encoding="utf-8")

    mission_creation._salvage_status_logs(tmp_path / "coord", tmp_path / "primary")

    assert (primary_dir / _STATUS_LOG).read_text(encoding="utf-8") == "primary\n"
    assert not (tmp_path / "primary" / "kitty-specs" / "other-01ABCDEF").exists()


def test_status_log_residue_accepts_only_status_logs_under_kitty_specs(tmp_path: Path) -> None:
    mission_dir = tmp_path / "kitty-specs" / "m-01ABCDEF"
    mission_dir.mkdir(parents=True)
    (mission_dir / _STATUS_LOG).write_text("", encoding="utf-8")
    is_residue = mission_creation._status_log_residue(tmp_path)

    assert is_residue("kitty-specs")
    assert is_residue(f"kitty-specs/m-01ABCDEF/{_STATUS_LOG}")

    (mission_dir / "notes.md").write_text("operator work\n", encoding="utf-8")
    (tmp_path / _STATUS_LOG).write_text("", encoding="utf-8")
    assert not is_residue("kitty-specs")
    assert not is_residue(_STATUS_LOG)
    assert not is_residue("kitty-specs/missing")
