"""Unit tests for the pure helpers extracted from ``scan_recovery_state``.

Mission ``coord-read-residuals-…-01KW2M8V`` WP03 / T018: the C901-complex
``scan_recovery_state`` was decomposed into deterministic helpers (dropping its
``# noqa: C901``). These tests exercise each extracted branch directly with
stable inputs/outputs — no filesystem or git — so the decomposition is covered
at the unit level (Sonar new-branch coverage; tactic
``test-scaffolding-as-design-smell``).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.lanes.recovery import (
    RecoveryState,
    _append_merged_and_deleted,
    _append_ready_to_start,
    _collect_done_wp_ids,
    _compute_ready_to_start,
    _compute_recovery_action,
    _enumerate_expected_wp_ids,
)
from specify_cli.status import Lane

# Pure, deterministic helper tests (no filesystem/git) — same profile as the
# sibling lane unit tests (e.g. ``test_resolve_lanes_dir.py``). The ``fast``
# marker registers the file with the CI lanes gate
# (``tests/specify_cli/lanes/ -m "fast and not windows_ci"`` in ci-quality.yml),
# so it is selected by a gate rather than orphaned (test_gate_coverage) and
# satisfies the module-level pytestmark convention (test_pytest_marker_convention).
pytestmark = [pytest.mark.fast]


# ---------------------------------------------------------------------------
# _compute_recovery_action — the decision table
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("worktree", "context", "commits", "status_lane", "expected"),
    [
        # No worktree → recreate the worktree regardless of context/commits.
        (False, False, False, "claimed", "recreate_worktree"),
        (False, True, True, "claimed", "recreate_worktree"),
        # Worktree present but context gone → recreate the context.
        (True, False, False, "claimed", "recreate_context"),
        # Everything present, commits ahead, and the lane can still advance →
        # emit the missing transitions.
        (True, True, True, "claimed", "emit_transitions"),
        # Everything present but no commits → nothing to do.
        (True, True, False, "claimed", "no_action"),
        # Commits ahead but the lane is terminal (no recovery transitions) →
        # nothing to do (the transitions list is empty).
        (True, True, True, Lane.DONE.value, "no_action"),
    ],
)
def test_compute_recovery_action(
    worktree: bool, context: bool, commits: bool, status_lane: str, expected: str,
) -> None:
    assert (
        _compute_recovery_action(
            worktree_exists=worktree,
            context_exists=context,
            has_commits=commits,
            status_lane=status_lane,
        )
        == expected
    )


# ---------------------------------------------------------------------------
# _enumerate_expected_wp_ids — tasks/ ∪ lanes.json (PRIMARY)
# ---------------------------------------------------------------------------


def _write_wp(tasks_dir: Path, wp_id: str) -> None:
    tasks_dir.mkdir(parents=True, exist_ok=True)
    (tasks_dir / f"{wp_id}.md").write_text(
        f"---\nwork_package_id: {wp_id}\ntitle: {wp_id}\n---\n# {wp_id}\n",
        encoding="utf-8",
    )


def test_enumerate_expected_wp_ids_empty_when_no_tasks(tmp_path: Path) -> None:
    """No tasks/ dir and no lanes.json → empty (the husk shape)."""
    assert _enumerate_expected_wp_ids(tmp_path) == []


def test_enumerate_expected_wp_ids_reads_tasks_dir(tmp_path: Path) -> None:
    _write_wp(tmp_path / "tasks", "WP01")
    _write_wp(tmp_path / "tasks", "WP02")
    assert _enumerate_expected_wp_ids(tmp_path) == ["WP01", "WP02"]


def test_enumerate_expected_wp_ids_unions_lanes_json(tmp_path: Path) -> None:
    """lanes.json WP ids not already in tasks/ are appended (no duplicates)."""
    _write_wp(tmp_path / "tasks", "WP01")
    (tmp_path / "lanes.json").write_text(
        '{"version":1,"mission_slug":"s","mission_id":"01KW2E7AFC0000000000000001",'
        '"mission_branch":"kitty/mission-s","target_branch":"main",'
        '"lanes":[{"lane_id":"lane-a","wp_ids":["WP01","WP03"],"write_scope":[],'
        '"predicted_surfaces":[],"depends_on_lanes":[],"parallel_group":0}],'
        '"computed_at":"2026-06-26T00:00:00+00:00","computed_from":"t",'
        '"planning_artifact_wps":[]}',
        encoding="utf-8",
    )
    result = _enumerate_expected_wp_ids(tmp_path)
    assert result == ["WP01", "WP03"]  # WP01 not duplicated; WP03 appended


# ---------------------------------------------------------------------------
# _collect_done_wp_ids
# ---------------------------------------------------------------------------


def _state(wp_id: str, *, status_lane: str = "planned", note: str = "") -> RecoveryState:
    return RecoveryState(
        wp_id=wp_id,
        lane_id="lane-a",
        branch_name="",
        branch_exists=False,
        worktree_exists=False,
        context_exists=False,
        status_lane=status_lane,
        has_commits=False,
        recovery_action="no_action",
        resolution_note=note,
    )


def test_collect_done_wp_ids_from_states_and_events() -> None:
    states = [
        _state("WP01", status_lane=Lane.DONE.value),
        _state("WP02", note="merged_and_deleted"),
        _state("WP03", status_lane="claimed"),
    ]
    all_wp_lanes = {"WP04": Lane.DONE.value, "WP03": "claimed"}
    assert _collect_done_wp_ids(states, all_wp_lanes) == {"WP01", "WP02", "WP04"}


# ---------------------------------------------------------------------------
# _append_merged_and_deleted
# ---------------------------------------------------------------------------


def test_append_merged_and_deleted_adds_branchless_done_wp() -> None:
    states: list[RecoveryState] = []
    _append_merged_and_deleted(
        states,
        all_task_wp_ids=["WP01", "WP02"],
        represented_wps={"WP02"},  # WP02 already has a live branch → skipped
        all_wp_lanes={"WP01": Lane.DONE.value, "WP02": Lane.DONE.value},
    )
    assert len(states) == 1
    assert states[0].wp_id == "WP01"
    assert states[0].resolution_note == "merged_and_deleted"


def test_append_merged_and_deleted_skips_non_done() -> None:
    states: list[RecoveryState] = []
    _append_merged_and_deleted(
        states,
        all_task_wp_ids=["WP01"],
        represented_wps=set(),
        all_wp_lanes={"WP01": "claimed"},
    )
    assert states == []


# ---------------------------------------------------------------------------
# _compute_ready_to_start
# ---------------------------------------------------------------------------


def test_compute_ready_to_start_empty_without_done_wps(tmp_path: Path) -> None:
    """No done WPs → not a post-merge context → empty (no tasks/ read attempted)."""
    assert (
        _compute_ready_to_start(
            tmp_path,
            all_task_wp_ids=["WP02"],
            done_wp_ids=set(),
            represented_wps=set(),
            recovery_states=[],
        )
        == []
    )


def test_compute_ready_to_start_unblocks_when_deps_done(tmp_path: Path) -> None:
    """WP02 depends on WP01; WP01 is done → WP02 is ready to start."""
    tasks_dir = tmp_path / "tasks"
    tasks_dir.mkdir()
    (tasks_dir / "WP02.md").write_text(
        '---\nwork_package_id: WP02\ntitle: WP02\ndependencies:\n  - "WP01"\n---\n',
        encoding="utf-8",
    )
    ready = _compute_ready_to_start(
        tmp_path,
        all_task_wp_ids=["WP01", "WP02"],
        done_wp_ids={"WP01"},
        represented_wps=set(),
        recovery_states=[],
    )
    assert ready == ["WP02"]


def test_compute_ready_to_start_globs_tasks_once_for_n_wps(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """#4523: the dependency read must not re-glob ``tasks/`` per WP.

    Pre-fix, ``_read_wp_dependencies`` globbed ``tasks/WP*.md`` once per
    candidate WP (N directory scans for N not-done WPs). The map is built
    once and consulted per WP.
    """
    from collections.abc import Iterator

    tasks_dir = tmp_path / "tasks"
    tasks_dir.mkdir()
    for wp_id in ("WP01", "WP02", "WP03"):
        (tasks_dir / f"{wp_id}.md").write_text(
            f'---\nwork_package_id: {wp_id}\ntitle: {wp_id}\ndependencies:\n  - "WP01"\n---\n',
            encoding="utf-8",
        )

    glob_calls: list[str] = []
    real_glob = Path.glob

    def _counting_glob(self: Path, pattern: str) -> Iterator[Path]:
        glob_calls.append(pattern)
        return real_glob(self, pattern)

    monkeypatch.setattr(Path, "glob", _counting_glob)

    ready = _compute_ready_to_start(
        tmp_path,
        all_task_wp_ids=["WP01", "WP02", "WP03"],
        done_wp_ids={"WP01"},
        represented_wps=set(),
        recovery_states=[],
    )

    assert ready == ["WP02", "WP03"]
    assert glob_calls.count("WP*.md") == 1, (
        f"tasks/WP*.md must be globbed exactly once for the whole scan, got {len(glob_calls)}: {glob_calls}"
    )


# ---------------------------------------------------------------------------
# _append_ready_to_start
# ---------------------------------------------------------------------------


def test_append_ready_to_start_adds_synthetic_state() -> None:
    states: list[RecoveryState] = []
    _append_ready_to_start(
        states, ready_to_start=["WP02"], all_wp_lanes={"WP02": "planned"},
    )
    assert len(states) == 1
    assert states[0].wp_id == "WP02"
    assert states[0].resolution_note == "ready_to_start_from_target"


def test_append_ready_to_start_dedupes_existing() -> None:
    existing = _state("WP02", note="ready_to_start_from_target")
    states = [existing]
    _append_ready_to_start(
        states, ready_to_start=["WP02"], all_wp_lanes={},
    )
    assert len(states) == 1  # no duplicate appended


# ---------------------------------------------------------------------------
# #7310: the STATUS leg reads through the one status read door; no Mission -> no status
# ---------------------------------------------------------------------------


def test_status_surface_is_none_for_a_mission_that_does_not_exist(tmp_path: Path) -> None:
    from specify_cli.lanes.recovery import _resolve_recovery_status_surface

    (tmp_path / "kitty-specs").mkdir()
    assert _resolve_recovery_status_surface(tmp_path, "no-such-mission") is None


def test_lane_helpers_read_no_status_without_a_surface() -> None:
    from specify_cli.lanes.recovery import _get_all_wp_lanes_from_events, _get_wp_lane_from_events

    assert _get_wp_lane_from_events(None, "WP01") == Lane.PLANNED.value
    assert _get_all_wp_lanes_from_events(None) == {}


def test_lane_helpers_propagate_a_door_refusal_but_tolerate_a_corrupt_log(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An unreadable ref stays loud (never PLANNED / {}); a corrupt log line still degrades."""
    from specify_cli.coordination.status_service import StatusSurfaceRefUnreadable
    from specify_cli.lanes.recovery import _get_all_wp_lanes_from_events, _get_wp_lane_from_events
    from specify_cli.status import StatusReadSurface, StoreError
    import specify_cli.status as status_pkg

    surface = StatusReadSurface.__new__(StatusReadSurface)  # the helpers only hand it to the reader

    def refuse(_surface: object) -> list[object]:
        raise StatusSurfaceRefUnreadable(repo_root=tmp_path, ref="refs/heads/x", path="p", detail="bad object")

    monkeypatch.setattr(status_pkg, "read_status_events", refuse)
    with pytest.raises(StatusSurfaceRefUnreadable):
        _get_wp_lane_from_events(surface, "WP01")
    with pytest.raises(StatusSurfaceRefUnreadable):
        _get_all_wp_lanes_from_events(surface)

    def corrupt(_surface: object) -> list[object]:
        raise StoreError("corrupt line")

    monkeypatch.setattr(status_pkg, "read_status_events", corrupt)
    assert _get_wp_lane_from_events(surface, "WP01") == Lane.PLANNED.value
    assert _get_all_wp_lanes_from_events(surface) == {}
