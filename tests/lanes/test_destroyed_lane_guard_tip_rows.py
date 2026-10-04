"""Seam tests for the destroyed-lane guard's tip-based decision rows (#5115 / WP07).

``test_destroyed_lane_guard_helpers.py`` pins the pure ``_destroyed_lane_verdict``
table and ``test_issue_4889_destroyed_lane_guard.py`` pins the base-reachability
half through the allocator. The tip-based half (``_refuse_on_tip``) and the
guard's entry short-circuit (``_refuse_if_lane_destroyed``) had no focused
guard: each row was only observable through a slow ``implement`` CLI replay in
``test_destroyed_lane_guard_lanes_topology.py``. These tests drive the two
functions directly with the git-facing collaborators replaced, one row per
test, so each decision-table row fails on its own when it is broken.

Rows (``worktree_allocator._refuse_on_tip``):

* no recorded tip                       -> ``LANE_WORK_TIP_UNKNOWN``
* tip == base, recorder hook inactive   -> ``LANE_WORK_TIP_UNKNOWN`` (recorder wording)
* tip == base, recorder hook active     -> falls through to the absorption check
* absorbed                              -> proceed
* not absorbed                          -> ``DESTROYED_LANE`` naming the tip
* absorption cannot be evaluated        -> ``DESTROYED_LANE`` naming the tip (fail closed)
* context deleted (no base)             -> absorption is evaluated with ``base=None``

Rows (``worktree_allocator._refuse_if_lane_destroyed``):

* neither a context nor a tip           -> proceed without reading status
* a tip but no context (FR-020)         -> the tip half still decides (never fail open)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from specify_cli.lanes import worktree_allocator as allocator
from specify_cli.lanes.lane_tip import AbsorptionUnsupported, tip_ref
from specify_cli.lanes.worktree_allocator import DestroyedLaneError, LaneWorkTipUnknownError
from specify_cli.workspace.context import WorkspaceContext

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_LANE = "lane-a"
_WP = "WP01"
_BRANCH = "kitty/mission-seam-lane-a"
_TARGET = "main"
_BASE = "b" * 40
_TIP = "a" * 40


def _context(base_commit: str | None = _BASE) -> WorkspaceContext:
    return WorkspaceContext(
        wp_id=_WP,
        mission_slug="seam",
        worktree_path=".worktrees/seam-lane-a",
        branch_name=_BRANCH,
        base_branch="main",
        base_commit=base_commit,
        dependencies=[],
        created_at="2026-10-04T00:00:00+00:00",
        created_by="test",
        vcs_backend="git",
        lane_id=_LANE,
        lane_wp_ids=[_WP],
        current_wp=_WP,
    )


def _refuse_on_tip(tip: str | None, context: WorkspaceContext | None) -> None:
    allocator._refuse_on_tip(Path("repo"), lane_id=_LANE, wp_id=_WP, branch=_BRANCH, target_branch=_TARGET, tip=tip, context=context)


def _recorder(monkeypatch: pytest.MonkeyPatch, *, active: bool) -> list[Path]:
    """Replace the recorder-activity probe; returns the repos it was asked about."""
    asked: list[Path] = []

    def _active(repo_root: Path) -> bool:
        asked.append(repo_root)
        return active

    monkeypatch.setattr("specify_cli.policy.lane_tip_recorder.lane_tip_recorder_active", _active)
    return asked


def _absorption(monkeypatch: pytest.MonkeyPatch, *, result: bool | None) -> list[tuple[str, str, str | None]]:
    """Replace ``is_absorbed``; ``None`` raises :class:`AbsorptionUnsupported`. Returns the calls."""
    calls: list[tuple[str, str, str | None]] = []

    def _is_absorbed(_repo_root: Path, tip: str, target: str, base: str | None) -> bool:
        calls.append((tip, target, base))
        if result is None:
            raise AbsorptionUnsupported("simulated git < 2.38")
        return result

    monkeypatch.setattr(allocator, "is_absorbed", _is_absorbed)
    return calls


def test_no_recorded_tip_fails_closed_as_unknown(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _absorption(monkeypatch, result=True)

    with pytest.raises(LaneWorkTipUnknownError) as excinfo:
        _refuse_on_tip(None, _context())

    assert excinfo.value.error_code == "LANE_WORK_TIP_UNKNOWN"
    assert "no lane work tip was ever recorded" in excinfo.value.next_step
    assert "recorder hook is not active" not in excinfo.value.next_step
    assert calls == [], "an unknown tip must refuse before absorption is evaluated"


def test_unmoved_tip_with_an_inactive_recorder_fails_closed_with_the_recorder_wording(monkeypatch: pytest.MonkeyPatch) -> None:
    asked = _recorder(monkeypatch, active=False)
    calls = _absorption(monkeypatch, result=True)

    with pytest.raises(LaneWorkTipUnknownError) as excinfo:
        _refuse_on_tip(_BASE, _context(_BASE))

    exc = excinfo.value
    assert exc.error_code == "LANE_WORK_TIP_UNKNOWN"
    assert "recorder hook is not active" in exc.next_step
    assert "git fsck --lost-found" in exc.next_step
    assert "spec-kitty context cleanup" in exc.next_step
    assert tip_ref(_BRANCH) in exc.next_step
    assert asked == [Path("repo")]
    assert calls == [], "an untrusted unmoved tip must not be classified as absorbed"


def test_unmoved_tip_with_an_active_recorder_falls_through_to_absorption(monkeypatch: pytest.MonkeyPatch) -> None:
    asked = _recorder(monkeypatch, active=True)
    calls = _absorption(monkeypatch, result=True)

    _refuse_on_tip(_BASE, _context(_BASE))

    assert asked == [Path("repo")]
    assert calls == [(_BASE, _TARGET, _BASE)]


def test_a_moved_tip_never_consults_the_recorder(monkeypatch: pytest.MonkeyPatch) -> None:
    asked = _recorder(monkeypatch, active=False)
    _absorption(monkeypatch, result=True)

    _refuse_on_tip(_TIP, _context(_BASE))

    assert asked == [], "the recorder probe only matters when tip == base"


def test_an_absorbed_tip_proceeds(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _absorption(monkeypatch, result=True)

    _refuse_on_tip(_TIP, _context(_BASE))

    assert calls == [(_TIP, _TARGET, _BASE)]


def test_an_unabsorbed_tip_refuses_naming_the_tip_and_both_remedies(monkeypatch: pytest.MonkeyPatch) -> None:
    _absorption(monkeypatch, result=False)

    with pytest.raises(DestroyedLaneError) as excinfo:
        _refuse_on_tip(_TIP, _context(_BASE))

    exc = excinfo.value
    assert exc.error_code == "DESTROYED_LANE"
    assert exc.tip_sha == _TIP
    assert tip_ref(_BRANCH) in exc.next_step
    assert "git branch" in exc.next_step
    assert "git update-ref -d" in exc.next_step


def test_unevaluable_absorption_fails_closed_as_destroyed(monkeypatch: pytest.MonkeyPatch) -> None:
    """git < 2.38 cannot run ``merge-tree --write-tree``: refuse, never treat "unsupported" as "absorbed"."""
    _absorption(monkeypatch, result=None)

    with pytest.raises(DestroyedLaneError) as excinfo:
        _refuse_on_tip(_TIP, _context(_BASE))

    assert excinfo.value.error_code == "DESTROYED_LANE"
    assert excinfo.value.tip_sha == _TIP
    assert tip_ref(_BRANCH) in excinfo.value.next_step


def test_a_deleted_context_evaluates_absorption_without_a_base(monkeypatch: pytest.MonkeyPatch) -> None:
    """FR-020: with no context there is no base leg -- never a spurious ``tip == base`` match."""
    asked = _recorder(monkeypatch, active=False)
    calls = _absorption(monkeypatch, result=False)

    with pytest.raises(DestroyedLaneError) as excinfo:
        _refuse_on_tip(_TIP, None)

    assert excinfo.value.tip_sha == _TIP
    assert calls == [(_TIP, _TARGET, None)]
    assert asked == []


def _guard(monkeypatch: pytest.MonkeyPatch, *, context: WorkspaceContext | None, tip: str | None) -> dict[str, list[Any]]:
    """Replace the guard's inputs; returns what each collaborator was asked."""
    seen: dict[str, list[Any]] = {"status": [], "tip_half": []}

    def _status(_repo_root: Path, _slug: str, wp_id: str) -> str:
        seen["status"].append(wp_id)
        return "in_progress"

    def _tip_half(_repo_root: Path, **kwargs: Any) -> None:
        seen["tip_half"].append(kwargs)

    monkeypatch.setattr("specify_cli.workspace.context.find_context_for_wp", lambda *_a, **_k: context)
    monkeypatch.setattr(allocator, "read_tip", lambda *_a, **_k: tip)
    monkeypatch.setattr(allocator, "_canonical_wp_lane_value", _status)
    monkeypatch.setattr(allocator, "_lane_base_reachable_from_target", lambda *_a, **_k: True)
    monkeypatch.setattr(allocator, "_refuse_on_tip", _tip_half)
    return seen


