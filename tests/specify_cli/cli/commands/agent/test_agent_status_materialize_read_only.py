"""``agent status materialize`` writes only into a checkout, and says so (WP06, FR-005, FR-043).

Mission lane-worktree-model-hardening; ADR ``2026-11-06-2-one-status-read-contract``.

* A source with a checkout path (``WRITE_CHECKOUT``, ``COORD_WORKTREE`` and, for a landed Mission
  on every topology, ``CONSOLIDATED_TARGET``) gets ``status.json`` written there.
* A pure ref source (``COORD_BRANCH_REF``, ``MISSION_BRANCH_REF``) has no checkout to write: the
  command refuses with an actionable remedy, never prints "Materialized", and writes nothing,
  neither into the lane checkout's fork-time copy nor into the repository root checkout's stale
  copy. Following the remedy leads to a successful materialize.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

from tests.status.test_status_read_matrix import (
    COORD_BRANCH,
    KITTY_SPECS,
    LANES,
    LANES_WITH_COORD,
    MATERIALIZED,
    SINGLE_BRANCH,
    SLUG,
    UNMATERIALIZED,
    build_matrix_mission,
    git,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

STATUS_JSON = "status.json"
MATERIALIZED_LINE = "Materialized"
REF_REFUSAL_CODE = "status_surface_on_ref"
TOP_LEVEL_REMEDY = f"spec-kitty materialize --mission {SLUG}"


def _tree_state(directory: Path) -> dict[str, bytes]:
    return {str(path.relative_to(directory)): path.read_bytes() for path in sorted(directory.rglob("*")) if path.is_file()}


def _invoke_status(cwd: Path, monkeypatch: pytest.MonkeyPatch, *args: str) -> tuple[int, str]:
    from specify_cli.cli.commands.agent.status import app

    monkeypatch.chdir(cwd)
    result = CliRunner().invoke(app, list(args))
    assert result.exception is None or isinstance(result.exception, SystemExit), repr(result.exception)
    return result.exit_code, result.output


def _first_json(output: str) -> dict[str, object]:
    line = next(line for line in output.splitlines() if line.strip().startswith("{"))
    payload: dict[str, object] = json.loads(line)
    return payload


def _materialize_json(cwd: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    exit_code, output = _invoke_status(cwd, monkeypatch, "materialize", "--mission", SLUG, "--json")
    assert exit_code == 0, output
    return _first_json(output)


def _empty_coordination_worktree(repo: Path) -> None:
    coord_worktree = repo / ".worktrees" / f"{SLUG}-coord"
    git(repo, "worktree", "add", "-q", str(coord_worktree), COORD_BRANCH)
    shutil.rmtree(coord_worktree / KITTY_SPECS / SLUG)


def _mark_landed(mission_dir: Path, repo: Path) -> None:
    meta_path = mission_dir / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["merged_at"] = "2026-11-06T01:00:00+00:00"
    meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "landed")


# ---------------------------------------------------------------------------
# Pure ref sources: refuse, write nothing, never claim success
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("coord_state", ["absent", "empty"])
@pytest.mark.parametrize("cwd_kind", ["root", "lane"])
def test_materialize_refuses_a_ref_source_and_writes_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, cwd_kind: str, coord_state: str) -> None:
    """Coordination worktree absent or empty: the source is the committed branch, which has no checkout."""
    mission = build_matrix_mission(tmp_path, LANES_WITH_COORD, UNMATERIALIZED)
    if coord_state == "empty":
        _empty_coordination_worktree(mission.repo)
    assert mission.lane_mission_dir is not None
    before_root = _tree_state(mission.root_mission_dir)
    before_lane = _tree_state(mission.lane_mission_dir)
    cwd = mission.repo if cwd_kind == "root" else mission.lane_worktree
    assert cwd is not None

    exit_code, human = _invoke_status(cwd, monkeypatch, "materialize", "--mission", SLUG)
    json_exit, json_output = _invoke_status(cwd, monkeypatch, "materialize", "--mission", SLUG, "--json")

    assert exit_code == 1, human
    assert MATERIALIZED_LINE not in human
    flat = " ".join(human.split())
    assert "did not write status.json" in flat
    assert TOP_LEVEL_REMEDY in flat
    assert json_exit == 1, json_output
    payload = _first_json(json_output)
    assert payload["error_code"] == REF_REFUSAL_CODE
    assert payload["source"] == "coord_branch_ref"
    assert payload["ref"] == f"refs/heads/{COORD_BRANCH}"
    assert TOP_LEVEL_REMEDY in str(payload["remedy"])
    assert _tree_state(mission.root_mission_dir) == before_root
    assert _tree_state(mission.lane_mission_dir) == before_lane
    coord_dir = mission.repo / ".worktrees" / f"{SLUG}-coord" / KITTY_SPECS / SLUG
    assert not (coord_dir / STATUS_JSON).exists()


@pytest.mark.parametrize("coord_state", ["absent", "empty"])
def test_the_ref_source_remedy_leads_to_a_written_status_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, coord_state: str) -> None:
    """Following the refusal's remedy (``spec-kitty materialize``) gives the Mission a checkout to write."""
    from specify_cli.cli.commands.materialize import materialize as top_level_materialize

    mission = build_matrix_mission(tmp_path, LANES_WITH_COORD, UNMATERIALIZED)
    if coord_state == "empty":
        _empty_coordination_worktree(mission.repo)
    monkeypatch.chdir(mission.repo)
    top_level = typer.Typer()
    top_level.command()(top_level_materialize)
    remedy = CliRunner().invoke(top_level, ["--mission", SLUG])
    assert remedy.exit_code == 0, remedy.output

    payload = _materialize_json(mission.repo, monkeypatch)

    work_packages = payload["work_packages"]
    assert isinstance(work_packages, dict)
    assert work_packages["WP01"]["lane"] == "in_progress"
    assert (mission.coord_mission_dir / STATUS_JSON).is_file()


