"""``agent status materialize`` never writes to a read-only path (WP06, FR-005, FR-043).

Mission lane-worktree-model-hardening; ADR ``2026-11-06-2-one-status-read-contract``. With the
coordination worktree absent the declared source is the committed coordination branch, which has
no writable path: materialize reports the reduced snapshot and writes nothing, neither into the
lane checkout's fork-time copy nor into the repository root checkout's stale copy.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from tests.status.test_status_read_matrix import (
    LANES_WITH_COORD,
    MATERIALIZED,
    SLUG,
    UNMATERIALIZED,
    build_matrix_mission,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


def _tree_state(directory: Path) -> dict[str, bytes]:
    return {str(path.relative_to(directory)): path.read_bytes() for path in sorted(directory.rglob("*")) if path.is_file()}


def _materialize_json(cwd: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    from specify_cli.cli.commands.agent.status import app

    monkeypatch.chdir(cwd)
    result = CliRunner().invoke(app, ["materialize", "--mission", SLUG, "--json"])
    assert result.exit_code == 0, result.output
    line = next(line for line in result.output.splitlines() if line.strip().startswith("{"))
    payload: dict[str, object] = json.loads(line)
    return payload


@pytest.mark.parametrize("cwd_kind", ["root", "lane"])
def test_agent_status_materialize_never_writes_read_only_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, cwd_kind: str) -> None:
    """Coordination worktree absent: the snapshot is the branch's, and no file on disk changes."""
    mission = build_matrix_mission(tmp_path, LANES_WITH_COORD, UNMATERIALIZED)
    assert mission.lane_mission_dir is not None
    before_root = _tree_state(mission.root_mission_dir)
    before_lane = _tree_state(mission.lane_mission_dir)
    cwd = mission.repo if cwd_kind == "root" else mission.lane_worktree
    assert cwd is not None

    payload = _materialize_json(cwd, monkeypatch)

    work_packages = payload["work_packages"]
    assert isinstance(work_packages, dict)
    assert work_packages["WP01"]["lane"] == "in_progress"
    assert _tree_state(mission.root_mission_dir) == before_root
    assert _tree_state(mission.lane_mission_dir) == before_lane
    assert not (mission.repo / ".worktrees" / f"{SLUG}-coord").exists()


def test_agent_status_materialize_writes_the_coordination_worktree_when_present(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Positive control: a materialized coordination worktree is the write dir and gets ``status.json``."""
    mission = build_matrix_mission(tmp_path, LANES_WITH_COORD, MATERIALIZED)
    before_root = _tree_state(mission.root_mission_dir)

    payload = _materialize_json(mission.repo, monkeypatch)

    work_packages = payload["work_packages"]
    assert isinstance(work_packages, dict)
    assert work_packages["WP01"]["lane"] == "in_progress"
    assert (mission.coord_mission_dir / "status.json").is_file()
    assert _tree_state(mission.root_mission_dir) == before_root
