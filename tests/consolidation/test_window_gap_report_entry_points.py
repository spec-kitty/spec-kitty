"""The window gap report on every consolidate surface (Mission consolidation-window-provenance-01M6Y84D, WP20).

FR-010, FR-011, SC-002, US3 (1, 3, 4), NFR-010. A work package whose window was not recorded is
judged by its approval-stamp bound (WP19); these tests pin that the operator SEES it: the fresh run,
the ``--resume`` and the ``--dry-run`` forecast print one ``Window gaps`` block, and
``--dry-run --json`` carries ``window_gaps``. Every run goes through the real CLI in process, on a
repository whose status events were written by the real status pipeline (the window axis is set
afterwards by ``set_window_state``). Fixture work never asserts: :func:`require` raises, so a broken
fixture ERRORS instead of reading as a verdict.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest

from specify_cli.lanes.persistence import read_lanes_json
from tests.consolidation import characterization_support as cs
from tests.consolidation.resume_frozen_anchors_support import fixture_phase, require
from tests.terminus.rollback_harness import ref_shas

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

HEADING = "Window gaps (judged by the approval-stamp bound)"
MOVED = "LANE_MOVED_AFTER_APPROVAL"
FORECAST_REFUSED = "CLAIM_REFUSED_FORECAST"
LANE = "lane-a"

_TEMPLATES: dict[str, Callable[[Path], cs.ShapeMission]] = {
    "plain": lambda d: cs.build_two_wp_lane(d, mid8="01M6YBA0"),
    "stray": lambda d: cs.build_two_wp_lane(d, mid8="01M6YBA1", stray_between=True),
    "single_branch": lambda d: cs.build_shape(d, "single_branch"),
}


class _Templates:
    """Each template is built once per module, on first use, and copied for every test (the original is never run)."""

    def __init__(self, root: Path) -> None:
        self._root = root
        self._built: dict[str, cs.ShapeMission] = {}

    def copy(self, name: str, dest: Path) -> cs.ShapeMission:
        if name not in self._built:
            with fixture_phase():
                self._built[name] = _TEMPLATES[name](self._root / name)
        return cs.copy_mission(self._built[name], dest / name)


@pytest.fixture(scope="module")
def templates(tmp_path_factory: pytest.TempPathFactory) -> Iterator[_Templates]:
    yield _Templates(tmp_path_factory.mktemp("gap-report-templates"))


# --------------------------------------------------------------------------- helpers


def _set_windows(mission: cs.ShapeMission, **states: str) -> None:
    with fixture_phase():
        for wp_id, state in states.items():
            cs.set_window_state(mission, wp_id, state)


def _fresh(mission: cs.ShapeMission) -> cs.CellResult:
    return cs.run_in_process(mission, cs.consolidate_args(mission, "fresh"))


def _payload(result: cs.CellResult) -> dict[str, Any]:
    start, end = result.output.find("{"), result.output.rfind("}")
    require(start >= 0 and end > start, f"the forecast printed no JSON payload:\n{result.output}")
    payload: dict[str, Any] = json.loads(result.output[start : end + 1])
    return payload


def _forecast_json(mission: cs.ShapeMission) -> tuple[cs.CellResult, dict[str, Any]]:
    result = cs.run_in_process(mission, cs.consolidate_args(mission, "forecast"))
    return result, _payload(result)


def _line(wp_id: str, lane_id: str, reason: str) -> str:
    return f"  - {wp_id} ({lane_id}): {reason}"


def _not_recorded(wp_id: str, lane_id: str = LANE) -> dict[str, str]:
    return {"wp_id": wp_id, "lane_id": lane_id, "reason": "not recorded"}


def _assert_block(output: str, *lines: str) -> None:
    assert HEADING in output, f"the gap report heading is missing:\n{output}"
    heading_at = output.index(HEADING)
    for line in lines:
        assert line in output, f"the gap report must list {line!r}:\n{output}"
        assert output.index(line) > heading_at, f"{line!r} must follow the heading:\n{output}"


def _assert_passes(result: cs.CellResult) -> None:
    assert result.exception is None, result.output
    assert result.exit_code == 0, result.output


# --------------------------------------------------------------------------- the fresh run


def test_fresh_run_prints_gap_report_for_all_gap_lane(templates: _Templates, tmp_path: Path) -> None:
    """US3-1: every work package's window is ``not_recorded``; the run passes and lists both."""
    mission = templates.copy("plain", tmp_path)
    _set_windows(mission, WP01="not_recorded", WP02="not_recorded")

    result = _fresh(mission)

    _assert_passes(result)
    _assert_block(result.output, _line("WP01", LANE, "not recorded"), _line("WP02", LANE, "not recorded"))


def test_fresh_run_without_gaps_prints_no_block(templates: _Templates, tmp_path: Path) -> None:
    mission = templates.copy("plain", tmp_path)
    _set_windows(mission, WP01="recorded", WP02="recorded")

    result = _fresh(mission)

    _assert_passes(result)
    assert HEADING not in result.output, result.output


