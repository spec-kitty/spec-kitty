"""Advisory shared-workspace warning (#5099; concurrent-mission-writers WP02, T012).

``agent action implement`` and ``agent action review`` name every OTHER actor that
holds a WP ``in_progress`` / ``in_review`` in the same resolved workspace: the
repository root checkout of a single_branch Mission (across Missions), or the
lane worktree for lanes Missions. Advisory only: nothing is refused (C-004).

Neither command has a JSON mode (their output is the prompt text), so the warning
is human output only; the structured entries are :class:`SharedWorkspaceWriter`.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from specify_cli.cli.commands.agent import workflow_executor
from specify_cli.lanes.checkout_occupancy import (
    SharedWorkspaceWriter,
    in_progress_wps_in_write_checkout,
    is_single_branch_repo_root_lane,
    shared_workspace_writers,
)
from specify_cli.lanes.compute import PLANNING_LANE_ID
from specify_cli.lanes.models import ExecutionLane
from tests.lanes.test_checkout_occupancy import _init_repo, _write_lanes, _write_repo_root_lane, _write_single_branch_meta
from specify_cli.workspace.context import ResolvedWorkspace
from tests.utils import write_wp

pytestmark = [pytest.mark.fast, pytest.mark.git_repo]

MISSION = "shared-ws-mission"
OTHER_MISSION = "shared-ws-other"


def _single_branch_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    _init_repo(repo)
    _write_single_branch_meta(repo, MISSION, "01SHAREDWSMISSION000000001")
    _write_repo_root_lane(repo, MISSION, "WP01", "WP02")
    return repo


def _workspace(lane_id: str, wp_ids: tuple[str, ...]) -> ResolvedWorkspace:
    return ResolvedWorkspace(
        mission_slug=MISSION,
        wp_id=wp_ids[0],
        execution_mode="code_change",
        mode_source="test",
        resolution_kind="repo_root" if lane_id == PLANNING_LANE_ID else "lane_workspace",
        workspace_name=lane_id,
        worktree_path=Path("."),
        branch_name=None,
        lane_id=lane_id,
        lane_wp_ids=list(wp_ids),
    )


def _repo_root_workspace(wp_ids: tuple[str, ...] = ("WP01", "WP02")) -> ResolvedWorkspace:
    return _workspace(PLANNING_LANE_ID, wp_ids)


def test_review_arm_names_the_other_actor_holding_a_wp_in_progress(tmp_path: Path) -> None:
    repo = _single_branch_repo(tmp_path)
    write_wp(repo, MISSION, "in_progress", "WP01", agent="alice")
    write_wp(repo, MISSION, "for_review", "WP02", agent="bob")

    writers = shared_workspace_writers(repo, MISSION, "WP02", _repo_root_workspace(), "bob")

    assert writers == [SharedWorkspaceWriter(MISSION, "WP01", "in_progress", "alice")]
    assert writers[0].warning() == f"Warning: {MISSION}/WP01 is in_progress by alice in this workspace; one writer per checkout."


def test_implement_arm_names_a_wp_another_actor_has_in_review(tmp_path: Path) -> None:
    repo = _single_branch_repo(tmp_path)
    write_wp(repo, MISSION, "in_review", "WP01", agent="reviewer-rae")
    write_wp(repo, MISSION, "planned", "WP02", agent="alice")

    writers = shared_workspace_writers(repo, MISSION, "WP02", _repo_root_workspace(), "alice")

    assert [(w.wp_id, w.lane, w.actor) for w in writers] == [("WP01", "in_review", "reviewer-rae")]


def test_single_branch_scan_crosses_missions(tmp_path: Path) -> None:
    repo = _single_branch_repo(tmp_path)
    _write_single_branch_meta(repo, OTHER_MISSION, "01SHAREDWSOTHER0000000001")
    _write_repo_root_lane(repo, OTHER_MISSION, "WP01")
    write_wp(repo, OTHER_MISSION, "in_progress", "WP01", agent="carol")

    writers = shared_workspace_writers(repo, MISSION, "WP01", _repo_root_workspace(), "alice")

    assert [(w.mission_slug, w.wp_id, w.actor) for w in writers] == [(OTHER_MISSION, "WP01", "carol")]


def test_lanes_arm_names_the_other_actor_on_the_same_lane_worktree(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    (repo / "kitty-specs" / "lanes-ws-mission").mkdir(parents=True)
    _write_lanes(repo, "lanes-ws-mission", {"lane-a": ("WP01", "WP02"), "lane-b": ("WP03",)})
    write_wp(repo, "lanes-ws-mission", "in_progress", "WP01", agent="alice")
    write_wp(repo, "lanes-ws-mission", "planned", "WP02", agent="bob")
    write_wp(repo, "lanes-ws-mission", "in_progress", "WP03", agent="dana")  # another lane worktree: not shared
    lane_a = _workspace("lane-a", ("WP01", "WP02"))

    writers = shared_workspace_writers(repo, "lanes-ws-mission", "WP02", lane_a, "bob")

    assert [(w.wp_id, w.lane, w.actor) for w in writers] == [("WP01", "in_progress", "alice")]


def test_no_concurrent_writer_means_no_warning(tmp_path: Path) -> None:
    repo = _single_branch_repo(tmp_path)
    write_wp(repo, MISSION, "planned", "WP01", agent="alice")
    write_wp(repo, MISSION, "for_review", "WP02", agent="bob")

    assert shared_workspace_writers(repo, MISSION, "WP02", _repo_root_workspace(), "bob") == []


def test_same_actor_is_not_a_shared_writer(tmp_path: Path) -> None:
    repo = _single_branch_repo(tmp_path)
    write_wp(repo, MISSION, "in_progress", "WP01", agent="alice")
    write_wp(repo, MISSION, "planned", "WP02", agent="alice")

    assert shared_workspace_writers(repo, MISSION, "WP02", _repo_root_workspace(), "alice") == []


def test_the_calling_wp_itself_is_never_reported(tmp_path: Path) -> None:
    repo = _single_branch_repo(tmp_path)
    write_wp(repo, MISSION, "in_progress", "WP01", agent="alice")

    assert shared_workspace_writers(repo, MISSION, "WP01", _repo_root_workspace(("WP01",)), "bob") == []


def test_unknown_calling_actor_counts_as_different(tmp_path: Path) -> None:
    repo = _single_branch_repo(tmp_path)
    write_wp(repo, MISSION, "in_progress", "WP01", agent="alice")

    assert len(shared_workspace_writers(repo, MISSION, "WP02", _repo_root_workspace(), None)) == 1


def test_in_progress_scan_keeps_its_public_behaviour_and_ignores_in_review(tmp_path: Path) -> None:
    repo = _single_branch_repo(tmp_path)
    write_wp(repo, MISSION, "in_progress", "WP01", agent="alice")
    write_wp(repo, MISSION, "in_review", "WP02", agent="bob")

    assert in_progress_wps_in_write_checkout(repo, repo) == [(MISSION, "WP01")]


def test_warn_helper_prints_each_warning_and_returns_the_lines(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    repo = _single_branch_repo(tmp_path)
    write_wp(repo, MISSION, "in_progress", "WP01", agent="alice")
    write_wp(repo, MISSION, "planned", "WP02", agent="bob")

    lines = workflow_executor.warn_shared_workspace_writers(repo, MISSION, "WP02", _repo_root_workspace(), "bob")

    assert lines == [f"Warning: {MISSION}/WP01 is in_progress by alice in this workspace; one writer per checkout."]
    assert capsys.readouterr().out.splitlines() == lines


def test_warn_helper_prints_nothing_without_a_concurrent_writer(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    repo = _single_branch_repo(tmp_path)
    write_wp(repo, MISSION, "planned", "WP01", agent="alice")

    assert workflow_executor.warn_shared_workspace_writers(repo, MISSION, "WP01", _repo_root_workspace(), "alice") == []
    assert capsys.readouterr().out == ""


def test_warn_helper_survives_an_unrelated_mission_with_a_corrupt_log(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """F3: the advisory scan reads other Missions' logs; a malformed one must degrade to no warning, never crash the command."""
    repo = _single_branch_repo(tmp_path)
    write_wp(repo, MISSION, "planned", "WP01", agent="alice")
    _write_single_branch_meta(repo, OTHER_MISSION, "01SHAREDWSOTHER0000000001")
    _write_repo_root_lane(repo, OTHER_MISSION, "WP01")
    write_wp(repo, OTHER_MISSION, "in_progress", "WP01", agent="carol")
    (repo / "kitty-specs" / OTHER_MISSION / "status.events.jsonl").write_text("{not json\n", encoding="utf-8")

    assert workflow_executor.warn_shared_workspace_writers(repo, MISSION, "WP01", _repo_root_workspace(), "alice") == []
    assert capsys.readouterr().out == ""


