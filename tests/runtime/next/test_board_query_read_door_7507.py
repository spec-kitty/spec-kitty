"""``next`` reads a coordination Mission's status through the read door (#7507, #7310 WP04).

Mission ``runtime-status-read-door-01M73HHB`` (FR-001, FR-002, FR-005, FR-006, FR-008).

The #7507 cells: a non-owned coordination Mission with WP01 ``planned`` and WP02 ``for_review``
committed on the coordination branch. With the coordination worktree **materialized** (the
control), **empty** (the Mission directory removed from the worktree) or **unmaterialized** (the
worktree removed), query mode reports the committed lanes, the same in all three cells. The board
selector dispatches WP01 from a materialized or empty worktree and keeps today's named
"materialize it" block for an unmaterialized one.

The owned cells (DM-1): an owned coordination query on an empty or unmaterialized worktree reads
the committed branch; the owned board on those cells keeps today's decline.

FR-008: one door read per board decision and per query, proven with a counting spy.
"""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from mission_runtime import MissionArtifactKind, MissionTopology, OwnedCheckout, placement_seam
from runtime.next import board_status as board_status_mod
from runtime.next import runtime_bridge_decision_mapping as decision_mapping
from runtime.next.runtime_bridge import query_current_state
from specify_cli.coordination.surface_resolver import CoordinationWorktreeUnmaterialized
from specify_cli.status import read_surface
from tests.runtime._next_mission_scaffold import analysis_is_current, scaffold_coord_software_dev

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

MATERIALIZED = "materialized"
EMPTY = "empty"
UNMATERIALIZED = "unmaterialized"
CELLS = [MATERIALIZED, EMPTY, UNMATERIALIZED]
COORD_TOPOLOGIES = [MissionTopology.COORD, MissionTopology.LANES_WITH_COORD]

_EXPECTED_PROGRESS = {
    "total_wps": 2,
    "done_wps": 0,
    "approved_wps": 0,
    "in_progress_wps": 0,
    "planned_wps": 1,
    "for_review_wps": 1,
    "weighted_percentage": 30.0,
}


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, check=True)


def _coord_cell_mission(tmp_path: Path, topology: MissionTopology, cell: str) -> tuple[Path, str]:
    """Build the #7507 Mission and put its coordination worktree in *cell*. Returns ``(repo, slug)``."""
    repo = tmp_path / "repo"
    repo.mkdir()
    feature_dir, coord_mission_dir = scaffold_coord_software_dev(
        repo,
        f"door-7507-{topology.value.replace('_', '-')}-{cell}",
        topology,
        wps={"WP01": "planned", "WP02": "for_review"},
    )
    coord_root = coord_mission_dir.parent.parent
    # Commit the coordination log so the coordination branch holds the authority.
    _git(coord_root, "add", "-A")
    _git(coord_root, "commit", "-q", "-m", "seed coordination log")
    if cell == EMPTY:
        shutil.rmtree(coord_mission_dir)
    elif cell == UNMATERIALIZED:
        _git(repo, "worktree", "remove", "--force", str(coord_root))
        assert not coord_root.exists()
    return repo, feature_dir.name


# ---------------------------------------------------------------------------
# T016: the #7507 cells (non-owned)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("cell", CELLS)
@pytest.mark.parametrize("topology", COORD_TOPOLOGIES, ids=lambda t: t.value)
def test_query_reads_the_committed_lanes_in_every_cell(tmp_path: Path, topology: MissionTopology, cell: str) -> None:
    """FR-001 / SC-001: the empty and unmaterialized cells report what the materialized control does."""
    repo, slug = _coord_cell_mission(tmp_path, topology, cell)

    decision = query_current_state("pedro", slug, repo, analysis_currency=analysis_is_current)

    assert str(decision.kind) == "query"
    assert decision.mission_state == "implement", decision.reason
    assert decision.wp_id == "WP01"
    assert decision.progress == _EXPECTED_PROGRESS


@pytest.mark.parametrize("cell", [MATERIALIZED, EMPTY])
@pytest.mark.parametrize("topology", COORD_TOPOLOGIES, ids=lambda t: t.value)
def test_board_dispatches_wp01_from_a_materialized_or_empty_worktree(tmp_path: Path, topology: MissionTopology, cell: str) -> None:
    """FR-002: an empty worktree dispatches from the committed lanes (today: ``blocked:no_actionable_wp``)."""
    repo, slug = _coord_cell_mission(tmp_path, topology, cell)

    board = decision_mapping._resolve_wp_board_action(mission_slug=slug, repo_root=repo)

    assert board.blocked_reason is None, board.blocked_reason
    assert board.board_step == "implement"
    assert board.action == "implement"
    assert board.wp_id == "WP01"


