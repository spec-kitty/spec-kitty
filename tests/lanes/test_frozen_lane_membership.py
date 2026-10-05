"""Frozen lane membership for started work packages (#5573, WP02 T005/T006).

A work package that has started (its status history left ``planned`` for real
work) owns commits on its recorded lane's branch. ``compute_lanes`` must keep
it on that lane id on every re-finalize, keep its started lane-mates together,
never re-mint a lane id that held started work, and refuse the unsatisfiable
cases with one typed error (``LANE_MEMBERSHIP_FROZEN``).
"""

from __future__ import annotations

from collections.abc import Iterable

import pytest

from mission_runtime import MissionTopology

from specify_cli.lanes.compute import (
    PLANNING_LANE_ID,
    LaneComputationError,
    LaneMembershipFrozenError,
    compute_lanes,
    lane_created_branch,
)
from specify_cli.lanes.frozen_membership import (
    FrozenLaneMembership,
    MembershipConflict,
    MembershipConflictReason,
    assert_frozen_membership_honoured,
    build_frozen_membership,
    remedy_for,
    started_wp_ids,
)
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.ownership.models import OwnershipManifest, WorkProductKind
from specify_cli.status import Lane, StatusEvent

pytestmark = pytest.mark.fast

_SLUG = "frozen-test"


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _manifest(owned_files: list[str]) -> OwnershipManifest:
    return OwnershipManifest(
        execution_mode=WorkProductKind("code_change"),
        owned_files=tuple(owned_files),
        authoritative_surface=owned_files[0] if owned_files else "",
    )


def _planning_manifest(owned_files: list[str]) -> OwnershipManifest:
    return OwnershipManifest(
        execution_mode=WorkProductKind.PLANNING_ARTIFACT,
        owned_files=tuple(owned_files),
        authoritative_surface=owned_files[0] if owned_files else "",
    )


def _lane(lane_id: str, *wp_ids: str) -> ExecutionLane:
    return ExecutionLane(
        lane_id=lane_id,
        wp_ids=tuple(wp_ids),
        write_scope=(),
        predicted_surfaces=(),
        depends_on_lanes=(),
        parallel_group=0,
    )


def _lanes_manifest(*lanes: ExecutionLane) -> LanesManifest:
    return LanesManifest(
        version=1,
        mission_slug=_SLUG,
        mission_id=None,
        mission_branch=f"kitty/mission-{_SLUG}",
        target_branch="main",
        lanes=list(lanes),
        computed_at="2026-10-04T00:00:00+00:00",
        computed_from="dependency_graph+ownership",
    )


def _events(wp_id: str, *lanes: str) -> list[StatusEvent]:
    """Build a linear status history ``lanes[0] -> lanes[1] -> ...`` for *wp_id*."""
    history: list[StatusEvent] = []
    for index, (from_lane, to_lane) in enumerate(zip(lanes, lanes[1:], strict=False)):
        history.append(
            StatusEvent(
                event_id=f"01EVENT{wp_id}{index:04d}",
                mission_slug=_SLUG,
                wp_id=wp_id,
                from_lane=Lane(from_lane),
                to_lane=Lane(to_lane),
                at=f"2026-10-04T00:00:{index:02d}+00:00",
                actor="tester",
                force=False,
                execution_mode="worktree",
            )
        )
    return history


def _frozen(bindings: dict[str, str], retired: Iterable[str] = ()) -> FrozenLaneMembership:
    return FrozenLaneMembership(bindings=bindings, retired_wp_ids=frozenset(retired))


def _lane_of(manifest: LanesManifest) -> dict[str, str]:
    return {wp: lane.lane_id for lane in manifest.lanes for wp in lane.wp_ids}


def _comparable(manifest: LanesManifest) -> dict[str, object]:
    data = manifest.to_dict()
    data.pop("computed_at", None)
    return data


