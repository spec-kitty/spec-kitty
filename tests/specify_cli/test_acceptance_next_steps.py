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

from specify_cli.acceptance import AcceptanceSummary, _build_acceptance_instructions, collect_feature_summary, perform_acceptance
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
    lanes = {lane: [] for lane in summary.lanes}
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
