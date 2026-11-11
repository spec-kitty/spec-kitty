"""#7310 (Mission ``runtime-status-read-door-01M73HHB``, WP01): the board status value.

:mod:`runtime.next.board_status` reduces one status read door surface once into an immutable
:class:`~runtime.next.board_status.BoardStatus`. These tests pin it to today's Path-typed readers:

* parity (NFR-001): for every ``kitty-specs/*/status.events.jsonl`` in this repository, the
  board's lanes equal ``get_all_wp_lanes`` and its weighted progress equals the rounded
  ``compute_weighted_progress(materialize_snapshot(...))``; a log that raises in one raises in
  the other;
* edges: no log, empty log, corrupt line, genesis WP, a ref-sourced surface (coordination log
  committed on the branch, empty coordination worktree);
* one read (NFR-002): one ``read_status_stream`` call per build.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from mission_runtime import MissionTopology
from runtime.next import board_status as board_status_module
from runtime.next.board_status import BoardStatus, board_status_from_dir, board_status_from_surface
from specify_cli.status import (
    Lane,
    StatusReadSource,
    StatusReadSurface,
    StoreError,
    compute_weighted_progress,
    get_all_wp_lanes,
    materialize_snapshot,
    read_status_stream,
    resolve_status_read,
)

pytestmark = [pytest.mark.unit]

_REPO_ROOT = Path(__file__).resolve().parents[3]
_EVENTS = "status.events.jsonl"
_REPO_LOG_DIRS = sorted(log.parent for log in (_REPO_ROOT / "kitty-specs").glob(f"*/{_EVENTS}"))
_FIXED_AT = "2026-11-11T05:00:00+00:00"


def _event(wp_id: str, from_lane: str, to_lane: str, n: int) -> dict[str, Any]:
    return {
        "actor": "tester",
        "at": _FIXED_AT,
        "event_id": f"01KBOARDSTATUS{n:012d}",
        "evidence": None,
        "execution_mode": "worktree",
        "feature_slug": "board-status-fixture",
        "force": False,
        "from_lane": from_lane,
        "reason": None,
        "review_ref": None,
        "to_lane": to_lane,
        "wp_id": wp_id,
    }


def _write_log(mission_dir: Path, events: list[dict[str, Any]]) -> Path:
    mission_dir.mkdir(parents=True, exist_ok=True)
    log = mission_dir / _EVENTS
    log.write_text("".join(json.dumps(event, sort_keys=True) + "\n" for event in events), encoding="utf-8")
    return mission_dir


def _outcome(read: Callable[[], Any]) -> tuple[str, Any]:
    """``("ok", value)`` or ``("raises", exception type)`` -- both readers handled alike."""
    try:
        return "ok", read()
    except Exception as exc:  # noqa: BLE001 -- the parity is "raises in both", whatever the type
        return "raises", type(exc)


def _today_lanes(mission_dir: Path) -> dict[str, Lane]:
    return dict(get_all_wp_lanes(mission_dir))


def _today_weighted(mission_dir: Path) -> float:
    return round(float(compute_weighted_progress(materialize_snapshot(mission_dir)).percentage), 1)


# ---------------------------------------------------------------------------
# Parity over every real status log (NFR-001)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("mission_dir", _REPO_LOG_DIRS, ids=lambda d: d.name)
def test_board_matches_todays_readers_on_every_repo_log(mission_dir: Path) -> None:
    board = _outcome(lambda: board_status_from_dir(mission_dir))
    lanes = _outcome(lambda: _today_lanes(mission_dir))
    weighted = _outcome(lambda: _today_weighted(mission_dir))

    if board[0] == "raises":
        # A log the board cannot read must raise on today's lane path too (C-003: callers keep
        # their current raise); the weighted figure only ever degraded.
        assert lanes[0] == "raises", f"{mission_dir}: board raised {board[1]} but get_all_wp_lanes did not"
        return
    value: BoardStatus = board[1]
    assert lanes == ("ok", dict(value.lanes)), f"lane parity gap in {mission_dir}"
    expected_weighted = weighted[1] if weighted[0] == "ok" else None
    assert value.weighted_percentage == expected_weighted, f"weighted parity gap in {mission_dir}"
    assert value.has_log is True
    assert value.source == "path"


def test_parity_sees_the_real_logs() -> None:
    """Non-vacuity: the parity test iterates the repository's own logs, not a fixture subset."""
    if not _REPO_LOG_DIRS:
        pytest.skip("no kitty-specs/*/status.events.jsonl in this checkout (sparse checkout?)")
    assert len(_REPO_LOG_DIRS) >= 100