@pytest.mark.parametrize("topology", COORD_TOPOLOGIES, ids=lambda t: t.value)
def test_board_keeps_the_named_block_for_an_unmaterialized_worktree(tmp_path: Path, topology: MissionTopology) -> None:
    """FR-002: the unmaterialized cell keeps today's block, byte for byte.

    The oracle is the exception the placement seam raises for this cell today: the block's text
    has one composer (the exception's own ``next_step``).
    """
    repo, slug = _coord_cell_mission(tmp_path, topology, UNMATERIALIZED)
    with pytest.raises(CoordinationWorktreeUnmaterialized) as raised:
        placement_seam(repo, slug).read_dir(MissionArtifactKind.STATUS_STATE)
    exc = raised.value
    expected = f"Coordination surface for mission {slug!r} is not readable ({exc}). {exc.next_step}"

    board = decision_mapping._resolve_wp_board_action(mission_slug=slug, repo_root=repo)

    assert board.action is None
    assert board.board_step is None
    assert board.blocked_reason == expected
    assert "unmaterializ" in expected.lower()
    assert f"spec-kitty doctor coordination --mission {slug} --fix" in expected


# ---------------------------------------------------------------------------
# T017: owned coordination query and board (DM-1, FR-005, FR-006)
# ---------------------------------------------------------------------------


def _owned_coordination_mission(tmp_path: Path, topology: MissionTopology, cell: str) -> tuple[Path, OwnedCheckout]:
    """The WP02 owned matrix Mission (WP01 ``in_progress`` on the branch), with a finalized task board in P."""
    from tests._factories import provision_test_charter
    from tests.status.test_read_surface_owned_coordination import _coord_worktree, _owned_only_coordination_mission
    from tests.status.test_status_read_matrix import KITTY_SPECS, MATERIALIZED as MATRIX_MATERIALIZED, SLUG

    repo, fact = _owned_only_coordination_mission(tmp_path, topology, MATRIX_MATERIALIZED)
    (fact.mission_dir / "tasks.md").write_text("# Tasks\n", encoding="utf-8")
    provision_test_charter(repo)
    provision_test_charter(fact.owned_root)
    if cell == EMPTY:
        shutil.rmtree(_coord_worktree(repo) / KITTY_SPECS / SLUG)
    elif cell == UNMATERIALIZED:
        _git(repo, "worktree", "remove", "--force", str(_coord_worktree(repo)))
    return repo, fact


@pytest.mark.parametrize("cell", [EMPTY, UNMATERIALIZED])
@pytest.mark.parametrize("topology", COORD_TOPOLOGIES, ids=lambda t: t.value)
def test_owned_query_reads_the_committed_branch(tmp_path: Path, topology: MissionTopology, cell: str) -> None:
    """FR-005: today the empty cell raises ``MissionNotFoundError`` and the unmaterialized cell shows no lanes."""
    repo, fact = _owned_coordination_mission(tmp_path, topology, cell)

    decision = query_current_state("pedro", fact.mission_slug, repo, owned=fact, analysis_currency=analysis_is_current)

    assert str(decision.kind) == "query"
    assert decision.progress is not None
    assert decision.progress["total_wps"] == 1
    assert decision.progress["in_progress_wps"] == 1, decision.progress
    assert decision.mission_state == "implement", decision.reason


@pytest.mark.parametrize("cell", [EMPTY, UNMATERIALIZED])
@pytest.mark.parametrize("topology", COORD_TOPOLOGIES, ids=lambda t: t.value)
def test_owned_board_declines_on_a_missing_coordination_workspace(tmp_path: Path, topology: MissionTopology, cell: str) -> None:
    """FR-006: dispatch never runs from a missing owned coordination workspace (today's outcome kept)."""
    repo, fact = _owned_coordination_mission(tmp_path, topology, cell)

    board = decision_mapping._resolve_wp_board_action(mission_slug=fact.mission_slug, repo_root=repo, owned=fact)

    assert board is decision_mapping._WP_BOARD_DECLINE


# ---------------------------------------------------------------------------
# FR-008: one door read per decision
# ---------------------------------------------------------------------------


def _counting(monkeypatch: pytest.MonkeyPatch, owner: Any, name: str) -> list[object]:
    calls: list[object] = []
    real: Callable[..., Any] = getattr(owner, name)

    def _spy(*args: Any, **kwargs: Any) -> Any:
        calls.append(args)
        return real(*args, **kwargs)

    monkeypatch.setattr(owner, name, _spy)
    return calls