# ---------------------------------------------------------------------------
# T005: started_wp_ids — history-based, positive started set (FR-008)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("history", "expected"),
    [
        pytest.param(["planned", "claimed"], {"WP01"}, id="claimed"),
        pytest.param(["planned", "blocked"], set(), id="blocked-from-planned-not-started"),
        pytest.param(["planned", "canceled"], set(), id="canceled-from-planned-not-started"),
        pytest.param(["planned", "claimed", "in_progress", "planned"], {"WP01"}, id="reset-to-planned-stays-started"),
        pytest.param(["planned", "in_progress"], {"WP01"}, id="forced-planned-to-in-progress"),
        pytest.param(["planned", "blocked", "in_progress"], {"WP01"}, id="blocked-then-in-progress"),
        pytest.param(["approved", "done"], {"WP01"}, id="done"),
        pytest.param(["genesis", "planned"], set(), id="genesis-seed-not-started"),
        pytest.param([], set(), id="no-events"),
    ],
)
def test_started_wp_ids_table(history: list[str], expected: set[str]) -> None:
    events = _events("WP01", *history) if history else []
    assert started_wp_ids(events) == frozenset(expected)


_WORK_LANES = {Lane.CLAIMED, Lane.IN_PROGRESS, Lane.FOR_REVIEW, Lane.IN_REVIEW, Lane.APPROVED, Lane.DONE}


@pytest.mark.parametrize("lane", list(Lane), ids=lambda lane: str(lane))
def test_started_set_is_exactly_the_work_lanes(lane: Lane) -> None:
    """Every Lane member is classified; a new lane is not-started until named."""
    event = StatusEvent(
        event_id="01EVENTSINGLE",
        mission_slug=_SLUG,
        wp_id="WP01",
        from_lane=Lane.PLANNED,
        to_lane=lane,
        at="2026-10-04T00:00:00+00:00",
        actor="tester",
        force=True,
        execution_mode="worktree",
    )
    assert started_wp_ids([event]) == (frozenset({"WP01"}) if lane in _WORK_LANES else frozenset())


def test_started_wp_ids_cancel_after_work_stays_started() -> None:
    events = _events("WP01", "planned", "claimed", "in_progress", "canceled")
    events += _events("WP02", "planned", "canceled")
    assert started_wp_ids(events) == frozenset({"WP01"})


def test_started_wp_ids_ignores_uninitialized_sentinel() -> None:
    events = _events("WP01", "genesis", "uninitialized")
    assert started_wp_ids(events) == frozenset()


# ---------------------------------------------------------------------------
# T005: FrozenLaneMembership value object
# ---------------------------------------------------------------------------


def test_empty_membership() -> None:
    empty = FrozenLaneMembership.empty()
    assert empty.is_empty
    assert dict(empty.bindings) == {}
    assert empty.retired_wp_ids == frozenset()
    assert empty.reserved_lane_ids == frozenset()


def test_membership_is_immutable_and_hashable() -> None:
    source = {"WP01": "lane-a"}
    frozen = _frozen(source, retired={"WP09"})
    source["WP02"] = "lane-b"  # mutating the caller's dict must not leak in
    assert dict(frozen.bindings) == {"WP01": "lane-a"}
    with pytest.raises(TypeError):
        frozen.bindings["WP03"] = "lane-c"  # type: ignore[index]  # proving read-only at runtime
    assert hash(frozen) == hash(_frozen({"WP01": "lane-a"}, retired={"WP09"}))
    assert frozen == _frozen({"WP01": "lane-a"}, retired={"WP09"})
    assert not frozen.is_empty
    assert frozen.reserved_lane_ids == frozenset({"lane-a"})


def test_retired_only_membership_is_not_empty() -> None:
    assert not _frozen({}, retired={"WP01"}).is_empty


# ---------------------------------------------------------------------------
# T005: build_frozen_membership
# ---------------------------------------------------------------------------


def _build(
    previous: LanesManifest | None,
    *,
    started: Iterable[str] = (),
    tipped: Iterable[str] = (),
    present: Iterable[str] = (),
    eligible: Iterable[str] = (),
) -> FrozenLaneMembership:
    return build_frozen_membership(
        previous,
        started=frozenset(started),
        tipped_branches=frozenset(tipped),
        present_wp_ids=frozenset(present),
        eligible_wp_ids=frozenset(eligible),
    )