def test_fresh_run_refusal_prints_gap_report_first(templates: _Templates, tmp_path: Path) -> None:
    """The operator sees which work packages got the weaker check even when the run refuses."""
    mission = templates.copy("stray", tmp_path)
    _set_windows(mission, WP01="not_recorded", WP02="recorded")
    before = ref_shas(mission.coord_mission())

    result = _fresh(mission)

    assert result.exit_code == 1, result.output
    wp01 = _line("WP01", LANE, "not recorded")
    _assert_block(result.output, wp01)
    assert _line("WP02", LANE, "not recorded") not in result.output, result.output
    assert MOVED in result.output, result.output
    assert result.output.index(wp01) < result.output.index(MOVED), f"the gap report must precede the refusal:\n{result.output}"
    assert ref_shas(mission.coord_mission()) == before


# --------------------------------------------------------------------------- the resume


def test_resume_prints_gap_report_and_keeps_the_verdict(templates: _Templates, tmp_path: Path) -> None:
    """US3-3, NFR-010: an all-gap Mission (the pre-upgrade shape) resumed after a SIGKILL after the claim."""
    mission = templates.copy("plain", tmp_path / "resumed")
    _set_windows(mission, WP01="not_recorded", WP02="not_recorded")
    twin = cs.copy_mission(mission, tmp_path / "twin")
    fresh = _fresh(twin)

    record = cs.interrupt_after_claim(mission)
    require(bool(record.get("pre_interrupt_lane_tips")), f"the record holds no pre_interrupt_lane_tips: {sorted(record)}")
    resumed = cs.run_in_process(mission, cs.consolidate_args(mission, "resume"))

    assert resumed.exception is None, resumed.output
    assert resumed.exit_code == fresh.exit_code, f"fresh:\n{fresh.output}\nresume:\n{resumed.output}"
    _assert_block(resumed.output, _line("WP01", LANE, "not recorded"), _line("WP02", LANE, "not recorded"))


# --------------------------------------------------------------------------- the forecast


def test_dry_run_json_carries_window_gaps(templates: _Templates, tmp_path: Path) -> None:
    """FR-010: the payload names every gap, in ``(lane_id, wp_id)`` order, with no absent cause or detail."""
    mission = templates.copy("plain", tmp_path)
    _set_windows(mission, WP01="not_recorded", WP02="not_recorded")

    result, payload = _forecast_json(mission)

    assert result.exit_code == 0, result.output
    assert payload["window_gaps"] == [_not_recorded("WP01"), _not_recorded("WP02")]


def test_dry_run_json_window_gaps_empty_when_all_recorded(templates: _Templates, tmp_path: Path) -> None:
    mission = templates.copy("plain", tmp_path)
    _set_windows(mission, WP01="recorded", WP02="recorded")

    result, payload = _forecast_json(mission)

    assert result.exit_code == 0, result.output
    assert payload["window_gaps"] == []


def test_dry_run_refusal_payload_carries_window_gaps(templates: _Templates, tmp_path: Path) -> None:
    mission = templates.copy("stray", tmp_path)
    _set_windows(mission, WP01="not_recorded", WP02="recorded")

    result, payload = _forecast_json(mission)

    assert result.exit_code == 1, result.output
    assert payload.get("error_code") == FORECAST_REFUSED, payload
    assert payload.get("window_gaps") == [_not_recorded("WP01")], payload


def test_dry_run_human_prints_gap_block(templates: _Templates, tmp_path: Path) -> None:
    mission = templates.copy("plain", tmp_path)
    _set_windows(mission, WP01="not_recorded", WP02="not_recorded")

    result = cs.run_in_process(mission, ["consolidate", "--mission", mission.slug, "--dry-run"])

    assert result.exit_code == 0, result.output
    _assert_block(result.output, _line("WP01", LANE, "not recorded"), _line("WP02", LANE, "not recorded"))
    assert result.output.index(HEADING) < result.output.index("{"), f"the gap block must precede the JSON block:\n{result.output}"


def test_capture_failed_gap_shows_cause(templates: _Templates, tmp_path: Path) -> None:
    mission = templates.copy("plain", tmp_path)
    _set_windows(mission, WP01="recorded", WP02="capture_failed")

    forecast, payload = _forecast_json(mission)
    fresh = _fresh(mission)

    assert forecast.exit_code == 0, forecast.output
    assert payload["window_gaps"] == [{"wp_id": "WP02", "lane_id": LANE, "reason": "capture failed", "cause": "git_error", "detail": "test"}]
    _assert_passes(fresh)
    _assert_block(fresh.output, _line("WP02", LANE, "capture failed (git_error): test"))
    assert "WP01 (" not in fresh.output[fresh.output.index(HEADING) :].split("\n\n")[0], fresh.output


# --------------------------------------------------------------------------- single_branch


def test_single_branch_unrecorded_window_is_reported(templates: _Templates, tmp_path: Path) -> None:
    """FR-011: no recorded window on any opener; the verdict is today's derived window (pass), and both are reported."""
    mission = templates.copy("single_branch", tmp_path)
    _set_windows(mission, WP01="not_recorded", WP02="not_recorded")
    with fixture_phase():
        lanes = read_lanes_json(mission.repo / "kitty-specs" / mission.slug)
    require(lanes is not None and len(lanes.lanes) == 1, "a single_branch Mission has exactly one (planning) lane")
    lane_id = lanes.lanes[0].lane_id if lanes is not None else ""

    result = _fresh(mission)

    _assert_passes(result)
    _assert_block(result.output, _line("WP01", lane_id, "not recorded"), _line("WP02", lane_id, "not recorded"))
