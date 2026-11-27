"""#7860 review 5 issue 2: a planning lane that credits nothing is named in the refusal.

Before a default Mission lands, the claim credits its planning lane's work on the Mission branch
only when every planning work package is approved (ruling R1), its ``owned_files`` are readable
and narrow, and each window start is proven (ruling R2). Otherwise the lane credits nothing and
the gate reports the content as un-attributable, which alone names neither the planning lane nor
the work package. :func:`planning_lane_notes` says which lane, why, which work packages, and the
remedy; the verifier prints it with an un-attributable FAIL. No verdict changes.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import pytest

from specify_cli.consolidation import planning_lane_scope
from specify_cli.consolidation import reconciliation_authorship as authorship
from specify_cli.consolidation.reconciliation import ApprovedWpCommitSet
from specify_cli.consolidation.reconciliation_verifier import Divergence, VerifyResult, _with_attribution_hint
from specify_cli.lanes.compute import PLANNING_LANE_ID
from specify_cli.lanes.models import ExecutionLane, LanesManifest

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_SLUG = "notes-01M8FFFF"
_PLANNING = ExecutionLane(PLANNING_LANE_ID, ("WP02", "WP03"), ("curation/pkg/**",), (), (), 0)
_CODE = ExecutionLane("lane-a", ("WP01",), ("src/m1/**",), (), (), 0)
_APPROVED = {"WP01": {"lane": "approved"}, "WP02": {"lane": "approved"}, "WP03": {"lane": "done"}}
_OWNED = {"WP02": ("curation/pkg/**",), "WP03": ("docs/notes/x.md",)}


def _manifest() -> LanesManifest:
    return LanesManifest(
        version=1,
        mission_slug=_SLUG,
        mission_id=None,
        mission_branch=f"kitty/mission-{_SLUG}",
        target_branch="main",
        lanes=[_CODE, _PLANNING],
        computed_at="2026-11-27T00:00:00+00:00",
        computed_from="test",
        planning_artifact_wps=["WP02", "WP03"],
        planning_commit_sha="pin0000",
    )


def _events() -> list[object]:
    return []


@pytest.fixture
def shape(monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    """The Mission-branch window applies; ownership and window starts read from ``knobs`` (patched on the authorship module)."""
    knobs: dict[str, object] = {"window": ("pin0000", "coord0000"), "owned": dict(_OWNED), "unproven": set(), "scope": None}

    monkeypatch.setattr(authorship, "_planning_lane_mission_branch_window", lambda *_args: knobs["window"])

    def _ownership(_root: Path, _slug: str, wp_ids: tuple[str, ...]) -> dict[str, tuple[str, ...]]:
        owned = knobs["owned"]
        assert isinstance(owned, dict)
        return {wp: owned[wp] for wp in wp_ids if wp in owned}

    def _starts(_root: Path, _manifest: LanesManifest, _lane: ExecutionLane, wp_ids: tuple[str, ...], events: object) -> dict[str, str] | None:
        assert events is _events
        unproven = knobs["unproven"]
        assert isinstance(unproven, set)
        return None if any(wp in unproven for wp in wp_ids) else dict.fromkeys(wp_ids, "claim0")

    monkeypatch.setattr(authorship, "_planning_ownership", _ownership)
    monkeypatch.setattr(authorship, "_planning_window_starts", _starts)
    monkeypatch.setattr(authorship, "_planning_scope", lambda *_args: knobs["scope"])
    return knobs


def _notes(work_packages: Mapping[str, Mapping[str, object]] = _APPROVED, sb_window: tuple[str, str] | None = None) -> tuple[str, ...]:
    return planning_lane_scope.planning_lane_notes(Path(), _manifest(), work_packages, "coord0000", sb_window, _events)


def test_a_credited_lane_gets_no_note(shape: dict[str, object]) -> None:
    shape["scope"] = authorship._PlanningScope(((("curation/pkg/**",), frozenset({"c1"})),))

    assert _notes() == ()


def test_another_shape_gets_no_note(shape: dict[str, object]) -> None:
    assert _notes(sb_window=("sb0", "sb1")) == ()
    shape["window"] = None
    assert _notes() == ()


_NOT_APPROVED_ROWS = [({"lane": "canceled"}, "WP03 is canceled"), ({"lane": "in_progress"}, "WP03 is in_progress"), (None, "WP03 is no status row")]


@pytest.mark.parametrize(("row", "shown"), _NOT_APPROVED_ROWS)
def test_a_non_approved_work_package_is_named_with_the_r1_remedy(shape: dict[str, object], row: dict[str, object] | None, shown: str) -> None:
    states: dict[str, dict[str, object]] = {"WP01": {"lane": "approved"}, "WP02": {"lane": "approved"}}
    if row is not None:
        states["WP03"] = row

    (note,) = _notes(states)

    assert note.startswith(f"The planning lane {PLANNING_LANE_ID} credits none of its work on the Mission branch")
    assert shown in note and "WP02" not in note.split(":", 1)[1].split(".", 1)[0]
    assert "no attestation lifts this" in note
    assert "spec-kitty agent tasks move-task <WP> --to approved --force" in note
    assert "spec-kitty consolidate --attest-no-implementation <WP>" in note
    assert "spec-kitty agent tasks move-task <WP> --to claimed --force" in note
    assert "spec-kitty agent action implement <WP>" in note


def test_an_unreadable_ownership_is_named(shape: dict[str, object]) -> None:
    shape["owned"] = {"WP02": _OWNED["WP02"]}

    (note,) = _notes()

    assert "the owned_files of WP03 cannot be read" in note


def test_a_too_broad_pattern_is_named(shape: dict[str, object]) -> None:
    shape["owned"] = {"WP02": ("src/**",), "WP03": _OWNED["WP03"]}

    (note,) = _notes()

    assert "too broad (WP02 'src/**')" in note and "two literal path segments" in note


def test_an_unproven_window_start_is_named_with_the_implement_remedy(shape: dict[str, object]) -> None:
    shape["unproven"] = {"WP03"}

    (note,) = _notes()

    assert "the claim of WP03 on the Mission branch cannot be proven" in note
    assert "spec-kitty agent action implement" in note


def test_all_empty_ownership_is_named(shape: dict[str, object]) -> None:
    shape["owned"] = {"WP02": (), "WP03": ()}
    shape["scope"] = authorship._PlanningScope((((), frozenset()), ((), frozenset())))

    (note,) = _notes()

    assert "every planning work package's owned_files list is empty" in note


def test_an_unreadable_window_is_the_remaining_reason(shape: dict[str, object]) -> None:
    (note,) = _notes()

    assert "the commits of a work package's window on the Mission branch cannot be read" in note


# ---------------------------------------------------------------- rendering


_NOTE = "The planning lane lane-planning credits none of its work on the Mission branch to any work package (#7860): WP03 is canceled. Remedy."


def _claim(notes: tuple[str, ...] = (), refs: tuple[str, ...] = ()) -> ApprovedWpCommitSet:
    return ApprovedWpCommitSet(enforce_closed_world=True, planning_lane_notes=notes, external_dependency_refs=refs)


def test_an_un_attributable_fail_names_the_planning_lane_before_the_dependency_hint() -> None:
    result = _with_attribution_hint(VerifyResult.failed(Divergence(unattributable_blobs=(("curation/x.py", "b" * 40),))), _claim((_NOTE,)))

    text = result.recovery_guidance()

    assert _NOTE in text and "--dependency-ref" in text
    assert text.index(_NOTE) < text.index("--dependency-ref")
    assert result.status.name == "FAIL"


def test_a_declared_dependency_keeps_the_planning_note() -> None:
    claim = _claim((_NOTE,), ("dep",))

    text = _with_attribution_hint(VerifyResult.failed(Divergence(unattributable_deletions=("curation/x.py",))), claim).recovery_guidance()

    assert _NOTE in text and "--dependency-ref" not in text


def test_the_note_rides_only_on_an_un_attributable_fail() -> None:
    claim = _claim((_NOTE,))
    missing = VerifyResult.failed(Divergence(missing_approved=(("WP01", "a" * 40),)))

    assert _NOTE not in _with_attribution_hint(missing, claim).recovery_guidance()
    assert _NOTE not in _with_attribution_hint(VerifyResult.refused("unreadable"), claim).recovery_guidance()
    assert _with_attribution_hint(VerifyResult.passed(), claim).is_pass


def test_no_note_keeps_the_hint_unchanged() -> None:
    failed = VerifyResult.failed(Divergence(unattributable_content=(("c" * 40, "p" * 40),)))

    assert _with_attribution_hint(failed, _claim()).attribution_hint == _with_attribution_hint(failed, ApprovedWpCommitSet()).attribution_hint