def test_build_without_previous_manifest_is_empty() -> None:
    assert _build(None, started={"WP01"}, present={"WP01"}, eligible={"WP01"}).is_empty


def test_build_binds_history_started_members_only() -> None:
    previous = _lanes_manifest(_lane("lane-a", "WP01", "WP02"), _lane("lane-b", "WP03"))
    frozen = _build(previous, started={"WP02", "WP03"}, present={"WP01", "WP02", "WP03"}, eligible={"WP01", "WP02", "WP03"})
    assert dict(frozen.bindings) == {"WP02": "lane-a", "WP03": "lane-b"}
    assert frozen.retired_wp_ids == frozenset()


def test_build_binds_started_planning_lane_members() -> None:
    previous = _lanes_manifest(_lane("lane-a", "WP01"), _lane(PLANNING_LANE_ID, "WP02"))
    frozen = _build(previous, started={"WP02"}, present={"WP01", "WP02"}, eligible={"WP01", "WP02"})
    assert dict(frozen.bindings) == {"WP02": PLANNING_LANE_ID}


def test_build_tip_fallback_freezes_every_member_of_an_unstarted_tipped_lane() -> None:
    previous = _lanes_manifest(_lane("lane-a", "WP01", "WP02"), _lane("lane-b", "WP03"))
    tipped = {lane_created_branch(previous, "lane-a")}
    frozen = _build(previous, tipped=tipped, present={"WP01", "WP02", "WP03"}, eligible={"WP01", "WP02", "WP03"})
    assert dict(frozen.bindings) == {"WP01": "lane-a", "WP02": "lane-a"}


def test_build_tip_fallback_ignored_when_lane_has_a_history_started_member() -> None:
    previous = _lanes_manifest(_lane("lane-a", "WP01", "WP02"))
    tipped = {lane_created_branch(previous, "lane-a")}
    frozen = _build(previous, started={"WP02"}, tipped=tipped, present={"WP01", "WP02"}, eligible={"WP01", "WP02"})
    assert dict(frozen.bindings) == {"WP02": "lane-a"}


def test_build_never_tip_freezes_the_planning_lane() -> None:
    previous = _lanes_manifest(_lane(PLANNING_LANE_ID, "WP01"))
    # The planning lane resolves to the target branch; even a tip recorded
    # under that name must not freeze planning-artifact WPs.
    tipped = {lane_created_branch(previous, PLANNING_LANE_ID), "main"}
    frozen = _build(previous, tipped=tipped, present={"WP01"}, eligible={"WP01"})
    assert frozen.is_empty


def test_build_retired_is_present_minus_eligible() -> None:
    previous = _lanes_manifest(_lane("lane-a", "WP01"), _lane("lane-b", "WP02"))
    frozen = _build(previous, started={"WP01"}, present={"WP01", "WP02", "WP03"}, eligible={"WP02", "WP03"})
    assert frozen.retired_wp_ids == frozenset({"WP01"})
    assert dict(frozen.bindings) == {"WP01": "lane-a"}
    assert frozen.reserved_lane_ids == frozenset({"lane-a"})


# ---------------------------------------------------------------------------
# T005: MembershipConflict / remedies
# ---------------------------------------------------------------------------


def test_conflict_to_dict_shape() -> None:
    conflict = MembershipConflict(
        reason="started_lanes_collapsed",
        wp_ids=("WP01", "WP02"),
        recorded_lanes=("lane-a", "lane-b"),
        remedy=remedy_for("started_lanes_collapsed", ("WP01", "WP02")),
    )
    assert conflict.to_dict() == {
        "reason": "started_lanes_collapsed",
        "wp_ids": ["WP01", "WP02"],
        "recorded_lanes": ["lane-a", "lane-b"],
        "remedy": conflict.remedy,
    }


