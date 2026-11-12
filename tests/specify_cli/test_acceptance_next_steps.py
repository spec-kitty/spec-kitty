"""#7599: accept's local-mode "Next steps" follow the Mission's consolidation state.

A local-mode acceptance on the target (integration) branch used to print
"Acceptance recorded directly on `<branch>`. No merge needed." for every Mission,
including a coordination Mission and a flat ``lanes`` Mission whose lanes still
have to be consolidated. Those Missions land only through ``spec-kitty
consolidate``, so the "Next steps" must name it, and the branch named must be the
one the acceptance record was committed to (the Mission/coordination branch from
``meta.json``), not the checkout's branch.

Controls: a Mission with nothing left to consolidate keeps the "No merge needed"
text byte-identical, and the ``pr`` and ``checklist`` arms are unchanged.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from specify_cli.acceptance import (
    AcceptanceSummary,
    _acceptance_record_branch,
    _build_acceptance_instructions,
    _has_lanes_to_consolidate,
    collect_feature_summary,
    perform_acceptance,
)
from specify_cli.lanes.branch_naming import PLANNING_LANE_ID
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import write_lanes_json
from tests.specify_cli.test_acceptance_regressions import _FEATURE_SLUG, _create_test_feature, _seed_lane_gate

pytestmark = pytest.mark.fast

_COORD_BRANCH = "kitty/mission-099-test-feature-01ABCDEF"
_NO_MERGE_NEEDED = "Acceptance recorded directly on `main`. No merge needed."
_CONSOLIDATE = f"spec-kitty consolidate --mission {_FEATURE_SLUG}"


def _summary_on_main(tmp_path: Path, **meta_updates: Any) -> AcceptanceSummary:
    """An accepted-ready summary for a Mission checked out on its target branch ``main``."""
    repo_root, feature_dir = _create_test_feature(tmp_path)
    _seed_lane_gate(repo_root, feature_dir, target_branch="main")
    summary = collect_feature_summary(tmp_path, _FEATURE_SLUG)
    object.__setattr__(summary, "branch", "main")
    # The topology facts are read by ``perform_acceptance`` from meta.json; the
    # fixture has no coordination worktree, so they are written after the summary
    # is collected (as the #6450 pr-arm regression does).
    if meta_updates:
        meta_path = feature_dir / "meta.json"
        meta = json.loads(meta_path.read_text())
        meta.update(meta_updates)
        meta_path.write_text(json.dumps(meta, indent=2) + "\n")
    return summary


def _with_lanes_still_to_consolidate(summary: AcceptanceSummary) -> AcceptanceSummary:
    """WP01 (code lane ``lane-a``) approved but not yet consolidated (``done`` comes with the landing)."""
    lanes: dict[str, list[str]] = {lane: [] for lane in summary.lanes}
    lanes["approved"] = ["WP01"]
    object.__setattr__(summary, "lanes", lanes)
    return summary


# ---------------------------------------------------------------------------
# Red cells: a Mission with lanes still to consolidate
# ---------------------------------------------------------------------------


def test_local_accept_on_target_of_coordination_mission_names_consolidate(tmp_path: Path) -> None:
    summary = _summary_on_main(tmp_path, topology="lanes_with_coord", coordination_branch=_COORD_BRANCH)

    result = perform_acceptance(summary, mode="local", actor="tester", auto_commit=False)

    text = " ".join(result.instructions)
    assert "No merge needed" not in text, result.instructions
    assert _CONSOLIDATE in text, result.instructions
    assert f"`{_COORD_BRANCH}`" in text, f"must name the branch the record was committed to: {result.instructions}"


def test_local_accept_on_target_of_recorded_coordination_branch_names_consolidate(tmp_path: Path) -> None:
    """A recorded ``coordination_branch`` is coordination-bearing whatever the ``topology`` spelling."""
    summary = _summary_on_main(tmp_path, coordination_branch=_COORD_BRANCH)

    result = perform_acceptance(summary, mode="local", actor="tester", auto_commit=False)

    text = " ".join(result.instructions)
    assert "No merge needed" not in text, result.instructions
    assert _CONSOLIDATE in text, result.instructions


def test_local_accept_on_target_of_flat_lanes_mission_with_lanes_to_consolidate(tmp_path: Path) -> None:
    summary = _with_lanes_still_to_consolidate(_summary_on_main(tmp_path, topology="lanes"))

    result = perform_acceptance(summary, mode="local", actor="tester", auto_commit=False)

    text = " ".join(result.instructions)
    assert "No merge needed" not in text, result.instructions
    assert _CONSOLIDATE in text, result.instructions


# ---------------------------------------------------------------------------
# Controls: byte-identical texts
# ---------------------------------------------------------------------------


def test_local_accept_with_nothing_to_consolidate_keeps_no_merge_needed(tmp_path: Path) -> None:
    """Flat ``lanes`` Mission, every WP ``done``: nothing remains to consolidate."""
    summary = _summary_on_main(tmp_path, topology="lanes")

    result = perform_acceptance(summary, mode="local", actor="tester", auto_commit=False)

    assert result.instructions == [_NO_MERGE_NEEDED]


def test_pr_accept_on_target_of_coordination_mission_is_unchanged(tmp_path: Path) -> None:
    summary = _summary_on_main(tmp_path, topology="coord", coordination_branch=_COORD_BRANCH)

    result = perform_acceptance(summary, mode="pr", actor="tester", auto_commit=False)

    assert result.instructions == [
        f"Acceptance recorded on `main`. This Mission lands through `{_CONSOLIDATE}`; its coordination branch is internal and that command lands it."
    ]


def _bare_summary(tmp_path: Path) -> Any:
    return cast(Any, SimpleNamespace(feature=_FEATURE_SLUG, worktree_root=tmp_path, primary_repo_root=tmp_path))


def test_pr_flat_integration_branch_text_is_unchanged(tmp_path: Path) -> None:
    instructions, _cleanup = _build_acceptance_instructions(_bare_summary(tmp_path), "pr", "main", True)
    assert instructions == ["Acceptance recorded on integration branch `main`. Push and open a pull request if needed."]


def test_checklist_text_is_unchanged(tmp_path: Path) -> None:
    instructions, _cleanup = _build_acceptance_instructions(_bare_summary(tmp_path), "checklist", "main", True)
    assert instructions == [f"All checks passed. Recommended next step: `{_CONSOLIDATE}`."]


def test_local_off_target_text_is_unchanged(tmp_path: Path) -> None:
    instructions, _cleanup = _build_acceptance_instructions(_bare_summary(tmp_path), "local", _COORD_BRANCH, False)
    assert instructions == [
        f"Acceptance passed. Run the mission consolidation: `{_CONSOLIDATE}`",
        "After merge, run /spec-kitty-mission-review and the retrospective workflow.",
    ]


# ---------------------------------------------------------------------------
# Helpers: the lanes-to-consolidate fact and the record branch
# ---------------------------------------------------------------------------


def _lane(lane_id: str, *wp_ids: str) -> ExecutionLane:
    return ExecutionLane(lane_id=lane_id, wp_ids=wp_ids, write_scope=(), predicted_surfaces=(), depends_on_lanes=(), parallel_group=0)


def _feature_with_lanes(tmp_path: Path, *lanes: ExecutionLane) -> Path:
    feature_dir = tmp_path / "kitty-specs" / _FEATURE_SLUG
    feature_dir.mkdir(parents=True)
    write_lanes_json(
        feature_dir,
        LanesManifest(
            version=1,
            mission_slug=_FEATURE_SLUG,
            mission_id=None,
            mission_branch="main",
            target_branch="main",
            lanes=list(lanes),
            computed_at="2026-11-12T00:00:00Z",
            computed_from="test",
        ),
    )
    return feature_dir


def _lanes_summary(feature_dir: Path, *, approved: list[str]) -> Any:
    return cast(Any, SimpleNamespace(feature_dir=feature_dir, lanes={"approved": approved, "done": []}))


def test_code_lane_with_approved_wp_has_lanes_to_consolidate(tmp_path: Path) -> None:
    feature_dir = _feature_with_lanes(tmp_path, _lane("lane-a", "WP01"), _lane(PLANNING_LANE_ID, "WP02"))
    assert _has_lanes_to_consolidate(_lanes_summary(feature_dir, approved=["WP01"]), lands_by_consolidation=False)


def test_only_planning_lane_wps_pending_has_nothing_to_consolidate(tmp_path: Path) -> None:
    feature_dir = _feature_with_lanes(tmp_path, _lane("lane-a", "WP01"), _lane(PLANNING_LANE_ID, "WP02"))
    assert not _has_lanes_to_consolidate(_lanes_summary(feature_dir, approved=["WP02"]), lands_by_consolidation=False)


def test_no_lanes_manifest_has_nothing_to_consolidate(tmp_path: Path) -> None:
    assert not _has_lanes_to_consolidate(_lanes_summary(tmp_path, approved=["WP01"]), lands_by_consolidation=False)


def test_corrupt_lanes_manifest_has_nothing_to_consolidate(tmp_path: Path) -> None:
    feature_dir = _feature_with_lanes(tmp_path, _lane("lane-a", "WP01"))
    for manifest in feature_dir.rglob("lanes.json"):
        manifest.write_text("{not json", encoding="utf-8")
    assert not _has_lanes_to_consolidate(_lanes_summary(feature_dir, approved=["WP01"]), lands_by_consolidation=False)


def test_coordination_mission_has_lanes_to_consolidate_until_landed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    summary = _lanes_summary(tmp_path, approved=[])
    assert _has_lanes_to_consolidate(summary, lands_by_consolidation=True)

    monkeypatch.setattr("mission_runtime.landing.mission_has_landed", lambda _primary_dir: True)
    assert not _has_lanes_to_consolidate(summary, lands_by_consolidation=True)


@pytest.mark.parametrize(
    ("meta", "expected"),
    [
        ({"coordination_branch": _COORD_BRANCH, "mission_branch": "kitty/mission-other"}, _COORD_BRANCH),
        ({"mission_branch": "kitty/mission-other"}, "kitty/mission-other"),
        ({}, "main"),
    ],
)
def test_acceptance_record_branch(tmp_path: Path, meta: dict[str, str], expected: str) -> None:
    (tmp_path / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    assert _acceptance_record_branch(tmp_path, "main") == expected


def test_local_arm_with_lanes_to_consolidate_falls_back_to_checkout_branch(tmp_path: Path) -> None:
    instructions, _cleanup = _build_acceptance_instructions(_bare_summary(tmp_path), "local", "main", True, lanes_to_consolidate=True)
    assert instructions == [f"Acceptance recorded on `main`. This Mission lands through `{_CONSOLIDATE}`; run it next."]


def test_local_arm_names_record_branch(tmp_path: Path) -> None:
    instructions, _cleanup = _build_acceptance_instructions(_bare_summary(tmp_path), "local", "main", True, lanes_to_consolidate=True, record_branch=_COORD_BRANCH)
    assert instructions == [f"Acceptance recorded on `{_COORD_BRANCH}`. This Mission lands through `{_CONSOLIDATE}`; run it next."]
