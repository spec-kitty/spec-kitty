"""Regression: orchestrator-api reads PRIMARY-partition artifacts off the primary
surface, not the coordination worktree (#2118).

The split-brain bug: for a ``topology: coord`` / ``pr_bound`` mission rooted on a
*writable* target branch, the write-surface-coherence work (#2090) routes planning
artifacts — ``lanes.json`` (``LANE_STATE``) and the WP ``tasks/`` files
(``WORK_PACKAGE_TASK``) — to the primary ``target_branch``. The orchestrator used
to read them off the coordination worktree (``_resolve_mission_dir`` →
``resolve_handle_to_read_path``), which carries only STATUS artifacts. The
dependency graph came back empty → ``list-ready`` returned nothing → the
orchestrator stalled with every WP stuck at ``lane=planned``.

This fixture reproduces the genuine split: ``lanes.json`` + ``tasks/`` live ONLY on
the target branch (the primary checkout HEAD); the coordination worktree (a checkout
of the coord branch) has only ``meta.json`` + the status event log. The endpoints
must still discover the WPs (PRIMARY reads → primary surface) while status continues
to resolve the coord worktree (STATUS reads → coord).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from specify_cli.coordination.workspace import CoordinationWorkspace
from specify_cli.orchestrator_api._common import _planning_read_dir, _resolve_mission_dir
from specify_cli.orchestrator_api.commands import app

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

runner = CliRunner()

MISSION_SLUG = "split-coord"
MID8 = "01KSPLIT"
MISSION_ID = "01KSPLIT000000000000000000"
MISSION_DIRNAME = f"{MISSION_SLUG}-{MID8}"
COORD_BRANCH = f"kitty/mission-{MISSION_DIRNAME}"
TARGET_BRANCH = "feat/split-target"

_WP01 = (
    "---\n"
    "work_package_id: WP01\n"
    "title: First\n"
    "dependencies: []\n"
    "---\n\n# WP01\n"
)
_WP02 = (
    "---\n"
    "work_package_id: WP02\n"
    "title: Second\n"
    "dependencies: [WP01]\n"
    "---\n\n# WP02\n"
)
_LANES_JSON = {
    "version": 1,
    "feature_slug": MISSION_DIRNAME,
    "target_branch": TARGET_BRANCH,
    "lanes": [
        {"lane_id": "lane-a", "wp_ids": ["WP01"]},
        {"lane_id": "lane-b", "wp_ids": ["WP02"]},
    ],
}


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    )


@pytest.fixture
def split_repo(tmp_path: Path) -> Path:
    """Coord-topology mission whose planning artifacts live ONLY on the target branch.

    The coordination worktree (coord branch) carries meta.json + status only — NO
    ``lanes.json`` and NO ``tasks/`` — exactly the #2118 split.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.invalid")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")

    feature_dir = repo / "kitty-specs" / MISSION_DIRNAME
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_slug": MISSION_SLUG,
                "mission_id": MISSION_ID,
                "mid8": MID8,
                "coordination_branch": COORD_BRANCH,
                "target_branch": TARGET_BRANCH,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    # Seed ONLY meta.json on main, then branch coord from it — so the coord branch
    # has the mission dir (for status writes) but NO planning artifacts.
    _git(repo, "add", "kitty-specs")
    _git(repo, "commit", "-q", "-m", "seed mission meta")
    _git(repo, "branch", COORD_BRANCH)

    # Planning artifacts (lanes.json + WP tasks/) land on the writable target branch
    # — the post-#2090 PRIMARY write surface. The operator is ON the target branch.
    _git(repo, "checkout", "-q", "-b", TARGET_BRANCH)
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir()
    (tasks_dir / "WP01.md").write_text(_WP01, encoding="utf-8")
    (tasks_dir / "WP02.md").write_text(_WP02, encoding="utf-8")
    (feature_dir / "lanes.json").write_text(
        json.dumps(_LANES_JSON) + "\n", encoding="utf-8"
    )
    _git(repo, "add", "kitty-specs")
    _git(repo, "commit", "-q", "-m", "planning artifacts on target branch")

    # Materialize the coordination worktree (status read/write surface).
    coord_worktree = CoordinationWorkspace.worktree_path(repo, MISSION_SLUG, MID8)
    _git(repo, "worktree", "add", "-q", str(coord_worktree), COORD_BRANCH)
    return repo


def _coord_feature_dir(repo: Path) -> Path:
    return (
        CoordinationWorkspace.worktree_path(repo, MISSION_SLUG, MID8)
        / "kitty-specs"
        / MISSION_DIRNAME
    )


def test_planning_read_dir_resolves_primary_not_coord(split_repo: Path) -> None:
    """``_planning_read_dir`` returns the primary surface; ``_resolve_mission_dir``
    the coord worktree. The planning artifacts exist at the former, not the latter."""
    planning_dir = _planning_read_dir(split_repo, MISSION_DIRNAME)
    status_dir = _resolve_mission_dir(split_repo, MISSION_DIRNAME)

    assert status_dir is not None
    assert planning_dir != status_dir, (
        "Under coord topology the planning surface must differ from the status "
        "(coord worktree) surface — else the split cannot be exercised."
    )
    # PRIMARY artifacts live on the planning surface ...
    assert (planning_dir / "lanes.json").exists()
    assert (planning_dir / "tasks" / "WP01.md").exists()
    # ... and are absent from the coord worktree (the bug's read surface).
    assert not (status_dir / "lanes.json").exists()
    assert not (status_dir / "tasks").exists()


def _invoke(repo: Path, *args: str) -> object:
    with patch(
        "specify_cli.orchestrator_api._common._get_main_repo_root",
        return_value=repo,
    ):
        return runner.invoke(app, list(args))


def test_mission_state_discovers_wps_from_primary_surface(split_repo: Path) -> None:
    """``mission-state`` enumerates WPs from the primary ``tasks/`` + dep graph even
    though the coord worktree (its status surface) has neither (#2118 stall fix)."""
    result = _invoke(split_repo, "mission-state", "--mission", MISSION_DIRNAME)
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)["data"]
    wp_ids = {wp["wp_id"] for wp in data["work_packages"]}
    assert wp_ids == {"WP01", "WP02"}, (
        "WPs not discovered — mission-state read tasks/ off the coord worktree "
        "(empty) instead of the primary surface (#2118)."
    )
    by_id = {wp["wp_id"]: wp for wp in data["work_packages"]}
    assert by_id["WP02"]["dependencies"] == ["WP01"]


def test_list_ready_returns_unblocked_wp_under_coord_split(split_repo: Path) -> None:
    """``list-ready`` returns WP01 (no deps, planned). Pre-fix the dependency graph
    was read off the empty coord worktree → no ready WPs → orchestrator stall."""
    result = _invoke(split_repo, "list-ready", "--mission", MISSION_DIRNAME)
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)["data"]
    ready = {wp["wp_id"] for wp in data["ready_work_packages"]}
    assert "WP01" in ready, (
        "WP01 should be schedulable; an empty ready-set is the #2118 stall "
        "(dependency graph read off the coord worktree instead of primary)."
    )
    # WP02 depends on the not-yet-approved WP01 → not ready.
    assert "WP02" not in ready
