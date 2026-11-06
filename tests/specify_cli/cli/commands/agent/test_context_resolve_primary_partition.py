"""FR-061: ``agent context resolve`` and ``check-prerequisites`` report the PRIMARY-partition location.

Mission lane-worktree-model-hardening (WP05), ADR ``2026-11-06-2`` "PRIMARY placement for default
Missions": a ``topology_source: default`` Mission keeps its PRIMARY partition on its topic branch
(``meta.mission_branch``) until consolidation lands it; an explicit ``--topology`` Mission keeps
today's placement (the target). Both commands agree with the read door's answer. The
post-settlement case (repository root checkout back on ``create_return_branch``) is WP14's.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from specify_cli.status.read_surface import resolve_primary_partition_dir
from tests.status.test_status_read_matrix import (
    LANES_WITH_COORD,
    MATERIALIZED,
    MISSION_BRANCH,
    SINGLE_BRANCH,
    SLUG,
    MatrixMission,
    build_matrix_mission,
    git,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

runner = CliRunner()


def _json_payload(stdout: str) -> dict[str, object]:
    start = stdout.find("{")
    assert start >= 0, stdout
    payload: dict[str, object] = json.loads(stdout[start:])
    return payload


def _add_planning_docs(mission: MatrixMission) -> None:
    (mission.root_mission_dir / "spec.md").write_text("# Spec\n", encoding="utf-8")
    (mission.root_mission_dir / "plan.md").write_text("# Plan\n", encoding="utf-8")


def _default_mission_on_topic_branch(tmp_path: Path) -> MatrixMission:
    mission = build_matrix_mission(tmp_path, SINGLE_BRANCH)
    meta_path = mission.root_mission_dir / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta.update({"topology_source": "default", "topology_settled": False, "create_return_branch": "main"})
    meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    _add_planning_docs(mission)
    git(mission.repo, "checkout", "-q", "-b", MISSION_BRANCH)
    git(mission.repo, "add", "-A")
    git(mission.repo, "commit", "-q", "-m", "default create")
    return mission


def _explicit_coord_mission(tmp_path: Path) -> MatrixMission:
    mission = build_matrix_mission(tmp_path, LANES_WITH_COORD, MATERIALIZED)
    _add_planning_docs(mission)
    git(mission.repo, "add", "-A")
    git(mission.repo, "commit", "-q", "-m", "planning docs")
    return mission


def _context_mission_dir(repo: Path) -> Path:
    from specify_cli.cli.commands.agent.context import app

    with patch("specify_cli.cli.commands.agent.context.locate_project_root", return_value=repo):
        result = runner.invoke(app, ["resolve", "--action", "tasks", "--mission", SLUG, "--json"])
    assert result.exit_code == 0, result.output
    return Path(str(_json_payload(result.stdout)["mission_dir"]))


def _prerequisites_mission_dir(repo: Path) -> Path:
    from specify_cli.cli.commands.agent.mission import app

    with (
        patch("specify_cli.cli.commands.agent.mission.locate_project_root", return_value=repo),
        patch("specify_cli.cli.commands.agent.mission._enforce_git_preflight"),
    ):
        result = runner.invoke(app, ["check-prerequisites", "--json", "--paths-only", "--mission", SLUG])
    assert result.exit_code == 0, result.output
    return Path(str(_json_payload(result.stdout)["feature_dir"]))


def test_context_resolve_mission_dir_is_primary_partition_location(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A default Mission held on its topic branch: both commands report the door's PRIMARY location."""
    mission = _default_mission_on_topic_branch(tmp_path)
    monkeypatch.chdir(mission.repo)

    primary = resolve_primary_partition_dir(mission.repo, SLUG)

    assert primary is not None
    assert primary.resolve() == mission.root_mission_dir.resolve()
    assert _context_mission_dir(mission.repo).resolve() == primary.resolve()
    assert _prerequisites_mission_dir(mission.repo).resolve() == primary.resolve()


def test_explicit_topology_mission_keeps_target_placement(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Positive control: an explicit ``--topology lanes_with_coord`` Mission reports today's location."""
    mission = _explicit_coord_mission(tmp_path)
    monkeypatch.chdir(mission.repo)

    assert resolve_primary_partition_dir(mission.repo, SLUG) is None
    assert _context_mission_dir(mission.repo).resolve() == mission.root_mission_dir.resolve()
    assert _prerequisites_mission_dir(mission.repo).resolve() == mission.root_mission_dir.resolve()