@pytest.mark.parametrize(
    ("reason", "must_mention"),
    [
        ("started_lanes_collapsed", "Remove the overlap that forces WP01 and WP02 into one lane"),
        ("started_wp_removed", "spec-kitty agent tasks move-task WP01 --to canceled"),
        ("started_wp_kind_changed", "execution_mode"),
        ("status_unreadable", "spec-kitty agent status validate"),
    ],
)
def test_remedy_for_names_the_work_packages_and_is_non_destructive(reason: str, must_mention: str) -> None:
    wp_ids = ("WP01", "WP02") if reason == "started_lanes_collapsed" else ("WP01",)
    remedy = remedy_for(reason, wp_ids)  # type: ignore[arg-type]  # parametrized literal
    assert must_mention in remedy
    assert "finalize-tasks" in remedy
    for forbidden in ("lanes.json", "--force", "git reset", "git restore", "git checkout", "worktree remove", "branch -D"):
        assert forbidden not in remedy


# ---------------------------------------------------------------------------
# T006: LaneMembershipFrozenError
# ---------------------------------------------------------------------------


def _conflict(reason: MembershipConflictReason, wp_ids: tuple[str, ...], lanes: tuple[str, ...]) -> MembershipConflict:
    return MembershipConflict(reason=reason, wp_ids=wp_ids, recorded_lanes=lanes, remedy=remedy_for(reason, wp_ids))


def test_error_reason_and_next_step_follow_precedence() -> None:
    kind = _conflict("started_wp_kind_changed", ("WP03",), ("lane-c",))
    collapsed = _conflict("started_lanes_collapsed", ("WP01", "WP02"), ("lane-a", "lane-b"))
    removed = _conflict("started_wp_removed", ("WP04",), ("lane-d",))
    error = LaneMembershipFrozenError((kind, collapsed, removed))
    assert isinstance(error, LaneComputationError)
    assert error.error_code == "LANE_MEMBERSHIP_FROZEN"
    assert error.reason == "started_lanes_collapsed"
    assert error.conflicts == (kind, collapsed, removed)
    assert error.next_step.split("\n") == [collapsed.remedy, removed.remedy, kind.remedy]
    message = str(error)
    assert message.startswith("Cannot re-finalize: started work packages would change lane. ")
    assert "WP01 (lane-a) and WP02 (lane-b) would be merged into one lane" in message
    assert "WP04 (lane-d)" in message
    assert "WP03 (lane-c)" in message


def test_error_dedupes_identical_remedies() -> None:
    first = _conflict("started_wp_removed", ("WP01",), ("lane-a",))
    error = LaneMembershipFrozenError((first, first))
    assert error.next_step == first.remedy


def test_error_requires_conflicts() -> None:
    with pytest.raises(ValueError, match="at least one conflict"):
        LaneMembershipFrozenError(())


# ---------------------------------------------------------------------------
# T006: compute_lanes(frozen=...) honours started membership
# ---------------------------------------------------------------------------


def _two_lane_prior() -> tuple[dict[str, list[str]], dict[str, OwnershipManifest], LanesManifest]:
    graph: dict[str, list[str]] = {"WP01": [], "WP02": []}
    manifests = {"WP01": _manifest(["a.py"]), "WP02": _manifest(["b.py"])}
    prior = compute_lanes(graph, manifests, _SLUG)
    assert _lane_of(prior) == {"WP01": "lane-a", "WP02": "lane-b"}
    return graph, manifests, prior


def test_issue_5573_tie_keeps_the_started_wp_lane() -> None:
    """WP01 now also owns b.py; WP02 is started on lane-b -> one lane, lane-b."""
    graph, manifests, prior = _two_lane_prior()
    manifests["WP01"] = _manifest(["a.py", "b.py"])
    result = compute_lanes(graph, manifests, _SLUG, previous_lanes=prior, frozen=_frozen({"WP02": "lane-b"}))
    assert _lane_of(result) == {"WP01": "lane-b", "WP02": "lane-b"}
    assert len(result.lanes) == 1


def test_issue_5573_tie_unfrozen_takes_the_lowest_lane_id() -> None:
    """Characterisation of the unchanged default tie-break (the #5573 trigger)."""
    graph, manifests, prior = _two_lane_prior()
    manifests["WP01"] = _manifest(["a.py", "b.py"])
    result = compute_lanes(graph, manifests, _SLUG, previous_lanes=prior)
    assert _lane_of(result) == {"WP01": "lane-a", "WP02": "lane-a"}


