"""#4758 (WP02, FR-002/FR-006): ``move-task`` planned-boundary lanes guard.

The bug (defense-in-depth half of #4758): the legacy ``agent tasks
finalize-tasks`` path can seed the canonical event log (bootstrapping every WP
to ``planned``) without computing ``lanes.json`` -- the escape this module
pins. Once that happens, ``move-task --to doing`` (or any hop out of
``planned``) drove the mission's canonical runtime state into a shape every
downstream gate (``implement``, review, approval) refuses, with no documented
repair -- the "wedge" the mission spec names.

``T007`` seeds exactly that shape (a genesis->planned bootstrap event, no
``lanes.json`` on disk) and asserts the DESIRED refusal -- naming
``spec-kitty doctor mission-state --fix --mission <slug>``. Before WP02's fix
this assertion is RED (the current code lets the move through instead of
refusing); the guard added in ``tasks_move_task.py`` (``_mt_guard_planned_
boundary_lanes``) turns it GREEN.

``T009`` adds the positive control: the identical scenario with ``lanes.json``
present on disk is completely unaffected by the new guard.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import typer

from specify_cli.cli.commands.agent.tasks import _do_move_task, _MoveTaskArgs
from specify_cli.agent_tasks_ports import (
    CommitStatusResult,
    TasksPorts,
)
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import write_lanes_json
from specify_cli.status.models import Lane, StatusEvent
from specify_cli.status.store import append_event
from tests.mocked_env import setup_mocked_env
from tests.specify_cli.cli.commands.agent.test_tasks_ports import (
    FakeCoordCommitRouter,
    FakeFsReader,
    FakeGitOps,
    FakeRender,
)

pytestmark = [pytest.mark.regression, pytest.mark.fast]

_MISSION = "test-move-task-planned-guard"
_WP_ID = "WP01"


def _build_wp_file(tmp_path: Path, mission_slug: str, wp_id: str) -> Path:
    """Minimal WP + feature-dir structure (mirrors the shared test helper)."""
    feature_dir = tmp_path / "kitty-specs" / mission_slug
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    (tmp_path / ".kittify").mkdir(exist_ok=True)
    wp_file = tasks_dir / f"{wp_id}-test.md"
    wp_file.write_text(
        f"---\n"
        f"work_package_id: {wp_id}\n"
        f"title: Test {wp_id}\n"
        f"execution_mode: code_change\n"
        f"subtasks: [T001, T002, T003]\n"
        f"owned_files:\n  - src/{wp_id.lower()}/**\n"
        f"authoritative_surface: src/{wp_id.lower()}/\n"
        f"---\n\n# {wp_id}\n\n## Activity Log\n",
        encoding="utf-8",
    )
    return feature_dir


def _seed_bootstrap_planned(feature_dir: Path, wp_id: str) -> None:
    """Seed a ``genesis -> planned`` bootstrap event.

    Mirrors the event shape ``agent tasks finalize-tasks`` writes when it
    seeds the event log for a freshly-finalized mission -- WITHOUT writing
    ``lanes.json``, reproducing the #4758 escape this WP closes.
    """
    append_event(
        feature_dir,
        StatusEvent(
            event_id=f"test-{wp_id}-bootstrap",
            mission_slug=feature_dir.name,
            wp_id=wp_id,
            from_lane=Lane.GENESIS,
            to_lane=Lane.PLANNED,
            at="2026-01-01T00:00:00+00:00",
            actor="system",
            force=True,
            execution_mode="worktree",
        ),
    )


def _fake_ports(feature_dir: Path) -> TasksPorts:
    coord = FakeCoordCommitRouter(
        write_dir=feature_dir,
        status_result=CommitStatusResult(event=None, skipped=False),
    )
    return TasksPorts(fs=FakeFsReader(), coord=coord, git=FakeGitOps(), render=FakeRender())


def _run_move(tmp_path: Path, ports: TasksPorts, *, to: str = "doing") -> None:
    with setup_mocked_env(
        tmp_path,
        mission_slug=_MISSION,
        target_branch="wip-lane",
        extra_patches={
            "_validate_ready_for_review": (True, []),
            "_check_unchecked_subtasks": [],
        },
    ):
        _do_move_task(
            _MoveTaskArgs(
                task_id=_WP_ID,
                to=to,
                mission=_MISSION,
                agent=None,
                assignee=None,
                shell_pid=None,
                note=None,
                review_feedback_file=None,
                approval_ref=None,
                reviewer=None,
                self_review_fallback=False,
                intended_reviewer=None,
                reviewer_failure_reason=None,
                done_override_reason=None,
                force=False,
                tracker_ref=None,
                skip_review_artifact_check=False,
                auto_commit=False,
                json_output=True,
            ),
            ports=ports,
        )


def test_move_task_refuses_leaving_planned_without_lanes_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """T007/T009 (GREEN): the #4758 escape is closed.

    A mission whose event log shows a bootstrapped ``planned`` WP but has no
    ``lanes.json`` on disk must REFUSE ``move-task --to doing`` -- not
    silently succeed (the pre-fix escape) -- and the refusal must name the
    documented repair command.
    """
    feature_dir = _build_wp_file(tmp_path, _MISSION, _WP_ID)
    _seed_bootstrap_planned(feature_dir, _WP_ID)
    assert not (feature_dir / "lanes.json").exists()
    ports = _fake_ports(feature_dir)

    with pytest.raises(typer.Exit) as exc_info:
        _run_move(tmp_path, ports)

    assert exc_info.value.exit_code == 1
    payload = json.loads(capsys.readouterr().out)
    message = payload.get("error", "")
    assert "planned" in message
    assert "spec-kitty doctor mission-state --fix" in message
    assert f"--mission {_MISSION}" in message


def test_move_task_leaving_planned_unaffected_when_lanes_json_present(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """T009 positive control: an ordinary move with ``lanes.json`` present is
    completely unaffected by the new guard (no new refusal)."""
    feature_dir = _build_wp_file(tmp_path, _MISSION, _WP_ID)
    _seed_bootstrap_planned(feature_dir, _WP_ID)
    write_lanes_json(
        feature_dir,
        LanesManifest(
            version=1,
            mission_slug=_MISSION,
            mission_id=None,
            mission_branch=f"kitty/mission-{_MISSION}",
            target_branch="wip-lane",
            lanes=[
                ExecutionLane(
                    lane_id="lane-a",
                    wp_ids=(_WP_ID,),
                    write_scope=(f"src/{_WP_ID.lower()}/**",),
                    predicted_surfaces=(),
                    depends_on_lanes=(),
                    parallel_group=0,
                )
            ],
            computed_at="2026-01-01T00:00:00+00:00",
            computed_from="dependency_graph+ownership",
            planning_commit_sha="a" * 40,
        ),
    )
    ports = _fake_ports(feature_dir)

    # No exception raised -- the transition proceeds exactly as before the guard.
    _run_move(tmp_path, ports)

    payload = json.loads(capsys.readouterr().out)
    assert payload["result"] == "success"
    assert payload["old_lane"] == "planned"
    assert payload["new_lane"] == "in_progress"
    assert ports.coord.status_calls  # at least one hop emitted


def test_move_task_already_past_planned_unaffected_by_missing_lanes_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """The guard is scoped to hops LEAVING ``planned`` only -- a WP already
    past ``planned`` (``claimed`` here) is unaffected by ``lanes.json``
    absence, matching the guard's stated scope (#4758 FR-002 is the
    ``planned`` escape specifically, not a blanket lanes.json requirement)."""
    feature_dir = _build_wp_file(tmp_path, _MISSION, _WP_ID)
    append_event(
        feature_dir,
        StatusEvent(
            event_id=f"test-{_WP_ID}-claimed",
            mission_slug=feature_dir.name,
            wp_id=_WP_ID,
            from_lane=Lane.PLANNED,
            to_lane=Lane.CLAIMED,
            at="2026-01-01T00:00:00+00:00",
            actor="codex",
            force=True,
            execution_mode="worktree",
            policy_metadata={"agent": "codex"},
        ),
    )
    assert not (feature_dir / "lanes.json").exists()
    ports = _fake_ports(feature_dir)

    # claimed -> in_progress never touches the planned-boundary guard.
    _run_move(tmp_path, ports, to="doing")

    payload = json.loads(capsys.readouterr().out)
    assert payload["result"] == "success"
    assert payload["old_lane"] == "claimed"
    assert payload["new_lane"] == "in_progress"
