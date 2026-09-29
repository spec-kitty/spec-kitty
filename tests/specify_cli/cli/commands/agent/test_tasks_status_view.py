"""Per-branch unit tests for the pure status-aggregation core (WP05 / T022).

RED-first artifact (charter C-011): these tests import
``specify_cli.cli.commands.agent.tasks_status_view`` — which does NOT exist on the
lane base — so the whole module fails to collect (red) until
:func:`build_status_view` / :func:`build_stale_fallback_results` are implemented
(T023). Once green, every named branch of the ``StatusView`` aggregation entity
(``data-model.md`` §StatusView) is exercised with ``--cov-branch``: the kanban
lane rollup (in-board + ``"other"`` overflow), the population counts, the
done/weighted progress percentages (snapshot vs the ``else 0`` fall-through), the
stale count, the per-WP dependency readiness (satisfied / unsatisfied / missing),
and the stale-detection fallback builder (both ``reason`` arms + the no-id skip).

``build_status_view`` is PURE (INV-4): every input here is an in-memory fact — no
filesystem, git, or clock access — so a Fake reader is unnecessary; the injected
reads ARE the request fields. The T025 sentinel at the bottom additionally proves
the view's RETURN VALUE drives the ``status`` command (anti-shadow-code, FR-002).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.agent import tasks as tasks_module
from specify_cli.cli.commands.agent.tasks import app
from specify_cli.cli.commands.agent.tasks_status_view import (
    OTHER_LANE_BUCKET,
    StatusRequest,
    StatusView,
    build_stale_fallback_results,
    build_status_view,
)
from specify_cli.core.dependency_graph import DependencyReadiness
from specify_cli.core.stale_detection import StaleCheckResult
from specify_cli.status.models import NON_DISPLAY_LANES, Lane, StatusSnapshot
from tests.mocked_env import setup_mocked_env

pytestmark = pytest.mark.fast

_MID8 = "01KWF08S"


def _row(wp_id: str, lane: Lane, **extra: object) -> dict[str, object]:
    """One status WP row as the shell freezes it (id + lane + optional fields)."""
    return {"id": wp_id, "lane": lane, "title": f"{wp_id} title", **extra}


def _req(
    rows: list[dict[str, object]],
    *,
    snapshot: StatusSnapshot | None = None,
    wp_dependencies: dict[str, list[str]] | None = None,
) -> StatusRequest:
    return StatusRequest(
        work_packages=rows,
        snapshot=snapshot,
        wp_dependencies=wp_dependencies or {},
    )


def _snapshot(lanes_by_wp: dict[str, str]) -> StatusSnapshot:
    """A reduced snapshot carrying only the per-WP lane (all ``compute_weighted_progress`` reads)."""
    return StatusSnapshot(
        mission_slug=f"status-view-{_MID8}",
        materialized_at="2026-01-01T00:00:00+00:00",
        event_count=len(lanes_by_wp),
        last_event_id=None,
        work_packages={wp: {"lane": lane} for wp, lane in lanes_by_wp.items()},
        summary={},
    )


# ---------------------------------------------------------------------------
# Kanban lane rollup
# ---------------------------------------------------------------------------


def test_rollup_groups_rows_by_lane_preserving_row_identity() -> None:
    r_planned = _row("WP01", Lane.PLANNED)
    r_done = _row("WP02", Lane.DONE)
    view = build_status_view(_req([r_planned, r_done]))

    assert view.lanes[Lane.PLANNED] == [r_planned]
    assert view.lanes[Lane.DONE] == [r_done]
    # Same object identity, so downstream rendering mutations propagate.
    assert view.lanes[Lane.PLANNED][0] is r_planned


def test_rollup_seeds_every_non_genesis_lane_even_when_empty() -> None:
    view = build_status_view(_req([_row("WP01", Lane.PLANNED)]))
    for lane in Lane:
        if lane in NON_DISPLAY_LANES:
            assert lane not in view.lanes
        else:
            assert lane in view.lanes
    assert view.lanes[Lane.IN_REVIEW] == []


def test_rollup_routes_offboard_lane_to_other_bucket() -> None:
    genesis_row = _row("WP09", Lane.GENESIS)
    view = build_status_view(_req([_row("WP01", Lane.PLANNED), genesis_row]))
    assert view.lanes[OTHER_LANE_BUCKET] == [genesis_row]


def test_rollup_omits_other_bucket_when_all_rows_on_board() -> None:
    view = build_status_view(_req([_row("WP01", Lane.PLANNED)]))
    assert OTHER_LANE_BUCKET not in view.lanes


def test_lane_counts_is_first_seen_ordered_counter() -> None:
    rows = [
        _row("WP01", Lane.DONE),
        _row("WP02", Lane.PLANNED),
        _row("WP03", Lane.DONE),
    ]
    view = build_status_view(_req(rows))
    assert view.lane_counts == {Lane.DONE: 2, Lane.PLANNED: 1}
    # Order mirrors ``dict(Counter(...))`` — DONE first-seen before PLANNED.
    assert list(view.lane_counts) == [Lane.DONE, Lane.PLANNED]


# ---------------------------------------------------------------------------
# Population counts
# ---------------------------------------------------------------------------


def test_population_counts_partition_the_board() -> None:
    rows = [
        _row("WP01", Lane.PLANNED),
        _row("WP02", Lane.CLAIMED),
        _row("WP03", Lane.IN_PROGRESS),
        _row("WP04", Lane.IN_REVIEW),
        _row("WP05", Lane.FOR_REVIEW),
        _row("WP06", Lane.APPROVED),
        _row("WP07", Lane.DONE),
    ]
    view = build_status_view(_req(rows))
    assert view.total_wps == 7
    assert view.done_count == 1
    assert view.planned_count == 1
    # claimed + in_progress + in_review + for_review
    assert view.in_progress_count == 4


# ---------------------------------------------------------------------------
# Progress percentages
# ---------------------------------------------------------------------------


def test_done_percentage_is_rounded_share() -> None:
    rows = [_row("WP01", Lane.DONE), _row("WP02", Lane.PLANNED), _row("WP03", Lane.PLANNED)]
    view = build_status_view(_req(rows))
    assert view.done_percentage == pytest.approx(33.3)


def test_progress_percentage_weighted_from_snapshot() -> None:
    rows = [_row("WP01", Lane.DONE)]
    snap = _snapshot({"WP01": "done"})
    view = build_status_view(_req(rows, snapshot=snap))
    # A single ``done`` WP weights to 100%.
    assert view.progress_percentage == pytest.approx(100.0)


def test_progress_percentage_falls_through_to_int_zero_without_snapshot() -> None:
    view = build_status_view(_req([_row("WP01", Lane.PLANNED)], snapshot=None))
    # Parity: the live ``else 0`` arm returns a bare ``int`` (JSON -> ``0``, not ``0.0``).
    assert view.progress_percentage == 0
    assert isinstance(view.progress_percentage, int)


# ---------------------------------------------------------------------------
# Stale count
# ---------------------------------------------------------------------------


def test_stale_count_counts_flagged_rows() -> None:
    rows = [
        _row("WP01", Lane.IN_PROGRESS, is_stale=True),
        _row("WP02", Lane.IN_PROGRESS, is_stale=False),
        _row("WP03", Lane.IN_PROGRESS),  # no is_stale key -> falsy
    ]
    view = build_status_view(_req(rows))
    assert view.stale_count == 1


# ---------------------------------------------------------------------------
# Dependency readiness (canonical: approved/done satisfy the gate)
# ---------------------------------------------------------------------------


def test_dependency_readiness_satisfied_when_dep_approved() -> None:
    rows = [_row("WP01", Lane.APPROVED), _row("WP02", Lane.PLANNED)]
    view = build_status_view(_req(rows, wp_dependencies={"WP02": ["WP01"]}))
    readiness = view.dependency_readiness["WP02"]
    assert isinstance(readiness, DependencyReadiness)
    assert readiness.satisfied is True
    assert readiness.unsatisfied == ()


def test_dependency_readiness_unsatisfied_when_dep_still_in_progress() -> None:
    rows = [_row("WP01", Lane.IN_PROGRESS), _row("WP02", Lane.PLANNED)]
    view = build_status_view(_req(rows, wp_dependencies={"WP02": ["WP01"]}))
    readiness = view.dependency_readiness["WP02"]
    assert readiness.satisfied is False
    assert readiness.unsatisfied == ("WP01",)


def test_dependency_readiness_treats_missing_dep_as_unsatisfied() -> None:
    rows = [_row("WP02", Lane.PLANNED)]
    view = build_status_view(_req(rows, wp_dependencies={"WP02": ["WP01"]}))
    assert view.dependency_readiness["WP02"].satisfied is False


def test_dependency_readiness_empty_when_no_declarations() -> None:
    view = build_status_view(_req([_row("WP01", Lane.PLANNED)]))
    assert view.dependency_readiness == {}


def test_row_without_valid_id_is_excluded_from_the_lane_map() -> None:
    # A row lacking "id" is still rolled up by lane, but contributes no lane-map
    # entry — a dependency on its (unknown) id therefore reads as unsatisfied.
    idless: dict[str, object] = {"lane": Lane.APPROVED, "title": "no id"}
    view = build_status_view(
        _req([idless, _row("WP02", Lane.PLANNED)], wp_dependencies={"WP02": ["WP01"]})
    )
    assert view.total_wps == 2
    assert view.dependency_readiness["WP02"].satisfied is False


# ---------------------------------------------------------------------------
# Stale-detection fallback builder (pure; both reason arms + the no-id skip)
# ---------------------------------------------------------------------------


def test_stale_fallback_default_reason_is_not_applicable() -> None:
    results = build_stale_fallback_results(
        [{"id": "WP01", "workspace_kind": "unknown", "execution_mode": "code_change"}],
        RuntimeError("boom"),
    )
    result = cast(StaleCheckResult, results["WP01"])
    assert result.stale.status == "not_applicable"
    assert result.stale.reason == "stale_detection_unavailable"
    assert result.is_stale is False
    assert result.error == "boom"


def test_stale_fallback_planning_artifact_repo_root_reason() -> None:
    results = build_stale_fallback_results(
        [{"id": "WP01", "workspace_kind": "repo_root", "execution_mode": "planning_artifact"}],
        RuntimeError("boom"),
    )
    assert (
        cast(StaleCheckResult, results["WP01"]).stale.reason
        == "planning_artifact_repo_root_shared_workspace"
    )


def test_stale_fallback_repo_root_code_wp_is_not_reported_stale_detection_unavailable() -> None:
    """#5100 WP04 T019: a single_branch repo-root CODE work package must get
    the SAME ``planning_artifact_repo_root_shared_workspace`` fallback reason
    a planning_artifact repo-root WP does, never
    ``stale_detection_unavailable`` -- the gate is ``workspace_kind ==
    "repo_root"`` alone (line 147, ``fallback_reason``), NOT also
    ``execution_mode == "planning_artifact"``. Mutation-checked: restoring
    the retired ``execution_mode``-gated form makes this test fail (see the
    docstring's contrast test below)."""
    results = build_stale_fallback_results(
        [{"id": "WP01", "workspace_kind": "repo_root", "execution_mode": "code_change"}],
        RuntimeError("boom"),
    )
    result = cast(StaleCheckResult, results["WP01"])
    assert result.stale.reason != "stale_detection_unavailable"
    assert (
        cast(StaleCheckResult, results["WP01"]).stale.reason
        == "planning_artifact_repo_root_shared_workspace"
    )


def test_stale_fallback_skips_rows_without_an_id() -> None:
    results = build_stale_fallback_results([{"title": "no id here"}], RuntimeError("boom"))
    assert results == {}


def test_stale_fallback_uses_work_package_id_alias() -> None:
    results = build_stale_fallback_results([{"work_package_id": "WP07"}], RuntimeError("x"))
    assert "WP07" in results


# ---------------------------------------------------------------------------
# T025 -- fake-core sentinel: the view's RETURN VALUE drives ``status``.
# ---------------------------------------------------------------------------
#
# The anti-shadow-code guard (FR-002): a "called-but-result-discarded" core would
# pass a grep-for-callers check while the old inline aggregation still ran. This
# injects a SENTINEL ``StatusView`` that CONTRADICTS what the real
# ``build_status_view`` would produce and asserts the command's observable JSON +
# human output FOLLOW the sentinel — proving the core genuinely DRIVES ``status``.


def _status_mission(root: Path, slug: str) -> Path:
    feature_dir = root / "kitty-specs" / slug
    (feature_dir / "tasks").mkdir(parents=True)
    (root / ".kittify").mkdir(exist_ok=True)
    (feature_dir / "tasks" / "WP01-fixture.md").write_text(
        "---\n"
        "work_package_id: WP01\n"
        "title: Fixture WP01\n"
        "execution_mode: code_change\n"
        "agent: testbot\n"
        "---\n\n# WP01\n\n## Activity Log\n",
        encoding="utf-8",
    )
    (feature_dir / "tasks.md").write_text(
        "# Work Packages\n\n## WP01 - fixture\n- [ ] T001 do a thing\n", encoding="utf-8"
    )
    (feature_dir / "spec.md").write_text("# Spec\n\nFR-001 do a thing.\n", encoding="utf-8")
    return feature_dir


def _sentinel_view() -> StatusView:
    """A StatusView whose aggregates contradict the single-planned-WP fixture."""
    lanes: dict[Lane | str, list[dict[str, object]]] = {
        lane: [] for lane in Lane if lane not in NON_DISPLAY_LANES
    }
    return StatusView(
        lanes=lanes,
        lane_counts={Lane.DONE: 7},
        total_wps=999,
        done_count=7,
        in_progress_count=3,
        planned_count=11,
        stale_count=5,
        done_percentage=42.4,
        progress_percentage=88.8,
        dependency_readiness={},
    )


def test_sentinel_view_drives_the_json_envelope(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A sentinel view's aggregates drive the ``--json`` envelope, not the real data.

    The fixture has ONE planned WP (real ``total_wps``/``done_count`` = 1/0), yet
    every aggregate key in the envelope follows the sentinel — proving the view
    drives the reported numbers.
    """
    fd = _status_mission(tmp_path, f"sentinel-status-json-{_MID8}")
    monkeypatch.setattr(tasks_module, "build_status_view", lambda _req: _sentinel_view())
    with setup_mocked_env(fd.parent.parent, mission_slug=fd.name, workspace_resolution=FileNotFoundError):
        result = CliRunner().invoke(app, ["status", "--mission", fd.name, "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["total_wps"] == 999
    assert payload["done_count"] == 7
    assert payload["done_percentage"] == 42.4
    assert payload["progress_percentage"] == 88.8
    assert payload["weighted_percentage"] == 88.8
    assert payload["stale_wps"] == 5
    assert payload["by_lane"] == {"done": 7}


def test_sentinel_view_drives_the_human_summary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The rendered human table follows the sentinel totals, not the real fixture."""
    fd = _status_mission(tmp_path, f"sentinel-status-human-{_MID8}")
    monkeypatch.setattr(tasks_module, "build_status_view", lambda _req: _sentinel_view())
    with setup_mocked_env(fd.parent.parent, mission_slug=fd.name, workspace_resolution=FileNotFoundError):
        result = CliRunner().invoke(app, ["status", "--mission", fd.name])
    assert result.exit_code == 0, result.output
    # The Summary panel echoes the sentinel Total WPs (999), never the real 1.
    assert "999" in result.output
    assert "88.8%" in result.output