def test_ref_source_remedy_names_a_checkout_for_each_ref_source(tmp_path: Path) -> None:
    """The remedy text per ref source: the coordination worktree, or the Mission topic branch."""
    from mission_runtime import MissionTopology

    from specify_cli.status.read_surface import StatusReadSource, StatusReadSurface, ref_source_remedy

    coord = StatusReadSurface(
        topology=MissionTopology.LANES_WITH_COORD,
        source=StatusReadSource.COORD_BRANCH_REF,
        mission_dir_name=f"{SLUG}-coord",
        path=None,
        repo_root=tmp_path,
        ref=f"refs/heads/{COORD_BRANCH}",
    )
    topic = StatusReadSurface(
        topology=MissionTopology.SINGLE_BRANCH,
        source=StatusReadSource.MISSION_BRANCH_REF,
        mission_dir_name=SLUG,
        path=None,
        repo_root=tmp_path,
        ref="refs/heads/kitty/mission-topic",
    )

    assert TOP_LEVEL_REMEDY in ref_source_remedy(coord, SLUG)
    topic_remedy = ref_source_remedy(topic, SLUG)
    assert "git switch kitty/mission-topic" in topic_remedy
    assert "git worktree add <path> kitty/mission-topic" in topic_remedy


# ---------------------------------------------------------------------------
# Sources with a checkout: status.json is written
# ---------------------------------------------------------------------------


def test_agent_status_materialize_writes_the_coordination_worktree_when_present(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Positive control: a materialized coordination worktree is the write dir and gets ``status.json``."""
    mission = build_matrix_mission(tmp_path, LANES_WITH_COORD, MATERIALIZED)
    before_root = _tree_state(mission.root_mission_dir)

    payload = _materialize_json(mission.repo, monkeypatch)

    work_packages = payload["work_packages"]
    assert isinstance(work_packages, dict)
    assert work_packages["WP01"]["lane"] == "in_progress"
    assert (mission.coord_mission_dir / STATUS_JSON).is_file()
    assert _tree_state(mission.root_mission_dir) == before_root


@pytest.mark.parametrize(
    ("topology", "coord_state"),
    [
        (SINGLE_BRANCH, "n/a"),
        (LANES, "n/a"),
        (LANES_WITH_COORD, MATERIALIZED),
        (LANES_WITH_COORD, UNMATERIALIZED),
    ],
)
def test_materialize_writes_status_json_for_a_landed_mission(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, topology: str, coord_state: str) -> None:
    """``CONSOLIDATED_TARGET`` is a checkout path: materialize writes there, and validate stops asking for it."""
    from specify_cli.status.read_surface import StatusReadSource, resolve_status_read

    mission = build_matrix_mission(tmp_path, topology, coord_state)
    _mark_landed(mission.root_mission_dir, mission.repo)
    (mission.root_mission_dir / STATUS_JSON).unlink(missing_ok=True)
    assert resolve_status_read(mission.repo, SLUG).source is StatusReadSource.CONSOLIDATED_TARGET

    exit_code, human = _invoke_status(mission.repo, monkeypatch, "materialize", "--mission", SLUG)

    assert exit_code == 0, human
    assert MATERIALIZED_LINE in human
    assert (mission.root_mission_dir / STATUS_JSON).is_file()
    _validate_exit, validate_output = _invoke_status(mission.repo, monkeypatch, "validate", "--mission", SLUG, "--json")
    assert "status.json is missing" not in validate_output