def test_issue_5573_mirror_keeps_lane_a() -> None:
    graph, manifests, prior = _two_lane_prior()
    manifests["WP01"] = _manifest(["a.py", "b.py"])
    result = compute_lanes(graph, manifests, _SLUG, previous_lanes=prior, frozen=_frozen({"WP01": "lane-a"}))
    assert _lane_of(result) == {"WP01": "lane-a", "WP02": "lane-a"}


def test_greedy_group_order_cannot_steal_a_started_lane_id() -> None:
    """H2: the earlier group (WP01, WP02) would read back lane-b, stranding started WP03."""
    graph: dict[str, list[str]] = {"WP01": [], "WP02": [], "WP03": []}
    manifests = {"WP01": _manifest(["x.py"]), "WP02": _manifest(["x.py"]), "WP03": _manifest(["c.py"])}
    prior = _lanes_manifest(_lane("lane-a", "WP09"), _lane("lane-b", "WP02", "WP03"))
    unfrozen = compute_lanes(graph, manifests, _SLUG, previous_lanes=prior)
    assert _lane_of(unfrozen) == {"WP01": "lane-b", "WP02": "lane-b", "WP03": "lane-a"}  # the old steal
    result = compute_lanes(graph, manifests, _SLUG, previous_lanes=prior, frozen=_frozen({"WP03": "lane-b"}))
    assert _lane_of(result) == {"WP01": "lane-a", "WP02": "lane-a", "WP03": "lane-b"}


def test_planned_lane_mate_split_out_of_a_started_lane_gets_an_unreserved_id() -> None:
    """US3 AS2: WP02 (planned) leaves started WP01's lane-a -> fresh id, never reserved."""
    graph: dict[str, list[str]] = {"WP01": [], "WP02": [], "WP03": []}
    manifests = {"WP01": _manifest(["a.py"]), "WP02": _manifest(["b.py"]), "WP03": _manifest(["c.py"])}
    prior = _lanes_manifest(_lane("lane-a", "WP01", "WP02"), _lane("lane-b", "WP03"), _lane("lane-c", "WP09"))
    frozen = _frozen({"WP01": "lane-a", "WP09": "lane-c"}, retired={"WP09"})
    result = compute_lanes(graph, manifests, _SLUG, previous_lanes=prior, frozen=frozen)
    lane_of = _lane_of(result)
    assert lane_of["WP01"] == "lane-a"
    assert lane_of["WP03"] == "lane-b"
    assert lane_of["WP02"] not in frozen.reserved_lane_ids
    assert lane_of["WP02"] not in {"lane-a", "lane-b"}
    assert lane_of["WP02"] == "lane-d"


def test_retired_started_lane_id_is_never_minted_for_a_new_group() -> None:
    """The orphaned lane-a (its started WP01 was canceled) is not re-minted (H3)."""
    graph: dict[str, list[str]] = {"WP02": [], "WP05": []}
    manifests = {"WP02": _manifest(["b.py"]), "WP05": _manifest(["new.py"])}
    prior = _lanes_manifest(_lane("lane-a", "WP01"), _lane("lane-b", "WP02"))
    unfrozen = compute_lanes(graph, manifests, _SLUG, previous_lanes=prior)
    assert _lane_of(unfrozen)["WP05"] == "lane-a"  # sanity: the old algorithm re-mints lane-a
    frozen = _frozen({"WP01": "lane-a"}, retired={"WP01"})
    result = compute_lanes(graph, manifests, _SLUG, previous_lanes=prior, frozen=frozen)
    assert _lane_of(result) == {"WP02": "lane-b", "WP05": "lane-c"}


