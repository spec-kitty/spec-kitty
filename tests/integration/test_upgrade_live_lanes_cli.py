"""Fresh upgrade with live lanes, then integrate: paths A, B and C of #5457.

Each scenario runs the real CLI end to end on WP01's older-version lanes
fixture: ``spec-kitty upgrade --yes`` first, then the integration command the
issue's reproducer ran (``consolidate`` or ``agent action review``). Before the
fix, upgrade committed its own divergent ``.kittify/metadata.yaml`` /
``.gitattributes`` on every lane and coordination branch, and each command
refused on those files:

* Path A (``lanes``, 2 lanes): ``Lane lane-b is stale: overlapping files
  ['.gitattributes', '.kittify/metadata.yaml']``.
* Path B (``lanes``, 1 lane, target ``work``): ``TARGET_BRANCH_CONTENT_CONFLICT``
  on ``.kittify/metadata.yaml``.
* Path C (``lanes_with_coord``, WP02 ``for_review`` at upgrade time):
  ``LANE_AUTO_REBASE_FAILED: no classifier rule matched .../.kittify/metadata.yaml``.

Fixture notes:

* The fixture writes today's mission-state shape (``meta.json``, status log,
  derived ``status.json``), so ``upgrade`` leaves the repository root checkout
  clean and ``consolidate`` runs straight after it.
* ``accept`` is not run in Path B: the fixture scaffolds no acceptance matrix
  and no path-convention directories, and ``consolidate`` (the command that
  refused in the issue) reads only the status log for its approval gate.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from tests.integration import primary_owned_fixtures as fx
from tests.integration.primary_owned_fixtures import (
    LanesProject,
    append_status_event_on_branch,
    build_older_version_lanes_project,
    output_names_auto_rebase_failure,
    output_names_stale_metadata_refusal,
    output_names_target_content_conflict,
    output_shows_primary_owned_defect,
    upgrade_commits_on,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.slow]


def _out(result: subprocess.CompletedProcess[str]) -> str:
    return (result.stdout or "") + (result.stderr or "")


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, check=True).stdout


def _upgrade(project: LanesProject) -> dict[str, list[str]]:
    """Run ``upgrade --yes``; return the upgrade commits each lane / coordination branch got.

    Read right after the upgrade, because a successful ``consolidate`` deletes
    the lane branches. Callers assert the map is empty AFTER the integration
    command, so a red run shows the integration refusal itself.
    """
    result = project.upgrade()
    assert result.returncode == 0, _out(result)
    return {branch: upgrade_commits_on(project.repo, branch) for branch in project.branches()}


def _assert_no_branch_upgrade_commits(commits: dict[str, list[str]]) -> None:
    """No ``chore: apply spec-kitty upgrade changes`` commit on an integrating branch."""
    assert {branch: shas for branch, shas in commits.items() if shas} == {}


def _run_in(project: LanesProject, cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Run the real CLI with ``cwd`` inside a worktree (isolated HOME)."""
    return subprocess.run(
        [sys.executable, "-m", "specify_cli", *args],
        cwd=str(cwd),
        env=fx._cli_env(project.mission.home),
        capture_output=True,
        text=True,
        check=False,
    )


def _assert_lane_runtime_still_works(project: LanesProject) -> None:
    """A skipped lane keeps its pre-upgrade ``.kittify`` copy; it must be inert."""
    lane_worktree = next(iter(project.lane_worktrees.values()))
    result = _run_in(project, lane_worktree, "agent", "tasks", "status", "--mission", project.slug)
    assert result.returncode == 0, _out(result)


def _wp_lane(project: LanesProject, wp_id: str) -> str:
    result = project.run("agent", "tasks", "status", "--mission", project.slug, "--json")
    assert result.returncode == 0, _out(result)
    payload = json.loads(result.stdout[result.stdout.index("{") :])
    return next(str(wp["lane"]) for wp in payload["work_packages"] if wp["id"] == wp_id)


def _assert_lane_files_on_target(project: LanesProject) -> None:
    for lane_id in project.lane_ids:
        path = f"src/{lane_id.replace('-', '_')}/m.py"
        _git(project.repo, "cat-file", "-e", f"{project.target_branch}:{path}")


def test_path_a_two_lanes_upgrade_then_consolidate(tmp_path: Path) -> None:
    project = build_older_version_lanes_project(tmp_path, topology="lanes", lanes=2)
    upgrade_commits = _upgrade(project)
    _assert_lane_runtime_still_works(project)

    result = project.run("consolidate", "--mission", project.slug)

    assert not output_names_stale_metadata_refusal(result), _out(result)
    assert not output_shows_primary_owned_defect(result), _out(result)
    assert result.returncode == 0, _out(result)
    _assert_lane_files_on_target(project)
    _assert_no_branch_upgrade_commits(upgrade_commits)


def test_path_b_one_lane_into_work_upgrade_then_consolidate(tmp_path: Path) -> None:
    project = build_older_version_lanes_project(tmp_path, topology="lanes", lanes=1, target_branch="work")
    upgrade_commits = _upgrade(project)
    _assert_lane_runtime_still_works(project)

    result = project.run("consolidate", "--mission", project.slug)

    assert not output_names_target_content_conflict(result), _out(result)
    assert "TARGET_BRANCH_CONTENT_CONFLICT" not in _out(result)
    assert result.returncode == 0, _out(result)
    _assert_lane_files_on_target(project)
    _assert_no_branch_upgrade_commits(upgrade_commits)


def _put_wp_back_in_review_queue(project: LanesProject, wp_id: str) -> None:
    """Record ``approved -> for_review`` (forced) on the coordination branch.

    The CLI refuses every status command before ``upgrade`` on an older project,
    so this commits the event the way the pre-upgrade CLI would have.
    """
    assert project.coord_branch is not None
    append_status_event_on_branch(
        project,
        project.coord_branch,
        wp_id,
        "approved",
        "for_review",
        force=True,
        reason="fixture: awaiting review at upgrade time",
    )


def test_path_c_coordination_mission_review_after_upgrade(tmp_path: Path) -> None:
    project = build_older_version_lanes_project(tmp_path, topology="lanes_with_coord", lanes=2, with_analysis_report=True)
    _put_wp_back_in_review_queue(project, "WP02")
    upgrade_commits = _upgrade(project)
    _assert_lane_runtime_still_works(project)
    assert _wp_lane(project, "WP02") == "for_review"

    result = project.run("agent", "action", "review", "WP02", "--mission", project.slug, "--agent", "claude")

    assert not output_names_auto_rebase_failure(result), _out(result)
    assert "LANE_AUTO_REBASE_FAILED" not in _out(result)
    assert result.returncode == 0, _out(result)
    assert _wp_lane(project, "WP02") == "in_review"
    _assert_no_branch_upgrade_commits(upgrade_commits)
