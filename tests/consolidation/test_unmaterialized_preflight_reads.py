"""The consolidation status readers read through the one status read door (WP07, FR-005).

Mission lane-worktree-model-hardening, ADR ``2026-11-06-2-one-status-read-contract``. One pin
per topology state, on real git fixtures from the WP04 matrix builder (no resolver is patched):
the repository root checkout carries a stale decoy log (``planned``) for ``lanes_with_coord``,
and the coordination branch carries the authority (``planned -> claimed -> in_progress``).

Before the migration the legacy path projection read an empty history for an unmaterialized
or empty coordination worktree, so the preflight saw no WP and the post-merge validator
reported a missing log although the branch held the real lanes.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
import typer

from specify_cli.consolidation import done_bookkeeping, forecast, phase_advance, preflight
from tests.status.test_status_read_matrix import (
    COORD_BRANCH,
    EMPTY,
    KITTY_SPECS,
    LANES,
    LANES_WITH_COORD,
    MATERIALIZED,
    SINGLE_BRANCH,
    SLUG,
    UNMATERIALIZED,
    MatrixMission,
    build_matrix_mission,
    git,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

STATE_SINGLE_BRANCH = "single_branch"
STATE_LANES = "lanes"
STATE_COORD_MATERIALIZED = "coord-materialized"
STATE_COORD_EMPTY = "coord-empty-worktree"
STATE_COORD_UNMATERIALIZED = "coord-unmaterialized"
STATE_COORD_PRESEED = "coord-preseed"
STATE_CONSOLIDATED = "consolidated"

ALL_STATES = [
    STATE_SINGLE_BRANCH,
    STATE_LANES,
    STATE_COORD_MATERIALIZED,
    STATE_COORD_EMPTY,
    STATE_COORD_UNMATERIALIZED,
    STATE_COORD_PRESEED,
    STATE_CONSOLIDATED,
]

#: The WP01 lane each state's declared source holds.
EXPECTED_LANE = {
    STATE_SINGLE_BRANCH: "in_progress",
    STATE_LANES: "in_progress",
    STATE_COORD_MATERIALIZED: "in_progress",
    STATE_COORD_EMPTY: "in_progress",
    STATE_COORD_UNMATERIALIZED: "in_progress",
    STATE_COORD_PRESEED: "planned",  # declared fallback: the write checkout's copy
    STATE_CONSOLIDATED: "planned",  # landed: the target's copy is the authority
}

REF_STATES = {STATE_COORD_EMPTY, STATE_COORD_UNMATERIALIZED}
COORD_STATES = {STATE_COORD_MATERIALIZED, STATE_COORD_EMPTY, STATE_COORD_UNMATERIALIZED}


def _build(tmp_path: Path, state: str) -> MatrixMission:
    if state == STATE_SINGLE_BRANCH:
        return build_matrix_mission(tmp_path, SINGLE_BRANCH)
    if state == STATE_LANES:
        return build_matrix_mission(tmp_path, LANES)
    if state == STATE_COORD_MATERIALIZED:
        return build_matrix_mission(tmp_path, LANES_WITH_COORD, MATERIALIZED)
    if state == STATE_COORD_PRESEED:
        return build_matrix_mission(tmp_path, LANES_WITH_COORD, EMPTY)
    mission = build_matrix_mission(tmp_path, LANES_WITH_COORD, UNMATERIALIZED)
    if state == STATE_COORD_EMPTY:
        coord_worktree = mission.repo / ".worktrees" / f"{SLUG}-coord"
        git(mission.repo, "worktree", "add", "-q", str(coord_worktree), COORD_BRANCH)
        shutil.rmtree(coord_worktree / KITTY_SPECS / SLUG)
    elif state == STATE_CONSOLIDATED:
        meta_path = mission.root_mission_dir / "meta.json"
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        meta["merged_at"] = "2026-11-06T01:00:00+00:00"
        meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
        git(mission.repo, "branch", "-D", COORD_BRANCH)
    return mission


@pytest.mark.parametrize("state", ALL_STATES)
def test_unmaterialized_preflight_reports_real_lanes(tmp_path: Path, state: str) -> None:
    """The bookkeeping preflight reads the declared source's lanes, never an empty history."""
    mission = _build(tmp_path, state)

    lanes = preflight._current_lanes_or_empty(mission.repo, SLUG)

    assert lanes == {"WP01": EXPECTED_LANE[state]}