def _lane(lane_id: str) -> ExecutionLane:
    return ExecutionLane(lane_id=lane_id, wp_ids=("WP01",), write_scope=(), predicted_surfaces=(), depends_on_lanes=(), parallel_group=0)


def _set_topology(repo: Path, mission: str, topology: str) -> None:
    meta_path = repo / "kitty-specs" / mission / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["topology"] = topology
    meta_path.write_text(json.dumps(meta), encoding="utf-8")


def test_predicate_accepts_the_repo_root_lane_and_the_repo_root_workspace_of_a_single_branch_mission(tmp_path: Path) -> None:
    repo = _single_branch_repo(tmp_path)

    assert is_single_branch_repo_root_lane(repo, MISSION, _lane(PLANNING_LANE_ID))
    assert is_single_branch_repo_root_lane(repo, MISSION, _repo_root_workspace())


def test_predicate_refuses_a_code_lane_of_a_single_branch_mission(tmp_path: Path) -> None:
    repo = _single_branch_repo(tmp_path)

    assert not is_single_branch_repo_root_lane(repo, MISSION, _lane("lane-a"))
    assert not is_single_branch_repo_root_lane(repo, MISSION, _workspace("lane-a", ("WP01",)))


def test_predicate_refuses_the_planning_lane_of_a_lanes_mission(tmp_path: Path) -> None:
    """A planning WP of a lanes Mission also sits in the repo-root lane, but it does not own the shared write checkout."""
    repo = _single_branch_repo(tmp_path)
    _set_topology(repo, MISSION, "lanes")

    assert not is_single_branch_repo_root_lane(repo, MISSION, _lane(PLANNING_LANE_ID))
    assert not is_single_branch_repo_root_lane(repo, MISSION, _repo_root_workspace())