@pytest.mark.parametrize("cell", [MATERIALIZED, EMPTY])
def test_query_reads_the_door_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, cell: str) -> None:
    repo, slug = _coord_cell_mission(tmp_path, MissionTopology.COORD, cell)
    door_reads = _counting(monkeypatch, read_surface, "resolve_status_read")
    stream_reads = _counting(monkeypatch, board_status_mod, "read_status_stream")

    decision = query_current_state("pedro", slug, repo, analysis_currency=analysis_is_current)

    assert decision.wp_id == "WP01"
    assert len(door_reads) == 1
    assert len(stream_reads) == 1


@pytest.mark.parametrize("cell", [MATERIALIZED, EMPTY])
def test_board_reads_the_door_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, cell: str) -> None:
    repo, slug = _coord_cell_mission(tmp_path, MissionTopology.COORD, cell)
    door_reads = _counting(monkeypatch, read_surface, "resolve_status_read")
    stream_reads = _counting(monkeypatch, board_status_mod, "read_status_stream")

    board = decision_mapping._resolve_wp_board_action(mission_slug=slug, repo_root=repo)

    assert board.wp_id == "WP01"
    assert len(door_reads) == 1
    assert len(stream_reads) == 1


# ---------------------------------------------------------------------------
# Door errors at the two read sites
# ---------------------------------------------------------------------------


def test_board_names_an_unreadable_status_ref(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An unreadable ref is a named block, never a traceback (FR-002)."""
    from specify_cli.coordination.status_service import StatusSurfaceRefUnreadable

    def _unreadable(*args: Any, **kwargs: Any) -> Any:
        raise StatusSurfaceRefUnreadable(repo_root=tmp_path, ref="refs/heads/x", path="kitty-specs/m/status.events.jsonl", detail="bad object")

    monkeypatch.setattr(read_surface, "resolve_status_read", _unreadable)

    board = decision_mapping._resolve_wp_board_action(mission_slug="m", repo_root=tmp_path)

    assert board.action is None
    assert board.blocked_reason is not None
    assert board.blocked_reason.startswith("Status surface for mission 'm' is not readable: ")


def test_query_maps_a_mission_the_door_cannot_find(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from runtime.next.runtime_bridge_query import MissionNotFoundError, _query_read_board

    def _missing(*args: Any, **kwargs: Any) -> Any:
        raise FileNotFoundError("meta.json not found")

    monkeypatch.setattr(read_surface, "resolve_status_read", _missing)

    with pytest.raises(MissionNotFoundError):
        _query_read_board(tmp_path, "m")


def test_task_surface_error_needs_a_status_source(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="status_dir or board"):
        decision_mapping._wp_task_surface_error(tmp_path, None, "m")


def test_board_names_an_unavailable_worktree_registry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """WP04 review F2: the registry arm of the board's door read is a named block too."""
    from specify_cli.coordination.surface_resolver import WorktreeRegistryUnavailable

    def _unavailable(*args: Any, **kwargs: Any) -> Any:
        raise WorktreeRegistryUnavailable(repo_root=tmp_path, detail="injected worktree-list failure")

    monkeypatch.setattr(read_surface, "resolve_status_read", _unavailable)

    board = decision_mapping._resolve_wp_board_action(mission_slug="m", repo_root=tmp_path)

    assert board.action is None
    assert board.blocked_reason is not None
    assert board.blocked_reason.startswith("Status surface for mission 'm' is not readable: ")
    assert "injected worktree-list failure" in board.blocked_reason


@pytest.mark.parametrize(
    ("error", "code"),
    [("ref", "STATUS_SURFACE_REF_UNREADABLE"), ("registry", "WORKTREE_REGISTRY_UNAVAILABLE")],
)
def test_query_renders_an_unreadable_status_source_as_a_typed_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], error: str, code: str
) -> None:
    """WP04 review F1: an unreadable ref or worktree registry in query mode is a typed error.

    Before WP04 the query read an empty board here; after it, the door's error escaped
    ``next`` query mode as a traceback.
    """
    import json

    import typer

    from specify_cli.cli.commands import next_cmd
    from specify_cli.coordination.status_service import StatusSurfaceRefUnreadable
    from specify_cli.coordination.surface_resolver import WorktreeRegistryUnavailable

    repo, slug = _coord_cell_mission(tmp_path, MissionTopology.COORD, MATERIALIZED)

    def _unreadable(*args: Any, **kwargs: Any) -> Any:
        if error == "ref":
            raise StatusSurfaceRefUnreadable(repo_root=repo, ref="refs/heads/x", path="kitty-specs/m/status.events.jsonl", detail="bad object")
        raise WorktreeRegistryUnavailable(repo_root=repo, detail="injected worktree-list failure")

    monkeypatch.setattr(read_surface, "resolve_status_read", _unreadable)

    with pytest.raises(typer.Exit) as exited:
        next_cmd._run_query_mode("pedro", slug, repo, True, None, None)

    assert exited.value.exit_code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["error_code"] == code
