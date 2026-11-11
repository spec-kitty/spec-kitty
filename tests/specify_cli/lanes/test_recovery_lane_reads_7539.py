"""The recovery scan reads the status log once per scan (#7539 item 2, pre-PR squad row 9).

``scan_recovery_state`` looks each live lane's work packages up in the status event log. The
outcomes pinned here (#7310, ``968fdc8e``): a WP's recorded lane, ``planned`` for a WP the log
does not hold or holds with an unknown lane, ``planned`` for every WP when the log has a corrupt
line, a door refusal (an unreadable ref) propagating, and ``planned`` without a status surface.
The scan's git and filesystem probes are stubbed; the status reader is spied on the
``specify_cli.status`` package attribute, which the helpers import at call time.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import specify_cli.lanes.recovery as recovery
import specify_cli.status as status_pkg
from specify_cli.coordination.status_service import StatusSurfaceRefUnreadable
from specify_cli.status import StatusReadSurface, StoreError

pytestmark = pytest.mark.fast

SLUG = "recovery-reads-7539"
_LANE_WPS = {"lane-a": ["WP01", "WP02"], "lane-b": ["WP03", "WP04"]}
_RECORDED = {"WP01": {"lane": "in_progress"}, "WP02": {"lane": "for_review"}, "WP03": {"lane": "bogus"}}
_EXPECTED_LANES = {"WP01": "in_progress", "WP02": "for_review", "WP03": "planned", "WP04": "planned"}

#: Status log reads per scan, for ``consult_status_events`` True and False: one reduction per scan.
_READS = {True: 1, False: 1}


def _surface() -> StatusReadSurface:
    return StatusReadSurface.__new__(StatusReadSurface)  # the scan only hands it to the reader


def _stub_scan(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, surface: StatusReadSurface | None) -> None:
    primary_dir = tmp_path / "primary"
    primary_dir.mkdir()
    seam = SimpleNamespace(read_dir=lambda _kind: primary_dir)
    monkeypatch.setattr(recovery, "placement_seam", lambda _root, _slug: seam)
    monkeypatch.setattr(recovery, "_resolve_recovery_status_surface", lambda _root, _slug: surface)
    branches = [f"kitty/mission-{SLUG}-{lane}" for lane in _LANE_WPS]
    monkeypatch.setattr(recovery, "_list_mission_branches", lambda _root, _slug: branches)
    monkeypatch.setattr(recovery, "_resolve_mission_branch", lambda _dir, _slug: f"kitty/mission-{SLUG}")
    monkeypatch.setattr(recovery, "_collect_contexts_by_lane", lambda _root, _slug: {})
    monkeypatch.setattr(recovery, "_worktree_exists_for_branch", lambda _root, _branch: None)
    monkeypatch.setattr(recovery, "predict_lane_worktree", lambda _root, _slug, lane: (tmp_path / "absent" / lane, ""))
    monkeypatch.setattr(recovery, "_branch_has_commits_beyond", lambda _root, _branch, _base: True)
    monkeypatch.setattr(recovery, "_find_wp_ids_for_lane", lambda _dir, lane: list(_LANE_WPS[lane]))


def _counting_reader(monkeypatch: pytest.MonkeyPatch, outcome: Any) -> list[object]:
    reads: list[object] = []

    def _read(surface: object) -> list[object]:
        reads.append(surface)
        if isinstance(outcome, Exception):
            raise outcome
        return ["event"]

    monkeypatch.setattr(status_pkg, "read_status_events", _read)
    monkeypatch.setattr(status_pkg, "reduce", lambda _events: SimpleNamespace(work_packages=_RECORDED))
    return reads


def _lanes(states: list[recovery.RecoveryState]) -> dict[str, str]:
    return {state.wp_id: state.status_lane for state in states if state.branch_exists}


@pytest.mark.parametrize("consult", [True, False])
def test_scan_reports_each_wps_recorded_lane(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, consult: bool) -> None:
    _stub_scan(monkeypatch, tmp_path, _surface())
    reads = _counting_reader(monkeypatch, None)

    states = recovery.scan_recovery_state(tmp_path, SLUG, consult_status_events=consult)

    assert _lanes(states) == _EXPECTED_LANES
    assert len(reads) == _READS[consult]


@pytest.mark.parametrize("consult", [True, False])
def test_a_corrupt_log_degrades_every_wp_to_planned(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, consult: bool) -> None:
    _stub_scan(monkeypatch, tmp_path, _surface())
    _counting_reader(monkeypatch, StoreError("corrupt line"))

    states = recovery.scan_recovery_state(tmp_path, SLUG, consult_status_events=consult)

    assert _lanes(states) == dict.fromkeys(_EXPECTED_LANES, "planned")


@pytest.mark.parametrize("consult", [True, False])
def test_a_door_refusal_propagates(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, consult: bool) -> None:
    _stub_scan(monkeypatch, tmp_path, _surface())
    _counting_reader(monkeypatch, StatusSurfaceRefUnreadable(repo_root=tmp_path, ref="refs/heads/x", path="p", detail="bad object"))

    with pytest.raises(StatusSurfaceRefUnreadable):
        recovery.scan_recovery_state(tmp_path, SLUG, consult_status_events=consult)


@pytest.mark.parametrize("consult", [True, False])
def test_no_surface_reads_nothing_and_reports_planned(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, consult: bool) -> None:
    _stub_scan(monkeypatch, tmp_path, None)
    reads = _counting_reader(monkeypatch, None)

    states = recovery.scan_recovery_state(tmp_path, SLUG, consult_status_events=consult)

    assert _lanes(states) == dict.fromkeys(_EXPECTED_LANES, "planned")
    assert reads == []