def test_started_lane_mates_stay_together_after_their_overlap_is_removed() -> None:
    graph: dict[str, list[str]] = {"WP01": [], "WP02": []}
    manifests = {"WP01": _manifest(["a.py"]), "WP02": _manifest(["b.py"])}
    prior = _lanes_manifest(_lane("lane-a", "WP01", "WP02"))
    unfrozen = compute_lanes(graph, manifests, _SLUG, previous_lanes=prior)
    assert len(unfrozen.lanes) == 2  # sanity: without frozen input they split
    result = compute_lanes(graph, manifests, _SLUG, previous_lanes=prior, frozen=_frozen({"WP01": "lane-a", "WP02": "lane-a"}))
    assert _lane_of(result) == {"WP01": "lane-a", "WP02": "lane-a"}
    assert result.collapse_report is not None
    rules = [event.rule for event in result.collapse_report.events]
    assert rules == ["frozen_lane_membership"]
    assert result.collapse_report.events[0].evidence == "both started on lane-a"


def test_frozen_union_runs_after_overlap_rules_so_overlap_evidence_is_kept() -> None:
    graph: dict[str, list[str]] = {"WP01": [], "WP02": []}
    manifests = {"WP01": _manifest(["a.py"]), "WP02": _manifest(["a.py"])}
    prior = _lanes_manifest(_lane("lane-a", "WP01", "WP02"))
    result = compute_lanes(graph, manifests, _SLUG, previous_lanes=prior, frozen=_frozen({"WP01": "lane-a", "WP02": "lane-a"}))
    assert result.collapse_report is not None
    assert [event.rule for event in result.collapse_report.events] == ["write_scope_overlap"]


def test_frozen_membership_unions_are_not_counted_as_independent_collapses() -> None:
    """Pinned choice: a frozen-membership union records history, not a new planning signal."""
    graph: dict[str, list[str]] = {"WP01": [], "WP02": []}
    manifests = {"WP01": _manifest(["a.py"]), "WP02": _manifest(["b.py"])}
    prior = _lanes_manifest(_lane("lane-a", "WP01", "WP02"))
    result = compute_lanes(graph, manifests, _SLUG, previous_lanes=prior, frozen=_frozen({"WP01": "lane-a", "WP02": "lane-a"}))
    assert result.collapse_report is not None
    assert result.collapse_report.independent_wps_collapsed == 0


def test_two_pins_in_one_group_refuse_with_started_lanes_collapsed() -> None:
    graph, manifests, prior = _two_lane_prior()
    manifests["WP01"] = _manifest(["a.py", "b.py"])
    with pytest.raises(LaneMembershipFrozenError) as excinfo:
        compute_lanes(graph, manifests, _SLUG, previous_lanes=prior, frozen=_frozen({"WP01": "lane-a", "WP02": "lane-b"}))
    error = excinfo.value
    assert error.error_code == "LANE_MEMBERSHIP_FROZEN"
    assert error.reason == "started_lanes_collapsed"
    assert len(error.conflicts) == 1
    conflict = error.conflicts[0]
    assert conflict.wp_ids == ("WP01", "WP02")
    assert conflict.recorded_lanes == ("lane-a", "lane-b")
    assert "WP01 (lane-a) and WP02 (lane-b) would be merged into one lane" in str(error)


def test_removed_started_wp_refuses() -> None:
    graph, manifests, prior = _two_lane_prior()
    graph.pop("WP02")
    manifests.pop("WP02")
    with pytest.raises(LaneMembershipFrozenError) as excinfo:
        compute_lanes(graph, manifests, _SLUG, previous_lanes=prior, frozen=_frozen({"WP02": "lane-b"}))
    assert excinfo.value.reason == "started_wp_removed"
    assert excinfo.value.conflicts[0].wp_ids == ("WP02",)
    assert excinfo.value.conflicts[0].recorded_lanes == ("lane-b",)


def test_removed_but_retired_started_wp_is_allowed_and_its_id_stays_reserved() -> None:
    graph, manifests, prior = _two_lane_prior()
    graph.pop("WP02")
    manifests.pop("WP02")
    graph["WP03"] = []
    manifests["WP03"] = _manifest(["c.py"])
    result = compute_lanes(graph, manifests, _SLUG, previous_lanes=prior, frozen=_frozen({"WP02": "lane-b"}, retired={"WP02"}))
    assert _lane_of(result) == {"WP01": "lane-a", "WP03": "lane-c"}