def _run_guard() -> None:
    allocator._refuse_if_lane_destroyed(Path("repo"), "seam", _WP, _LANE, _BRANCH, _TARGET)


def test_neither_context_nor_tip_proceeds_without_reading_status(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = _guard(monkeypatch, context=None, tip=None)

    _run_guard()

    assert seen == {"status": [], "tip_half": []}


def test_a_tip_without_a_context_still_reaches_the_tip_half(monkeypatch: pytest.MonkeyPatch) -> None:
    """FR-020: a deleted ``WorkspaceContext`` must never fail the guard open while a tip is recorded."""
    seen = _guard(monkeypatch, context=None, tip=_TIP)

    _run_guard()

    assert seen["status"] == [_WP]
    assert len(seen["tip_half"]) == 1
    assert seen["tip_half"][0]["tip"] == _TIP
    assert seen["tip_half"][0]["context"] is None


def test_a_context_with_a_reachable_base_still_reaches_the_tip_half(monkeypatch: pytest.MonkeyPatch) -> None:
    """#5115: base reachability alone no longer ends the guard on a LANES-topology mission."""
    context = _context(_BASE)
    seen = _guard(monkeypatch, context=context, tip=_TIP)

    _run_guard()

    assert len(seen["tip_half"]) == 1
    assert seen["tip_half"][0]["context"] is context
