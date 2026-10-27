"""#5466: ``events tail`` reads the resolved status surface, not the primary checkout.

On a coordination-routed Mission (``coord`` / ``lanes_with_coord``) every work
package transition is appended to the coordination worktree's
``status.events.jsonl``. ``events tail`` built its log path from
``resolve_mission_handle(...).feature_dir`` (the primary checkout), so it showed
none of those transitions and exited 0. It now resolves the log through
``resolve_status_surface``, the resolver every status writer uses.

Real git fixtures throughout (``tests._factories.coord_mission``), nothing in the
resolution chain mocked. Every invocation is ``--once`` or ``--max-events N``, so
no test blocks.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner, Result

from mission_runtime import MissionTopology
from specify_cli.cli.commands import events as events_cli
from tests._factories.coord_mission import (
    COORD_TOPOLOGIES,
    CoordMission,
    make_coord_mission,
    make_prefix_coord_mission,
)
from tests.integration.test_placement_partition_golden_path import _create_mission, _init_git_repo

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

runner = CliRunner()

# Production mounts ``events.app`` under a named group; a bare single-command
# Typer app would collapse ``tail`` (see test_events_tail.py's docstring).
_root_app = typer.Typer()
_root_app.add_typer(events_cli.app, name="events")

_STATUS_LOG = "status.events.jsonl"


def _tail(repo_root: Path, mission: str, *extra: str) -> Result:
    return runner.invoke(
        _root_app,
        ["events", "tail", "--mission", mission, *extra],
        env={"SPECIFY_REPO_ROOT": str(repo_root)},
    )


def _wp_transition(event_id: str, from_lane: str, to_lane: str) -> dict[str, object]:
    return {
        "actor": "claude",
        "at": "2026-10-27T12:00:00+00:00",
        "event_id": event_id,
        "evidence": None,
        "execution_mode": "worktree",
        "force": False,
        "from_lane": from_lane,
        "reason": None,
        "review_ref": None,
        "to_lane": to_lane,
        "wp_id": "WP01",
    }


def _append(log: Path, rows: list[dict[str, object]]) -> None:
    with log.open("a", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")


def _event_ids(log: Path) -> list[str]:
    return [json.loads(line)["event_id"] for line in log.read_text(encoding="utf-8").splitlines() if line.strip()]


def _stdout_rows(result: Result) -> list[dict[str, object]]:
    return [json.loads(line) for line in result.stdout.splitlines() if line.strip()]


def _coord_with_wp_transitions(tmp_path: Path, topology: MissionTopology) -> CoordMission:
    coord = make_coord_mission(tmp_path, topology, materialized=True)
    _append(
        coord.coord_mission_dir / _STATUS_LOG,
        [
            _wp_transition("01EVTAILWP01CLAIMED0000000", "planned", "claimed"),
            _wp_transition("01EVTAILWP01INPROGRESS0000", "claimed", "in_progress"),
            _wp_transition("01EVTAILWP01FORREVIEW00000", "in_progress", "for_review"),
        ],
    )
    return coord


@pytest.mark.parametrize("topology", COORD_TOPOLOGIES)
def test_once_tails_the_coordination_log(tmp_path: Path, topology: MissionTopology) -> None:
    coord = _coord_with_wp_transitions(tmp_path, topology)
    coord_log = coord.coord_mission_dir / _STATUS_LOG

    result = _tail(coord.repo_root, coord.mission_dir_name, "--once")

    assert result.exit_code == 0, result.output
    rows = _stdout_rows(result)
    assert [row["event_id"] for row in rows] == _event_ids(coord_log)
    assert [row["to_lane"] for row in rows if row.get("wp_id") == "WP01"] == ["claimed", "in_progress", "for_review"]


# Bounded so the pre-fix red (a stream over the empty primary path waits forever) fails, not hangs.
@pytest.mark.timeout(60)
@pytest.mark.parametrize("topology", COORD_TOPOLOGIES)
def test_stream_tails_the_coordination_log(tmp_path: Path, topology: MissionTopology) -> None:
    coord = _coord_with_wp_transitions(tmp_path, topology)
    coord_log = coord.coord_mission_dir / _STATUS_LOG
    expected = _event_ids(coord_log)

    result = _tail(coord.repo_root, coord.mission_dir_name, "--max-events", str(len(expected)))

    assert result.exit_code == 0, result.output
    assert [row["event_id"] for row in _stdout_rows(result)] == expected


def test_resume_cursor_is_validated_against_the_coordination_log(tmp_path: Path) -> None:
    """An offset taken from the coordination log resumes there, not in the primary checkout."""
    coord = _coord_with_wp_transitions(tmp_path, MissionTopology.COORD)
    coord_log = coord.coord_mission_dir / _STATUS_LOG
    lines = coord_log.read_bytes().splitlines(keepends=True)
    offset = sum(len(line) for line in lines[:-1])

    result = _tail(coord.repo_root, coord.mission_dir_name, "--once", "--from-offset", str(offset))

    assert result.exit_code == 0, result.output
    assert [row["event_id"] for row in _stdout_rows(result)] == _event_ids(coord_log)[-1:]


def test_empty_coordination_surface_tails_the_primary_log(tmp_path: Path) -> None:
    """A Mission created before the coordination seed (EMPTY coordination
    worktree) keeps its log in the primary checkout; the resolver says so and
    ``events tail`` follows it."""
    coord = make_prefix_coord_mission(tmp_path, MissionTopology.COORD, worktree="empty")
    root_log = coord.root_mission_dir / _STATUS_LOG

    result = _tail(coord.repo_root, coord.mission_dir_name, "--once")

    assert result.exit_code == 0, result.output
    assert [row["event_id"] for row in _stdout_rows(result)] == _event_ids(root_log)
    assert _event_ids(root_log)


def test_deleted_coordination_branch_refuses_on_stderr(tmp_path: Path) -> None:
    """The resolver fails closed when the declared coordination branch is gone;
    ``events tail`` reports that instead of silently tailing the primary checkout."""
    coord = make_prefix_coord_mission(tmp_path, MissionTopology.COORD, branch_deleted=True)

    result = _tail(coord.repo_root, coord.mission_dir_name, "--once")

    assert result.exit_code == 1
    assert result.stdout == ""
    envelope = json.loads(result.stderr)
    assert envelope["error"] == "status_surface_unavailable"
    assert coord.coordination_branch in envelope["detail"]


def test_lanes_mission_tails_the_primary_log(tmp_path: Path) -> None:
    """Control: a Mission with no coordination topology keeps tailing its primary log."""
    _init_git_repo(tmp_path, branch="topic")
    created = _create_mission(tmp_path, "lanes-events-tail", MissionTopology.LANES)
    primary_log = created.feature_dir / _STATUS_LOG
    _append(primary_log, [_wp_transition("01EVTAILLANESWP01CLAIMED00", "planned", "claimed")])

    result = _tail(tmp_path, created.feature_dir.name, "--once")

    assert result.exit_code == 0, result.output
    assert [row["event_id"] for row in _stdout_rows(result)] == _event_ids(primary_log)