@pytest.mark.parametrize("state", ALL_STATES)
def test_canceled_reader_reads_the_declared_source(tmp_path: Path, state: str) -> None:
    """``acceptably_canceled_wp_ids`` reduces the door's events (one reader for every state)."""
    mission = _build(tmp_path, state)

    events = done_bookkeeping._canceled_status_events(mission.repo, SLUG, None)

    assert [str(event.to_lane) for event in events][-1] == EXPECTED_LANE[state]
    assert done_bookkeeping.acceptably_canceled_wp_ids(mission.repo, SLUG) == set()


@pytest.mark.parametrize("state", ALL_STATES)
def test_post_merge_validator_reports_the_real_lane(tmp_path: Path, state: str, capsys: pytest.CaptureFixture[str]) -> None:
    """The post-merge done check names the source's real lane, not a missing log."""
    mission = _build(tmp_path, state)

    with pytest.raises(typer.Exit):
        done_bookkeeping._assert_merged_wps_reached_done(mission.repo, SLUG, ["WP01"])

    assert f"WP01={EXPECTED_LANE[state]}" in capsys.readouterr().out.replace("\n", "")


@pytest.mark.parametrize("state", ALL_STATES)
def test_durable_coordination_lanes_read_the_committed_ref(tmp_path: Path, state: str) -> None:
    """The resume authority reads the committed coordination ref through the door's committed entry."""
    mission = _build(tmp_path, state)

    lanes = done_bookkeeping._durable_coordination_lanes(repo_root=mission.repo, mission_slug=SLUG, candidate_wps=["WP01"])

    if state in COORD_STATES:
        assert lanes == {"WP01": "in_progress"}
    else:
        assert lanes is None


@pytest.mark.parametrize("state", ALL_STATES)
def test_forecast_claim_dir_is_a_path_source_or_refuses(tmp_path: Path, state: str, capsys: pytest.CaptureFixture[str]) -> None:
    """The dry-run claim reads a path source; a ref source refuses with the door's remedy."""
    mission = _build(tmp_path, state)

    if state in REF_STATES:
        with pytest.raises(typer.Exit):
            forecast._forecast_claim_status_dir(mission.repo, SLUG, json_output=True)
        payload = json.loads(capsys.readouterr().out)
        assert "spec-kitty materialize" in payload["error"]
        return
    status_dir = forecast._forecast_claim_status_dir(mission.repo, SLUG, json_output=True)
    expected = mission.coord_mission_dir if state == STATE_COORD_MATERIALIZED else mission.root_mission_dir
    assert status_dir.resolve() == expected.resolve()


@pytest.mark.parametrize("state", ALL_STATES)
def test_phase_advance_projects_only_a_landed_mission(tmp_path: Path, state: str) -> None:
    """The completed-Mission ``--resume`` path is the door's consolidated target, else ``None``."""
    mission = _build(tmp_path, state)
    run = SimpleNamespace(main_repo=mission.repo, mission_slug=SLUG, target_feature_dir=mission.root_mission_dir)

    projected = phase_advance._completed_mission_projected_events_path(cast(Any, run))

    if state == STATE_CONSOLIDATED:
        assert projected is not None
        assert projected.resolve() == (mission.root_mission_dir / "status.events.jsonl").resolve()
    else:
        assert projected is None


def test_phase_advance_has_no_landed_reader_copy() -> None:
    """The landed signal is ``mission_runtime.mission_has_landed`` alone (no third copy)."""
    assert not hasattr(phase_advance, "_primary_mission_is_merged")