# ---------------------------------------------------------------------------
# CLI wiring: deleting the call from implement() / review() must fail these
# ---------------------------------------------------------------------------


def _lane_mate_mission(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, wp01_lane: str, mate_lane: str, mate_actor: str) -> tuple[str, str]:
    """A flat Mission whose WP01 and WP02 share lane-a; WP02 sits in ``mate_lane`` held by ``mate_actor``."""
    from specify_cli.lanes.models import ExecutionLane
    from specify_cli.lanes.persistence import read_lanes_json, write_lanes_json
    from tests.characterization.test_trio_json_envelope import _build_mission_repo

    repo, mission = _build_mission_repo(tmp_path, monkeypatch, coord=False, mission_slug="warn-wiring", wp_lane=wp01_lane)
    write_wp(repo, mission, mate_lane, "WP02", agent=mate_actor)
    feature_dir = repo / "kitty-specs" / mission
    manifest = read_lanes_json(feature_dir)
    assert manifest is not None
    lane = manifest.lanes[0]
    manifest.lanes = [
        ExecutionLane(
            lane_id=lane.lane_id,
            wp_ids=(*lane.wp_ids, "WP02"),
            write_scope=lane.write_scope,
            predicted_surfaces=lane.predicted_surfaces,
            depends_on_lanes=lane.depends_on_lanes,
            parallel_group=lane.parallel_group,
        )
    ]
    write_lanes_json(feature_dir, manifest)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-q", "-m", "add WP02"], cwd=repo, check=True, capture_output=True)
    return mission, mate_actor


def _run_action(verb: str, mission: str, agent: str) -> str:
    from typer.testing import CliRunner

    from specify_cli import app as root_app

    extra = ["--allow-sparse-checkout"] if verb == "implement" else []
    result = CliRunner().invoke(root_app, ["agent", "action", verb, "WP01", "--mission", mission, "--agent", agent, *extra])
    assert result.exit_code == 0, result.output
    return str(result.output)


def test_implement_command_warns_about_another_actor_on_its_lane_worktree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mission, _ = _lane_mate_mission(tmp_path, monkeypatch, wp01_lane="planned", mate_lane="in_progress", mate_actor="alice")

    out = _run_action("implement", mission, "bob")

    assert f"Warning: {mission}/WP02 is in_progress by alice in this workspace; one writer per checkout." in out


def test_implement_command_stays_quiet_for_the_same_actor(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mission, _ = _lane_mate_mission(tmp_path, monkeypatch, wp01_lane="planned", mate_lane="in_progress", mate_actor="alice")

    assert "one writer per checkout" not in _run_action("implement", mission, "alice")


def test_review_command_warns_about_another_actor_on_the_lane_worktree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mission, _ = _lane_mate_mission(tmp_path, monkeypatch, wp01_lane="for_review", mate_lane="in_progress", mate_actor="alice")

    out = _run_action("review", mission, "bob")

    assert f"Warning: {mission}/WP02 is in_progress by alice in this workspace; one writer per checkout." in out
