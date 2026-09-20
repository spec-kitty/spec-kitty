"""#4758 regression: legacy ``agent tasks finalize-tasks`` never half-finalizes.

Mission ``canonical-state-recovery-01M2ZE3D`` / WP01.

Reproduced live (research.md): ``agent tasks finalize-tasks`` bootstraps
canonical status -- seeding ``genesis -> planned`` events for every WP -- but
never wrote ``lanes.json``. Once seeded, ``move-task --to doing`` would walk a
WP straight from ``planned`` to ``in_progress`` with no lanes on disk to
resolve a worktree from: a wedged, unrecoverable mission (FR-001, SC-001).

T001: this is the pinned RED-first regression proving the desired post-state
(lanes present alongside the bootstrapped events) through the pre-existing
``agent tasks finalize-tasks`` CLI entry point -- not a unit test of an
internal helper. Confirmed RED on the pre-fix tree (see the WP01 report).
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.agent.tasks import app
from specify_cli.lanes.persistence import read_lanes_json
from specify_cli.status.lane_reader import get_all_wp_lanes, has_event_log
from specify_cli.status.models import Lane

pytestmark = pytest.mark.regression

runner = CliRunner()

_MISSION_SLUG = "060-lanes-minting"


def _build_feature_with_owned_wps(tmp_path: Path, mission_slug: str) -> Path:
    """Fresh mission: tasks.md + two code-change WPs with disjoint owned_files.

    Also creates the files each WP's glob pattern matches, so lane
    computation hits the happy path with zero glob-validation warnings.
    """
    feature_dir = tmp_path / "kitty-specs" / mission_slug
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    (tmp_path / ".kittify").mkdir(exist_ok=True)

    (feature_dir / "meta.json").write_text(
        json.dumps({"mission_type": "software-dev", "mission_id": "01ARZ3NDEKTSV4RRFFQ69G5FAV"}),
        encoding="utf-8",
    )
    (feature_dir / "tasks.md").write_text(
        "## Work Package WP01\n\nSetup work.\n\n## Work Package WP02\n\n",
        encoding="utf-8",
    )
    for wp_id in ("WP01", "WP02"):
        (tmp_path / "src" / wp_id.lower()).mkdir(parents=True)
        (tmp_path / "src" / wp_id.lower() / "mod.py").write_text("x = 1\n", encoding="utf-8")
        (tasks_dir / f"{wp_id}-test.md").write_text(
            f"---\n"
            f"work_package_id: {wp_id}\n"
            f"title: Test {wp_id}\n"
            f"execution_mode: code_change\n"
            f"owned_files:\n  - src/{wp_id.lower()}/**\n"
            f"authoritative_surface: src/{wp_id.lower()}/\n"
            f"---\n\n# {wp_id}\n\n## Activity Log\n",
            encoding="utf-8",
        )
    return feature_dir


@patch("specify_cli.cli.commands.agent.tasks._ensure_target_branch_checked_out")
@patch("specify_cli.cli.commands.agent.tasks.locate_project_root")
@patch("specify_cli.cli.commands.agent.tasks._find_mission_slug")
def test_finalize_tasks_never_seeds_events_without_lanes(
    mock_slug: MagicMock,
    mock_root: MagicMock,
    mock_branch: MagicMock,
    tmp_path: Path,
) -> None:
    """#4758: after a fresh finalize-tasks run, lanes.json exists alongside events.

    RED on the pre-fix tree: ``bootstrap_canonical_state`` ran (the event log
    existed with every WP at ``planned``) but ``lanes.json`` was absent --
    exactly the wedge ``move-task`` can then walk a WP out of ``planned``
    through, with no lanes to resolve a worktree from.

    GREEN post-fix: either lanes.json is written (this scenario -- a fresh
    mission with real ownership declared, execution not yet begun) or the
    command refuses outright naming the repair path; it never leaves events
    seeded with lanes.json absent.
    """
    feature_dir = _build_feature_with_owned_wps(tmp_path, _MISSION_SLUG)

    mock_root.return_value = tmp_path
    mock_slug.return_value = _MISSION_SLUG
    mock_branch.return_value = (tmp_path, "main")

    result = runner.invoke(app, ["finalize-tasks", "--mission", _MISSION_SLUG, "--json"])
    assert result.exit_code == 0, f"CLI error: {result.output}"

    # The bug: events seeded (has_event_log True) but lanes.json absent.
    # The fix: whenever events are seeded, lanes.json must also be present.
    events_seeded = has_event_log(feature_dir)
    lanes = read_lanes_json(feature_dir)
    assert events_seeded, "expected finalize-tasks to bootstrap the event log"
    assert lanes is not None, "#4758 regression: finalize-tasks seeded genesis->planned events but left lanes.json absent -- a wedged, unrecoverable mission."

    # Every WP the event log knows about is planned (fresh mission) and lanes
    # covers the same WP ids -- so a subsequent move-task has lanes to
    # resolve a worktree from instead of wedging.
    wp_lanes = get_all_wp_lanes(feature_dir)
    assert set(wp_lanes) == {"WP01", "WP02"}
    assert all(lane == Lane.PLANNED for lane in wp_lanes.values())
    lanes_wp_ids = {wp_id for lane_entry in lanes.lanes for wp_id in lane_entry.wp_ids}
    assert lanes_wp_ids == {"WP01", "WP02"}


@patch("specify_cli.cli.commands.agent.tasks._ensure_target_branch_checked_out")
@patch("specify_cli.cli.commands.agent.tasks.locate_project_root")
@patch("specify_cli.cli.commands.agent.tasks._find_mission_slug")
def test_finalize_tasks_is_idempotent_once_lanes_exist(
    mock_slug: MagicMock,
    mock_root: MagicMock,
    mock_branch: MagicMock,
    tmp_path: Path,
) -> None:
    """#3311 guard preserved: a second finalize-tasks run never rewrites lanes.json."""
    feature_dir = _build_feature_with_owned_wps(tmp_path, _MISSION_SLUG)

    mock_root.return_value = tmp_path
    mock_slug.return_value = _MISSION_SLUG
    mock_branch.return_value = (tmp_path, "main")

    first = runner.invoke(app, ["finalize-tasks", "--mission", _MISSION_SLUG, "--json"])
    assert first.exit_code == 0, f"CLI error: {first.output}"
    first_lanes_bytes = (feature_dir / "lanes.json").read_bytes()

    second = runner.invoke(app, ["finalize-tasks", "--mission", _MISSION_SLUG, "--json"])
    assert second.exit_code == 0, f"CLI error: {second.output}"
    second_lanes_bytes = (feature_dir / "lanes.json").read_bytes()

    assert first_lanes_bytes == second_lanes_bytes
