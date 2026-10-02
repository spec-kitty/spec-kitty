"""Coordination-routed create seeds the status log on the coordination branch (#5440).

Companion to the red-first reproduction
``tests/core/test_mission_create_coord_status_placement.py`` (PR #5518). These
tests pin the paths around the fix through the real ``create_mission_core``
entry point over real temporary git repositories (no commit mocks):

* ``lanes_with_coord`` seeds the coordination branch exactly like ``coord``;
* with no local coordination branch to hold it, the log keeps its primary home.

The create-time salvage / seed-gate stopgap internals this file used to pin
were superseded by the single-home seed machinery (coord-artifact-single-home).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from mission_runtime import MissionTopology
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
