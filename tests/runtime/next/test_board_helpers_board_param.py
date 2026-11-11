"""The board and progress helpers read a ``BoardStatus`` passed as ``board=`` (#7310, WP03).

Same-fixture equivalence: every helper gives the same answer from
``board=board_status_from_dir(d)`` as from its Path form ``status_dir=d``. The Path forms keep
their own exception policy, pinned here for an absent and a corrupt log.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from tests.runtime.next._board_path import board_status_from_dir
from runtime.next.decision import _compute_wp_progress, _find_first_wp_by_lane
from runtime.next.discovery import preview_claimable_wp
from specify_cli.status import StoreError
from tests.runtime._next_mission_scaffold import scaffold_software_dev, seed_wp_lane

pytestmark = pytest.mark.fast

_SLUG = "071-board-helpers"
_EVENTS = "status.events.jsonl"

# One WP per lane the board can hold, plus WP09 (genesis: a task file with no lane event).
_SEEDED: dict[str, str] = {
    "WP01": "planned",
    "WP02": "claimed",
    "WP03": "in_progress",
    "WP04": "for_review",
    "WP05": "approved",
    "WP06": "done",
    "WP07": "canceled",
    "WP08": "blocked",
}
_GENESIS = "WP09"
_ALL_WPS = (*_SEEDED, _GENESIS, "WP10")
_LANE_QUERIES = ("planned", "claimed", "doing", "in_progress", "for_review", "approved", "done", "canceled", "blocked", "genesis")


def _write_task(tasks_dir: Path, wp_id: str, deps: tuple[str, ...] = ()) -> None:
    deps_yaml = "[" + ", ".join(deps) + "]"
    (tasks_dir / f"{wp_id}.md").write_text(
        f"---\nwork_package_id: {wp_id}\ndependencies: {deps_yaml}\ntitle: {wp_id}\n---\n## {wp_id}\n",
        encoding="utf-8",
    )


@pytest.fixture
def feature_dir(tmp_path: Path) -> Path:
    """A single_branch Mission: WPs in every lane, a genesis WP and a planned WP10."""
    repo = scaffold_software_dev(tmp_path / "repo", _SLUG)
    mission_dir = repo / "kitty-specs" / _SLUG
    tasks_dir = mission_dir / "tasks"
    tasks_dir.mkdir()
    # WP01 waits on WP03 (in_progress), so the claimable WP is WP10 (no dependencies).
    _write_task(tasks_dir, "WP01", ("WP03",))
    for wp_id in (*list(_SEEDED)[1:], _GENESIS):
        _write_task(tasks_dir, wp_id)
    _write_task(tasks_dir, "WP10", ("WP05", "WP06"))
    for wp_id, lane in _SEEDED.items():
        seed_wp_lane(mission_dir, _SLUG, wp_id, lane)
    seed_wp_lane(mission_dir, _SLUG, "WP10", "planned")
    return mission_dir


@pytest.fixture
def split_status_dir(feature_dir: Path, tmp_path: Path) -> Path:
    """The same log in a distinct status directory (the coord-husk shape of ``status_dir=``)."""
    status_dir = tmp_path / "coord" / _SLUG
    status_dir.mkdir(parents=True)
    shutil.copy2(feature_dir / _EVENTS, status_dir / _EVENTS)
    return status_dir


@pytest.fixture(params=["same", "split"])
def status_dir(request: pytest.FixtureRequest, feature_dir: Path) -> Path:
    """The status directory: the Mission dir itself, or a distinct copy of its log."""
    if request.param == "same":
        return feature_dir
    split: Path = request.getfixturevalue("split_status_dir")
    return split


def test_fixture_is_a_real_positive_control(feature_dir: Path) -> None:
    board = board_status_from_dir(feature_dir)

    assert {wp: str(lane) for wp, lane in board.lanes.items()} == {**_SEEDED, "WP10": "planned"}
    assert board.weighted_percentage is not None
    assert len(list((feature_dir / "tasks").glob("WP*.md"))) == len(_ALL_WPS)


def test_preview_claimable_wp_board_equals_path(feature_dir: Path, status_dir: Path) -> None:
    by_path = preview_claimable_wp(feature_dir, status_dir=status_dir)
    by_board = preview_claimable_wp(feature_dir, board=board_status_from_dir(status_dir))

    assert by_board == by_path
    assert by_board.wp_id == "WP10"


def test_preview_dependency_blocked_board_equals_path(feature_dir: Path) -> None:
    (feature_dir / "tasks" / "WP10.md").unlink()

    by_path = preview_claimable_wp(feature_dir, status_dir=feature_dir)
    by_board = preview_claimable_wp(feature_dir, board=board_status_from_dir(feature_dir))

    assert by_board == by_path
    assert by_board.selection_reason == "dependencies_not_satisfied"


def test_compute_wp_progress_board_equals_path(feature_dir: Path, status_dir: Path) -> None:
    by_path = _compute_wp_progress(feature_dir, status_dir=status_dir)
    by_board = _compute_wp_progress(feature_dir, board=board_status_from_dir(status_dir))

    assert by_path is not None
    assert by_board == by_path
    # Genesis WP09 is counted in total_wps but in no bucket.
    assert by_board is not None
    assert by_board["total_wps"] == len(_ALL_WPS)
    assert by_board["weighted_percentage"] == pytest.approx(by_path["weighted_percentage"], abs=0.05)


def test_board_weighted_progress_does_not_read_materialize_snapshot(feature_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    board = board_status_from_dir(feature_dir)

    def _forbidden(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("board= must not re-read the status log")

    monkeypatch.setattr("specify_cli.status.materialize_snapshot", _forbidden)
    monkeypatch.setattr("runtime.next.decision._get_wp_lanes", _forbidden)

    progress = _compute_wp_progress(feature_dir, board=board)

    assert progress is not None
    assert progress["weighted_percentage"] == board.weighted_percentage


def test_board_without_weighted_figure_omits_the_key(feature_dir: Path) -> None:
    from dataclasses import replace

    board = replace(board_status_from_dir(feature_dir), weighted_percentage=None)

    progress = _compute_wp_progress(feature_dir, board=board)

    assert progress is not None
    assert "weighted_percentage" not in progress


@pytest.mark.parametrize("lane", _LANE_QUERIES)
def test_find_first_wp_by_lane_board_equals_path(feature_dir: Path, status_dir: Path, lane: str) -> None:
    board = board_status_from_dir(status_dir)

    assert _find_first_wp_by_lane(feature_dir, lane, board=board) == _find_first_wp_by_lane(feature_dir, lane, status_dir=status_dir)


def test_absent_log_reads_the_same_both_ways(feature_dir: Path) -> None:
    (feature_dir / _EVENTS).unlink()
    board = board_status_from_dir(feature_dir)
    assert board.has_log is False

    assert preview_claimable_wp(feature_dir, board=board) == preview_claimable_wp(feature_dir, status_dir=feature_dir)
    assert _compute_wp_progress(feature_dir, board=board) == _compute_wp_progress(feature_dir, status_dir=feature_dir)
    for lane in _LANE_QUERIES:
        assert _find_first_wp_by_lane(feature_dir, lane, board=board) == _find_first_wp_by_lane(feature_dir, lane, status_dir=feature_dir)


def test_corrupt_status_log_keeps_the_path_forms_and_the_board_raises(feature_dir: Path, split_status_dir: Path) -> None:
    # Corrupt only the status directory, so the planning reads on feature_dir stay clean.
    with (split_status_dir / _EVENTS).open("a", encoding="utf-8") as handle:
        handle.write("{not json\n")

    # Pinned Path-form behaviour: discovery's lane read is best-effort (no states, so every
    # candidate reads as genesis); the progress helpers raise, as ``get_all_wp_lanes`` does.
    preview = preview_claimable_wp(feature_dir, status_dir=split_status_dir)
    assert preview.wp_id is None
    assert preview.selection_reason == "not_finalized"
    with pytest.raises(StoreError):
        _compute_wp_progress(feature_dir, status_dir=split_status_dir)
    with pytest.raises(StoreError):
        _find_first_wp_by_lane(feature_dir, "planned", status_dir=split_status_dir)

    with pytest.raises(StoreError):
        board_status_from_dir(split_status_dir)


def test_corrupt_mission_log_raises_from_the_planning_read(feature_dir: Path) -> None:
    """Pinned: with one directory, the dependency-graph planning read raises before any lane read."""
    with (feature_dir / _EVENTS).open("a", encoding="utf-8") as handle:
        handle.write("{not json\n")

    with pytest.raises(StoreError):
        preview_claimable_wp(feature_dir, status_dir=feature_dir)


def test_no_tasks_dir_is_none_both_ways(feature_dir: Path) -> None:
    board = board_status_from_dir(feature_dir)
    shutil.rmtree(feature_dir / "tasks")

    assert _compute_wp_progress(feature_dir, board=board) is None
    assert _find_first_wp_by_lane(feature_dir, "planned", board=board) is None
    assert preview_claimable_wp(feature_dir, board=board).selection_reason == "no_tasks_dir"
