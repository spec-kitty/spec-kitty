"""WP14 (coord-artifact-single-home-01M3V4BE), B3: orchestrator ``commit_surfaces``/``warnings``.

Covers ``orchestrator_api/commands.py::_record_analysis_commit_surfaces_payload``
(T076) with a one-surface-refused fixture: a stubbed
:class:`~specify_cli.coordination.commit_router.CommitRouterResult` carrying a
committed PRIMARY surface alongside a COORDINATION surface refused with
``STATUS_LOCK_HELD`` -- the same "test via a stubbed CommitRouterResult,
labelled as a unit test" escape hatch the WP prompt names for this exact edge
case.

Mutation-sensitive: kills M5 from the cycle 1 review's mutation table
(``_record_analysis_commit_surfaces_payload`` always returning ``{}``), which
survived all 177 pre-existing orchestrator tests because none of them ever
drove this function with a non-empty, non-fully-committed ``surfaces`` tuple.
"""

from __future__ import annotations

import pytest

from specify_cli.coordination.commit_outcome import PathFate, SurfaceOutcome
from specify_cli.coordination.commit_router import CommitRouterResult
from specify_cli.orchestrator_api import design_phase

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_TARGET_BRANCH = "topic"
_COORD_BRANCH = "kitty/mission-demo-01TESTPLAN"


def _mixed_surfaces_result() -> CommitRouterResult:
    """A split batch: PRIMARY committed cleanly, COORDINATION refused by a contended status lock."""
    primary = SurfaceOutcome(
        surface="primary",
        branch=_TARGET_BRANCH,
        status="committed",
        commit_hash="abc1234567890",
        committed=("kitty-specs/demo/analysis-report.md",),
    )
    coordination = SurfaceOutcome(
        surface="coordination",
        branch=_COORD_BRANCH,
        status="error",
        commit_hash=None,
        refused=(PathFate(path="kitty-specs/demo/status.events.jsonl", reason="STATUS_LOCK_HELD"),),
        diagnostic="status lock held by another writer",
    )
    return CommitRouterResult(
        status="committed",
        placement_ref=_TARGET_BRANCH,
        commit_hash="abc1234567890",
        surfaces=(primary, coordination),
    )


def test_commit_surfaces_payload_is_empty_for_none() -> None:
    """``None`` (the best-effort commit itself raised) adds nothing -- additive-only."""
    assert design_phase._record_analysis_commit_surfaces_payload(None) == {}


def test_commit_surfaces_payload_is_empty_for_empty_surfaces() -> None:
    """The legacy empty-``surfaces`` shape adds nothing either (C-008 control)."""
    result = CommitRouterResult(status="committed", placement_ref=_TARGET_BRANCH, commit_hash="abc")
    assert design_phase._record_analysis_commit_surfaces_payload(result) == {}


def test_commit_surfaces_payload_names_the_refused_surface_and_reason() -> None:
    """Load-bearing (kills M5): the refused COORDINATION surface's fate and
    reason reach ``commit_surfaces``, even though the top-level/caller status
    is ``"committed"`` -- the exact masking this WP cures (#5513, #5501)."""
    mixed = _mixed_surfaces_result()

    payload = design_phase._record_analysis_commit_surfaces_payload(mixed)

    assert "commit_surfaces" in payload
    surface_names = {entry["surface"] for entry in payload["commit_surfaces"]}
    assert surface_names == {"primary", "coordination"}
    coordination_payload = next(entry for entry in payload["commit_surfaces"] if entry["surface"] == "coordination")
    assert coordination_payload["refused"][0]["reason"] == "STATUS_LOCK_HELD"


def test_commit_surfaces_payload_adds_warnings_for_an_incomplete_batch() -> None:
    """``warnings`` is populated when some surface is neither ``committed`` nor
    ``unchanged`` (research D8); the rendered text names the surface and reason."""
    mixed = _mixed_surfaces_result()

    payload = design_phase._record_analysis_commit_surfaces_payload(mixed)

    assert "warnings" in payload
    warnings_text = " ".join(payload["warnings"])
    assert "coordination" in warnings_text
    assert "STATUS_LOCK_HELD" in warnings_text


def test_commit_surfaces_payload_omits_warnings_for_an_all_success_batch() -> None:
    """D8 rule control: an all-committed batch carries ``commit_surfaces`` but no ``warnings``."""
    all_ok = CommitRouterResult(
        status="committed",
        placement_ref=_TARGET_BRANCH,
        commit_hash="abc",
        surfaces=(SurfaceOutcome(surface="primary", branch=_TARGET_BRANCH, status="committed", commit_hash="abc", committed=("a",)),),
    )

    payload = design_phase._record_analysis_commit_surfaces_payload(all_ok)

    assert "commit_surfaces" in payload
    assert "warnings" not in payload