def test_every_code_wp_removed_while_started_refuses_on_the_planning_only_path() -> None:
    graph: dict[str, list[str]] = {"WP01": [], "WP02": []}
    manifests = {"WP01": _manifest(["a.py"]), "WP02": _planning_manifest(["kitty-specs/x/plan.md"])}
    prior = compute_lanes(graph, manifests, _SLUG)
    graph.pop("WP01")
    manifests.pop("WP01")
    with pytest.raises(LaneMembershipFrozenError) as excinfo:
        compute_lanes(graph, manifests, _SLUG, previous_lanes=prior, frozen=_frozen({"WP01": "lane-a"}))
    assert excinfo.value.reason == "started_wp_removed"


def test_every_wp_removed_while_started_refuses_on_the_empty_graph_path() -> None:
    graph: dict[str, list[str]] = {"WP01": []}
    manifests = {"WP01": _manifest(["a.py"])}
    prior = compute_lanes(graph, manifests, _SLUG)
    with pytest.raises(LaneMembershipFrozenError) as excinfo:
        compute_lanes({}, {}, _SLUG, previous_lanes=prior, frozen=_frozen({"WP01": "lane-a"}))
    assert excinfo.value.reason == "started_wp_removed"


def test_started_code_wp_now_planning_artifact_refuses_on_the_planning_only_path() -> None:
    graph: dict[str, list[str]] = {"WP01": [], "WP02": []}
    manifests = {"WP01": _manifest(["a.py"]), "WP02": _planning_manifest(["kitty-specs/x/plan.md"])}
    prior = compute_lanes(graph, manifests, _SLUG)
    manifests["WP01"] = _planning_manifest(["kitty-specs/x/notes.md"])
    with pytest.raises(LaneMembershipFrozenError) as excinfo:
        compute_lanes(graph, manifests, _SLUG, previous_lanes=prior, frozen=_frozen({"WP01": "lane-a"}))
    assert excinfo.value.reason == "started_wp_kind_changed"
    assert excinfo.value.conflicts[0].recorded_lanes == ("lane-a",)


def test_started_planning_wp_now_code_refuses_with_kind_changed() -> None:
    graph: dict[str, list[str]] = {"WP01": [], "WP02": []}
    manifests = {"WP01": _manifest(["a.py"]), "WP02": _planning_manifest(["kitty-specs/x/plan.md"])}
    prior = compute_lanes(graph, manifests, _SLUG)
    manifests["WP02"] = _manifest(["b.py"])
    with pytest.raises(LaneMembershipFrozenError) as excinfo:
        compute_lanes(graph, manifests, _SLUG, previous_lanes=prior, frozen=_frozen({"WP02": PLANNING_LANE_ID}))
    assert excinfo.value.reason == "started_wp_kind_changed"
    assert excinfo.value.conflicts[0].recorded_lanes == (PLANNING_LANE_ID,)


def test_started_planning_wp_staying_planning_is_honoured() -> None:
    graph: dict[str, list[str]] = {"WP01": [], "WP02": []}
    manifests = {"WP01": _manifest(["a.py"]), "WP02": _planning_manifest(["kitty-specs/x/plan.md"])}
    prior = compute_lanes(graph, manifests, _SLUG)
    result = compute_lanes(graph, manifests, _SLUG, previous_lanes=prior, frozen=_frozen({"WP01": "lane-a", "WP02": PLANNING_LANE_ID}))
    assert _lane_of(result) == {"WP01": "lane-a", "WP02": PLANNING_LANE_ID}


def test_all_conflicts_are_collected_into_one_error() -> None:
    graph: dict[str, list[str]] = {"WP01": [], "WP02": [], "WP04": []}
    manifests = {"WP01": _manifest(["a.py", "b.py"]), "WP02": _manifest(["b.py"]), "WP04": _planning_manifest(["kitty-specs/x/n.md"])}
    prior = _lanes_manifest(_lane("lane-a", "WP01"), _lane("lane-b", "WP02"), _lane("lane-c", "WP03"), _lane("lane-d", "WP04"))
    frozen = _frozen({"WP01": "lane-a", "WP02": "lane-b", "WP03": "lane-c", "WP04": "lane-d"})
    with pytest.raises(LaneMembershipFrozenError) as excinfo:
        compute_lanes(graph, manifests, _SLUG, previous_lanes=prior, frozen=frozen)
    reasons = sorted(conflict.reason for conflict in excinfo.value.conflicts)
    assert reasons == ["started_lanes_collapsed", "started_wp_kind_changed", "started_wp_removed"]
    assert excinfo.value.reason == "started_lanes_collapsed"


