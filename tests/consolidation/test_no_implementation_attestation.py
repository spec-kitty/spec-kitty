"""Unit tests for the operator no-implementation attestation (#6715, WP02).

``specify_cli.consolidation.no_implementation_attestation``: validation, the record shape, the
executor's recording before the claim, and the exclusions that keep the attestation from ever
reading as a review. The attestation lifts ``IMPLEMENTATION_MISSING`` for the named work package
only (``wp_evidence``); it is never the approving actor of the #5939 independence comparison,
never an approval stamp, and never feeds the hollow-review force count. The end-to-end CLI
replay lives in ``tests/integration/test_6715_no_implementation_attestation.py``.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import typer

from specify_cli.consolidation import no_implementation_attestation as nia
from specify_cli.consolidation.approved_bound import approval_stamp
from specify_cli.consolidation.canceled_attestation import ATTESTATION_KEY, AttestationError
from specify_cli.consolidation.preflight import _independent_reviewer_confirmed, _review_force_counts
from specify_cli.consolidation.wp_evidence import NO_IMPLEMENTATION, _no_implementation_attested_wp_ids
from specify_cli.lanes.models import LanesManifest
from specify_cli.lanes.persistence import read_lanes_json
from specify_cli.status import Lane, StatusEvent, TransitionRequest, read_events
from specify_cli.status.store import append_events_atomic
from tests.terminus.conftest import CoordMission
from tests.terminus.post_approval_support import build_post_approval_lanes_mission

_REASON = "docs-only: the deliverable already exists on main"


# ---------------------------------------------------------------------------
# validation and record shape (pure)
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.parametrize("reason", [None, "", "   "])
def test_a_request_without_a_reason_is_refused(reason: str | None) -> None:
    with pytest.raises(AttestationError, match=r"--attest-no-implementation requires --attest-reason"):
        nia._validate_no_implementation_request(["WP01"], reason, claim_lanes={"WP01": "approved"})


@pytest.mark.unit
def test_a_work_package_outside_the_approved_claim_is_refused() -> None:
    with pytest.raises(AttestationError, match=r"applies only to an approved work package; not approved: WP09\. Nothing was recorded\."):
        nia._validate_no_implementation_request(["WP01", "WP09"], _REASON, claim_lanes={"WP01": "approved"})


@pytest.mark.unit
def test_a_valid_request_is_de_duplicated_and_an_empty_one_is_nothing() -> None:
    assert nia._validate_no_implementation_request(["WP01", "WP02", "WP01"], _REASON, claim_lanes={"WP01": "approved", "WP02": "done"}) == ("WP01", "WP02")
    assert nia._validate_no_implementation_request([], None, claim_lanes={}) == ()


@pytest.mark.unit
@pytest.mark.parametrize("current_lane", ["approved", "done"])
def test_the_attestation_is_a_forced_operator_self_transition(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, current_lane: str) -> None:
    captured: list[TransitionRequest] = []
    monkeypatch.setattr("specify_cli.coordination.status_transition.emit_status_transition_transactional", captured.append)

    nia.record_no_implementation_attestation(
        repo_root=tmp_path,
        feature_dir=tmp_path / "kitty-specs" / "m",
        mission_slug="m",
        wp_id="WP02",
        current_lane=current_lane,
        reason=f"  {_REASON}  ",
        actor="stijn",
    )

    (request,) = captured
    assert request.to_lane == Lane(current_lane)
    assert request.force is True and request.actor == "stijn" and request.reason_source == "operator"
    assert request.reason == f"operator attests no implementation is owed: {_REASON}"
    assert request.policy_metadata == {ATTESTATION_KEY: NO_IMPLEMENTATION}
    assert request.evidence == {"review": {"reviewer": "stijn", "verdict": "approved", "reference": "operator-attestation:WP02"}}


@pytest.mark.unit
def test_the_metadata_predicate_reads_only_the_no_implementation_value() -> None:
    assert nia.is_no_implementation_attestation({ATTESTATION_KEY: NO_IMPLEMENTATION})
    assert not nia.is_no_implementation_attestation({ATTESTATION_KEY: "approved_reviewed"})
    assert not nia.is_no_implementation_attestation(None)
    assert not nia.is_no_implementation_attestation({})


@pytest.mark.unit
def test_the_cli_refuses_a_no_implementation_attestation_without_a_reason() -> None:
    from specify_cli.cli.commands.consolidate import _validated_no_implementation_attestation_flags

    with pytest.raises(typer.Exit) as exited:
        _validated_no_implementation_attestation_flags(["WP02"], "  ")

    assert exited.value.exit_code == 2
    assert _validated_no_implementation_attestation_flags(["WP02", "WP02", " "], "checked") == ("WP02",)
    assert _validated_no_implementation_attestation_flags(None, None) == ()


@pytest.mark.unit
def test_the_dry_run_names_the_unapplied_attestation() -> None:
    from specify_cli.cli.commands.consolidate import _dry_run_attestation_notices

    (notice,) = _dry_run_attestation_notices((), (), ("WP02",), json_output=False)
    assert notice.startswith("--attest-no-implementation is not applied with --dry-run: nothing is recorded")
    assert _dry_run_attestation_notices((), (), ("WP02",), json_output=True) == []


# ---------------------------------------------------------------------------
# a hand-written status log: the attestation is never the approving actor
# ---------------------------------------------------------------------------

_SLUG = "m-nia"


def _event(n: int, wp: str, from_lane: str, to_lane: str, actor: str, *, force: bool = False, metadata: dict[str, str] | None = None) -> StatusEvent:
    return StatusEvent(
        event_id=f"01J{n:023d}",
        mission_slug=_SLUG,
        wp_id=wp,
        from_lane=Lane(from_lane),
        to_lane=Lane(to_lane),
        at=f"2026-10-27T10:{n:02d}:00+00:00",
        actor=actor,
        force=force,
        execution_mode="worktree",
        reason="operator attests no implementation is owed: docs-only" if metadata else None,
        reason_source="operator" if metadata else None,
        policy_metadata=metadata,
    )


def _approved_log(feature_dir: Path, *, implementer: str, reviewer: str, attester: str) -> None:
    feature_dir.mkdir(parents=True, exist_ok=True)
    events = [
        _event(1, "WP02", "planned", "claimed", implementer),
        _event(2, "WP02", "claimed", "in_progress", implementer),
        _event(3, "WP02", "in_progress", "for_review", implementer),
        _event(4, "WP02", "for_review", "in_review", reviewer),
        _event(5, "WP02", "in_review", "approved", reviewer),
        _event(6, "WP02", "approved", "approved", attester, force=True, metadata={ATTESTATION_KEY: NO_IMPLEMENTATION}),
    ]
    append_events_atomic(feature_dir, events)


@pytest.mark.unit
def test_an_attestation_by_another_actor_does_not_make_a_self_approval_independent(tmp_path: Path) -> None:
    feature_dir = tmp_path / "self"
    _approved_log(feature_dir, implementer="claude", reviewer="claude", attester="stijn")

    assert _independent_reviewer_confirmed(feature_dir, "WP02") is False


@pytest.mark.unit
def test_an_attestation_by_the_implementer_does_not_unconfirm_an_independent_review(tmp_path: Path) -> None:
    feature_dir = tmp_path / "independent"
    _approved_log(feature_dir, implementer="claude", reviewer="bob", attester="claude")

    assert _independent_reviewer_confirmed(feature_dir, "WP02") is True
    assert _no_implementation_attested_wp_ids(read_events(feature_dir)) == {"WP02"}


@pytest.mark.unit
def test_the_attestation_does_not_feed_the_hollow_review_force_count(tmp_path: Path) -> None:
    feature_dir = tmp_path / "force"
    _approved_log(feature_dir, implementer="claude", reviewer="bob", attester="stijn")

    assert _review_force_counts(feature_dir, {"WP02"}) == {"WP02": 1}, "the forced attestation is discounted like a review claim"


@pytest.mark.unit
def test_the_lifted_notice_names_the_work_package_and_the_recorded_reason(tmp_path: Path) -> None:
    feature_dir = tmp_path / "notice"
    _approved_log(feature_dir, implementer="claude", reviewer="bob", attester="stijn")
    events = read_events(feature_dir)

    assert nia.lifted_notices(events, ["WP02"]) == ["⚠️  WP02: IMPLEMENTATION_MISSING lifted by operator attestation (docs-only)"]
    assert nia.lifted_notices(events, []) == []


@pytest.mark.unit
def test_the_reason_is_that_of_the_attestation_in_force_or_none(tmp_path: Path) -> None:
    """A voided attestation is never cited: the consolidate "lifted" notice names only the one in force."""
    feature_dir = tmp_path / "voided"
    _approved_log(feature_dir, implementer="claude", reviewer="bob", attester="stijn")
    assert nia._attested_reason(read_events(feature_dir), "WP02") == "docs-only"

    append_events_atomic(feature_dir, [_event(7, "WP02", "approved", "planned", "bob", force=True)])
    events = read_events(feature_dir)
    assert nia._attested_reason(events, "WP02") is None
    assert nia._attested_reason(events, "WP09") is None
    assert _no_implementation_attested_wp_ids(events) == frozenset()


# ---------------------------------------------------------------------------
# the planner and the executor's recording, over a real two-lane mission
# ---------------------------------------------------------------------------


def _manifest(mission: CoordMission) -> LanesManifest:
    manifest = read_lanes_json(mission.feature_dir)
    assert manifest is not None
    return manifest


def _attestation_events(mission: CoordMission) -> list[StatusEvent]:
    return [event for event in read_events(mission.feature_dir) if (event.policy_metadata or {}).get(ATTESTATION_KEY) == NO_IMPLEMENTATION]


@pytest.mark.integration
@pytest.mark.git_repo
def test_the_planner_maps_an_approved_work_package_to_its_lane_and_refuses_an_invalid_request(tmp_path: Path) -> None:
    mission = build_post_approval_lanes_mission(tmp_path)
    manifest = _manifest(mission)

    assert nia.plan_no_implementation_attestations(mission.feature_dir, manifest, ["WP01"], _REASON, repo_root=mission.repo, excluded_canceled_wp_ids=()) == {
        "WP01": "approved"
    }
    assert nia.plan_no_implementation_attestations(mission.feature_dir, manifest, [], None, repo_root=mission.repo, excluded_canceled_wp_ids=()) == {}
    with pytest.raises(AttestationError, match=r"not approved: WP01\. Nothing was recorded\."):
        nia.plan_no_implementation_attestations(mission.feature_dir, manifest, ["WP01"], _REASON, repo_root=mission.repo, excluded_canceled_wp_ids=("WP01",))


@pytest.mark.integration
@pytest.mark.git_repo
def test_the_executor_records_the_attestation_and_it_is_neither_a_stamp_nor_the_approver(tmp_path: Path) -> None:
    from specify_cli.consolidation import executor

    mission = build_post_approval_lanes_mission(tmp_path)
    stamp_before = approval_stamp(read_events(mission.feature_dir), "WP01")
    independent_before = _independent_reviewer_confirmed(mission.feature_dir, "WP01")
    assert stamp_before is not None, "fixture: WP01 carries a review approval stamp"

    recorded = executor._record_operator_attestations(
        mission.repo,
        mission.slug,
        wp_ids=(),
        reason=_REASON,
        acceptably_canceled=frozenset(),
        no_implementation_wp_ids=("WP01",),
        feature_dir=mission.feature_dir,
        lanes_manifest=_manifest(mission),
    )

    assert recorded == ("WP01",)
    (attestation,) = _attestation_events(mission)
    assert attestation.force is True and attestation.from_lane == attestation.to_lane == Lane.APPROVED
    assert attestation.reason_source == "operator" and attestation.actor not in ("", None)
    events = read_events(mission.feature_dir)
    assert approval_stamp(events, "WP01") == stamp_before, "the attestation never becomes the approval bound"
    assert _independent_reviewer_confirmed(mission.feature_dir, "WP01") is independent_before
    assert _no_implementation_attested_wp_ids(events) == {"WP01"}


@pytest.mark.integration
@pytest.mark.git_repo
def test_a_refused_request_records_nothing(tmp_path: Path) -> None:
    from specify_cli.consolidation import executor

    mission = build_post_approval_lanes_mission(tmp_path)
    log_before = read_events(mission.feature_dir)

    with pytest.raises(typer.Exit) as exited:
        executor._record_operator_attestations(
            mission.repo,
            mission.slug,
            wp_ids=(),
            reason=_REASON,
            acceptably_canceled=frozenset(),
            approved_wp_ids=(),
            no_implementation_wp_ids=("WP01", "WP09"),
            feature_dir=mission.feature_dir,
            lanes_manifest=_manifest(mission),
        )

    assert exited.value.exit_code == 1
    assert read_events(mission.feature_dir) == log_before