# ---------------------------------------------------------------------------
# Edges
# ---------------------------------------------------------------------------


def test_no_log(tmp_path: Path) -> None:
    mission_dir = tmp_path / "kitty-specs" / "no-log"
    mission_dir.mkdir(parents=True)

    board = board_status_from_dir(mission_dir)

    assert board.has_log is False
    assert dict(board.lanes) == {}
    assert dict(board.wp_states) == {}
    assert board.weighted_percentage == _today_weighted(mission_dir)


def test_empty_log(tmp_path: Path) -> None:
    mission_dir = _write_log(tmp_path / "kitty-specs" / "empty-log", [])

    board = board_status_from_dir(mission_dir)

    assert board.has_log is True
    assert dict(board.lanes) == {}
    assert board.weighted_percentage == _today_weighted(mission_dir)


def test_corrupt_line_raises_like_get_all_wp_lanes(tmp_path: Path) -> None:
    mission_dir = _write_log(tmp_path / "kitty-specs" / "corrupt", [_event("WP01", "planned", "claimed", 1)])
    with (mission_dir / _EVENTS).open("a", encoding="utf-8") as handle:
        handle.write("{not json\n")

    with pytest.raises(StoreError):
        get_all_wp_lanes(mission_dir)
    with pytest.raises(StoreError):
        board_status_from_dir(mission_dir)


def test_lanes_and_states_from_a_written_log(tmp_path: Path) -> None:
    mission_dir = _write_log(
        tmp_path / "kitty-specs" / "two-wps",
        [
            _event("WP01", "planned", "claimed", 1),
            _event("WP01", "claimed", "in_progress", 2),
            _event("WP02", "planned", "planned", 3),
        ],
    )

    board = board_status_from_dir(mission_dir)

    assert dict(board.lanes) == {"WP01": Lane.IN_PROGRESS, "WP02": Lane.PLANNED}
    assert board.wp_states["WP01"]["lane"] == "in_progress"
    assert board.lanes == _today_lanes(mission_dir)
    assert board.weighted_percentage == _today_weighted(mission_dir)


def test_genesis_wp_is_kept_as_genesis() -> None:
    """A reduced state with no lane is kept (as GENESIS) so callers can skip unseeded WPs."""
    states = board_status_module._lanes_from_states({"WP01": {"wp_id": "WP01"}, "WP02": {"lane": "planned"}})

    assert dict(states) == {"WP01": Lane.GENESIS, "WP02": Lane.PLANNED}


def test_value_is_read_only(tmp_path: Path) -> None:
    mission_dir = _write_log(tmp_path / "kitty-specs" / "frozen", [_event("WP01", "planned", "claimed", 1)])
    board = board_status_from_dir(mission_dir)

    with pytest.raises(TypeError):
        board.lanes["WP09"] = Lane.DONE  # type: ignore[index]  # proving the mapping is read-only
    with pytest.raises(TypeError):
        board.wp_states["WP01"]["lane"] = "done"  # type: ignore[index]  # proving the state is read-only
    with pytest.raises(AttributeError):
        board.has_log = False  # type: ignore[misc]  # proving the dataclass is frozen