def test_none_empty_and_absent_frozen_give_identical_output() -> None:
    graph: dict[str, list[str]] = {"WP01": [], "WP02": [], "WP03": ["WP01"]}
    manifests = {"WP01": _manifest(["a.py", "b.py"]), "WP02": _manifest(["b.py"]), "WP03": _manifest(["c.py"])}
    prior = _lanes_manifest(_lane("lane-a", "WP01"), _lane("lane-b", "WP02"), _lane("lane-c", "WP03"))
    absent = compute_lanes(graph, manifests, _SLUG, previous_lanes=prior)
    none = compute_lanes(graph, manifests, _SLUG, previous_lanes=prior, frozen=None)
    empty = compute_lanes(graph, manifests, _SLUG, previous_lanes=prior, frozen=FrozenLaneMembership.empty())
    assert _comparable(absent) == _comparable(none) == _comparable(empty)


def test_single_branch_ignores_frozen() -> None:
    graph: dict[str, list[str]] = {"WP01": []}
    manifests = {"WP01": _manifest(["a.py"])}
    prior = _lanes_manifest(_lane("lane-a", "WP01"))
    frozen = _frozen({"WP01": "lane-a", "WP02": "lane-b"})
    result = compute_lanes(graph, manifests, _SLUG, previous_lanes=prior, topology=MissionTopology.SINGLE_BRANCH, frozen=frozen)
    baseline = compute_lanes(graph, manifests, _SLUG, previous_lanes=prior, topology=MissionTopology.SINGLE_BRANCH)
    assert _comparable(result) == _comparable(baseline)
    assert _lane_of(result) == {"WP01": PLANNING_LANE_ID}


def test_single_branch_empty_graph_ignores_frozen() -> None:
    prior = _lanes_manifest(_lane(PLANNING_LANE_ID, "WP01"))
    result = compute_lanes({}, {}, _SLUG, previous_lanes=prior, topology=MissionTopology.SINGLE_BRANCH, frozen=_frozen({"WP01": PLANNING_LANE_ID}))
    assert result.lanes == []


# ---------------------------------------------------------------------------
# T005: assert_frozen_membership_honoured (writer defence in depth)
# ---------------------------------------------------------------------------


def test_assert_honoured_passes_for_none_empty_and_matching() -> None:
    manifest = _lanes_manifest(_lane("lane-a", "WP01"), _lane("lane-b", "WP02"))
    assert_frozen_membership_honoured(manifest, None)
    assert_frozen_membership_honoured(manifest, FrozenLaneMembership.empty())
    assert_frozen_membership_honoured(manifest, _frozen({"WP01": "lane-a", "WP09": "lane-z"}))


def test_assert_honoured_raises_when_a_binding_is_violated() -> None:
    manifest = _lanes_manifest(_lane("lane-a", "WP01", "WP02"))
    with pytest.raises(LaneMembershipFrozenError) as excinfo:
        assert_frozen_membership_honoured(manifest, _frozen({"WP02": "lane-b"}))
    assert excinfo.value.reason == "started_lanes_collapsed"
    conflict = excinfo.value.conflicts[0]
    assert conflict.wp_ids == ("WP02",)
    assert conflict.recorded_lanes == ("lane-b",)


def test_assert_honoured_ignores_single_branch_manifests() -> None:
    manifest = _lanes_manifest(_lane(PLANNING_LANE_ID, "WP01"))
    assert_frozen_membership_honoured(manifest, _frozen({"WP01": "lane-a"}), topology=MissionTopology.SINGLE_BRANCH)
