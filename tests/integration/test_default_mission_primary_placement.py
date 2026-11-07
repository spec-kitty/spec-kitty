"""FR-061 / analyze-3 H1: a default Mission's PRIMARY partition is pinned on its topic branch (#7282).

Before and after settlement (both outcomes), the placement seam reads and writes a
``topology_source: default`` Mission's PRIMARY artifacts (spec, tasks, WP files,
``lanes.json``, ``meta.json``) on the topic branch: the checkout that holds it. After a
``lanes_with_coord`` settlement that is the coordination worktree, because the repository
root checkout is back on ``create_return_branch``. Positive control: an explicit
``--topology lanes_with_coord`` Mission keeps PRIMARY on ``target_branch``. The
``consolidate`` landing leg is WP20's (FR-062) and is not asserted here.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from tests.specify_cli.cli.commands.agent.test_finalize_topology_settlement import (
    THREE_LANES,
    DefaultMission,
    _quiet_status_fanout,  # noqa: F401 -- autouse fixture re-exported into this module
    git,
    make_default_mission,
    run_finalize,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.non_sandbox]

_PRIMARY_KINDS = ("SPEC", "TASKS_INDEX", "WORK_PACKAGE_TASK", "PRIMARY_METADATA")


def _seam_dirs(mission: DefaultMission) -> dict[str, tuple[Path, str]]:
    from mission_runtime import MissionArtifactKind, placement_seam

    seam = placement_seam(mission.root, mission.slug)
    return {name: (seam.read_dir(MissionArtifactKind[name]), seam.write_target(MissionArtifactKind[name]).ref) for name in _PRIMARY_KINDS}


def _assert_primary_on(mission: DefaultMission, expected_dir: Path, expected_ref: str) -> None:
    for name, (read_dir, ref) in _seam_dirs(mission).items():
        assert read_dir.resolve() == expected_dir.resolve(), name
        assert ref == expected_ref, name


@pytest.mark.parametrize("owned", [("src/one.py", "src/two.py"), THREE_LANES], ids=["single_branch", "lanes_with_coord"])
def test_default_mission_primary_placement_topic_branch_pinned(tmp_path: Path, owned: tuple[str, ...]) -> None:
    mission = make_default_mission(tmp_path, owned)
    _assert_primary_on(mission, mission.root_mission_dir, mission.topic)

    code, payload = run_finalize(mission)
    assert code == 0, payload

    settled_dir = mission.coord_mission_dir if len(owned) == 3 else mission.root_mission_dir
    _assert_primary_on(mission, settled_dir, mission.topic)
    for name in ("spec.md", "tasks.md", "lanes.json", "meta.json"):
        assert git(mission.root, "cat-file", "-e", f"{mission.topic}:kitty-specs/{mission.slug}/{name}") == ""


def test_explicit_lanes_with_coord_keeps_primary_on_target(tmp_path: Path) -> None:
    mission = make_default_mission(tmp_path, THREE_LANES, explicit="lanes_with_coord", standing_on="work")
    assert run_finalize(mission)[0] == 0
    _assert_primary_on(mission, mission.root_mission_dir, "work")


def _json(stdout: str) -> dict[str, object]:
    payload: dict[str, object] = json.loads(stdout[stdout.find("{") :])
    return payload


def test_context_resolve_and_prerequisites_report_primary_location_after_settlement(tmp_path: Path) -> None:
    from specify_cli.cli.commands.agent.context import app as context_app
    from specify_cli.cli.commands.agent.mission import app as mission_app

    mission = make_default_mission(tmp_path, THREE_LANES)
    assert run_finalize(mission)[0] == 0
    assert git(mission.root, "branch", "--show-current") == mission.return_branch
    runner = CliRunner()

    with patch("specify_cli.cli.commands.agent.context.locate_project_root", return_value=mission.root):
        resolved = runner.invoke(context_app, ["--action", "implement", "--mission", mission.slug, "--json"])
    assert resolved.exit_code == 0, resolved.output
    assert Path(str(_json(resolved.stdout)["mission_dir"])).resolve() == mission.coord_mission_dir.resolve()

    with (
        patch("specify_cli.cli.commands.agent.mission.locate_project_root", return_value=mission.root),
        patch("specify_cli.cli.commands.agent.mission._enforce_git_preflight"),
    ):
        prereq = runner.invoke(mission_app, ["check-prerequisites", "--json", "--paths-only", "--mission", mission.slug])
    assert prereq.exit_code == 0, prereq.output
    assert Path(str(_json(prereq.stdout)["feature_dir"])).resolve() == mission.coord_mission_dir.resolve()


def test_status_write_after_root_moved_is_readable_through_the_door(tmp_path: Path) -> None:
    """WP05 review obligation N1: write side aligned with the read door, read-after-write.

    The repository root checkout moved to ``main`` while still carrying a stale copy of the
    Mission directory; a linked checkout holds the topic branch. A status write must land
    in the topic holder, where the door reads it, never in the root's stale copy.
    """
    from mission_runtime import MissionArtifactKind, placement_seam
    from specify_cli.status.emit import emit_status_transition
    from specify_cli.status.read_surface import read_status_events, resolve_status_read

    mission = make_default_mission(tmp_path, ("src/one.py", "src/two.py"))
    assert run_finalize(mission)[0] == 0
    git(mission.root, "checkout", "-q", "main")
    holder = tmp_path / "topic-holder"
    git(mission.root, "worktree", "add", "-q", str(holder), mission.topic)
    shutil.copytree(holder / "kitty-specs" / mission.slug, mission.root_mission_dir, dirs_exist_ok=True)
    held_dir = holder / "kitty-specs" / mission.slug

    write_dir = placement_seam(mission.root, mission.slug).write_dir(MissionArtifactKind.STATUS_STATE).path
    assert write_dir.resolve() == held_dir.resolve()
    emit_status_transition(mission_dir=write_dir, mission_slug=mission.slug, wp_id="WP01", to_lane="claimed", actor="claude")

    surface = resolve_status_read(mission.root, mission.slug)
    events = read_status_events(surface)
    assert surface.path is not None and surface.path.resolve() == held_dir.resolve(), surface
    assert any(event.wp_id == "WP01" and str(event.to_lane) == "claimed" for event in events)

    # The transactional door (move-task) writes and commits on the topic holder too.
    from specify_cli.coordination.status_transition import emit_status_transition_transactional
    from specify_cli.status.models import TransitionRequest

    emit_status_transition_transactional(TransitionRequest(mission_dir=write_dir, mission_slug=mission.slug, wp_id="WP02", to_lane="claimed", actor="claude"))
    events = read_status_events(resolve_status_read(mission.root, mission.slug))
    assert any(event.wp_id == "WP02" and str(event.to_lane) == "claimed" for event in events)
    assert "claimed" in git(holder, "show", f"HEAD:kitty-specs/{mission.slug}/status.events.jsonl")
    stale = (mission.root_mission_dir / "status.events.jsonl").read_text(encoding="utf-8")
    assert '"to_lane":"claimed"' not in stale.replace(" ", "")