def test_path_surface_builds_the_same_value_as_the_adapter(tmp_path: Path) -> None:
    mission_dir = _write_log(tmp_path / "kitty-specs" / "path-surface", [_event("WP01", "planned", "claimed", 1)])
    surface = StatusReadSurface(
        topology=MissionTopology.SINGLE_BRANCH,
        source=StatusReadSource.WRITE_CHECKOUT,
        mission_dir_name=mission_dir.name,
        path=mission_dir,
        repo_root=tmp_path,
        ref=None,
    )

    from_surface = board_status_from_surface(surface)
    from_dir = board_status_from_dir(mission_dir)

    assert from_surface.source == "write_checkout"
    assert (from_surface.lanes, from_surface.wp_states, from_surface.has_log, from_surface.weighted_percentage) == (
        from_dir.lanes,
        from_dir.wp_states,
        from_dir.has_log,
        from_dir.weighted_percentage,
    )


def test_weighted_failure_degrades_to_none(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    mission_dir = _write_log(tmp_path / "kitty-specs" / "weighted-fails", [_event("WP01", "planned", "claimed", 1)])

    def _boom(*_args: object, **_kwargs: object) -> None:
        raise ValueError("no weights")

    monkeypatch.setattr(board_status_module, "compute_weighted_progress", _boom)
    with caplog.at_level("WARNING", logger=board_status_module.__name__):
        board = board_status_from_dir(mission_dir)

    assert board.weighted_percentage is None
    assert dict(board.lanes) == {"WP01": Lane.CLAIMED}
    assert "weighted progress unavailable" in caplog.text


def test_one_read_per_build(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mission_dir = _write_log(tmp_path / "kitty-specs" / "one-read", [_event("WP01", "planned", "claimed", 1)])
    surface = StatusReadSurface(
        topology=MissionTopology.SINGLE_BRANCH,
        source=StatusReadSource.WRITE_CHECKOUT,
        mission_dir_name=mission_dir.name,
        path=mission_dir,
        repo_root=tmp_path,
        ref=None,
    )
    calls: list[StatusReadSurface] = []
    real = read_status_stream

    def _counting(arg: StatusReadSurface) -> Any:
        calls.append(arg)
        return real(arg)

    monkeypatch.setattr(board_status_module, "read_status_stream", _counting)

    board_status_from_surface(surface)
    assert len(calls) == 1
    board_status_from_surface(surface)
    assert len(calls) == 2


# ---------------------------------------------------------------------------
# Ref-sourced surface: log committed on the coordination branch, empty worktree
# ---------------------------------------------------------------------------


def _git(*args: str, cwd: Path) -> None:
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True)


@pytest.mark.git_repo
def test_ref_surface_reads_the_committed_coordination_log(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from tests.runtime._next_mission_scaffold import scaffold_coord_software_dev

    repo = tmp_path / "repo"
    repo.mkdir()
    feature_dir, coord_mission_dir = scaffold_coord_software_dev(
        repo,
        "board-status-ref",
        MissionTopology.COORD,
        wps={"WP01": "planned", "WP02": "for_review"},
    )
    coord_root = coord_mission_dir.parent.parent
    _git("add", "-A", cwd=coord_root)
    _git("commit", "-m", "seed coordination log", cwd=coord_root)
    shutil.rmtree(coord_mission_dir)  # the EMPTY coordination worktree cell

    surface = resolve_status_read(repo, feature_dir.name)
    assert surface.source is StatusReadSource.COORD_BRANCH_REF

    reads: list[StatusReadSurface] = []
    real = read_status_stream

    def _counting(arg: StatusReadSurface) -> Any:
        reads.append(arg)
        return real(arg)

    monkeypatch.setattr(board_status_module, "read_status_stream", _counting)
    board = board_status_from_surface(surface)

    assert len(reads) == 1
    assert board.source == "coord_branch_ref"
    assert board.has_log is True
    assert board.lanes["WP01"] is Lane.PLANNED
    assert board.lanes["WP02"] is Lane.FOR_REVIEW
    assert board.weighted_percentage == 30.0
