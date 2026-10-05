"""Unit tests for the operator attestation of an unstamped approval (#5668, plan D-5).

``specify_cli.consolidation.approved_attestation``: the validation branches and the
record shape, in-process (the end-to-end replays in
``tests/terminus/test_unstamped_approval_attestation.py`` run the CLI as a subprocess and
collect no coverage), plus the executor's recording of the requests before the claim.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
import typer

from specify_cli.consolidation import approved_attestation as aa
from specify_cli.consolidation.approved_bound import APPROVED_REVIEWED
from specify_cli.consolidation.canceled_attestation import ATTESTATION_KEY, AttestationError
from specify_cli.consolidation.git_probes import GitProbeError
from specify_cli.lanes.models import LanesManifest
from specify_cli.lanes.persistence import read_lanes_json
from specify_cli.status import Lane, StatusEvent, StoreError, TransitionRequest, read_events
from tests.terminus.conftest import CoordMission, git_rev
from tests.terminus.post_approval_support import add_post_approval_commit, build_post_approval_lanes_mission, strip_approval_stamps

_REASON = "read every line of lane-a"


@pytest.mark.unit
def test_a_work_package_outside_the_approved_claim_is_refused() -> None:
    with pytest.raises(AttestationError, match=r"applies only to an approved work package; not approved: WP09\. Nothing was recorded\."):
        aa.validate_approved_attestation_request(["WP01", "WP09"], "checked", events=[], claim_lanes={"WP01": "approved"})


@pytest.mark.unit
def test_a_done_work_package_is_attested_with_a_forced_done_self_transition(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[TransitionRequest] = []

    def _fake_emit(request: TransitionRequest) -> None:
        captured.append(request)

    monkeypatch.setattr("specify_cli.coordination.status_transition.emit_status_transition_transactional", _fake_emit)
    aa.record_approved_reviewed_attestation(
        repo_root=tmp_path,
        feature_dir=tmp_path / "kitty-specs" / "m",
        mission_slug="m",
        wp_id="WP01",
        current_lane="done",
        reason="  read the whole lane  ",
        actor="stijn",
    )

    (request,) = captured
    assert request.to_lane == Lane.DONE
    assert request.force is True and request.actor == "stijn" and request.reason_source == "operator"
    assert request.reason == "operator attests approved content reviewed: read the whole lane"
    assert request.policy_metadata == {ATTESTATION_KEY: APPROVED_REVIEWED}
    assert request.evidence == {"review": {"reviewer": "stijn", "verdict": "approved", "reference": "operator-attestation:WP01"}}


# ---------------------------------------------------------------------------
# the planner and the executor's recording, over a real two-lane mission
# ---------------------------------------------------------------------------


def _manifest(mission: CoordMission) -> LanesManifest:
    manifest = read_lanes_json(mission.feature_dir)
    assert manifest is not None
    return manifest


def _plan(mission: CoordMission, wp_ids: list[str], reason: str | None = _REASON) -> dict[str, str]:
    plan: dict[str, str] = aa.plan_approved_attestations(mission.repo, mission.feature_dir, _manifest(mission), wp_ids, reason, excluded_canceled_wp_ids=())
    return plan


def _record(mission: CoordMission, wp_id: str = "WP01") -> None:
    aa.record_approved_reviewed_attestation(
        repo_root=mission.repo, feature_dir=mission.feature_dir, mission_slug=mission.slug, wp_id=wp_id, current_lane="approved", reason=_REASON, actor="stijn"
    )


def _attestation_events(mission: CoordMission) -> list[StatusEvent]:
    return [event for event in read_events(mission.feature_dir) if (event.policy_metadata or {}).get(ATTESTATION_KEY) == APPROVED_REVIEWED]


@pytest.fixture(scope="module")
def unstamped_mission(tmp_path_factory: pytest.TempPathFactory) -> Iterator[CoordMission]:
    """WP01 is a legacy approval (no lane head); WP02 keeps its stamped review approval. Read-only: tests must not record."""
    mission = build_post_approval_lanes_mission(tmp_path_factory.mktemp("unstamped"))
    strip_approval_stamps(mission, "WP01")
    yield mission


@pytest.mark.parametrize(
    ("wp_ids", "reason", "message"),
    [
        pytest.param(["WP01"], "   ", r"requires --attest-reason", id="blank-reason"),
        pytest.param(["WP01", "WP09"], _REASON, r"not approved: WP09\. Nothing was recorded\.", id="not-in-the-claim"),
        pytest.param(["WP02"], _REASON, r"WP02 already has one\. Move it back for review instead\. Nothing was recorded\.", id="stamped-review-approval"),
    ],
)
@pytest.mark.integration
@pytest.mark.git_repo
def test_the_planner_refuses_an_invalid_request(unstamped_mission: CoordMission, wp_ids: list[str], reason: str, message: str) -> None:
    with pytest.raises(AttestationError, match=message):
        _plan(unstamped_mission, wp_ids, reason)


@pytest.mark.integration
@pytest.mark.git_repo
def test_the_planner_maps_an_unstamped_approval_to_its_current_lane_and_an_empty_request_to_nothing(unstamped_mission: CoordMission) -> None:
    assert _plan(unstamped_mission, ["WP01"]) == {"WP01": "approved"}
    assert _plan(unstamped_mission, []) == {}


@pytest.mark.integration
@pytest.mark.git_repo
def test_the_planner_refuses_when_the_status_log_cannot_be_read(unstamped_mission: CoordMission, monkeypatch: pytest.MonkeyPatch) -> None:
    def _unreadable(*_args: object, **_kwargs: object) -> object:
        raise StoreError("status.events.jsonl is unreadable")

    monkeypatch.setattr(aa, "read_events", _unreadable)

    with pytest.raises(AttestationError, match=r"could not read the status log: .*unreadable\. Nothing was recorded\."):
        _plan(unstamped_mission, ["WP01"])


@pytest.mark.integration
@pytest.mark.git_repo
def test_an_earlier_attestation_is_accepted_again_while_the_lane_is_unmoved_and_refused_once_it_moved(tmp_path: Path) -> None:
    mission = build_post_approval_lanes_mission(tmp_path)
    strip_approval_stamps(mission, "WP01")
    _record(mission)
    assert len(_attestation_events(mission)) == 1

    assert _plan(mission, ["WP01"]) == {"WP01": "approved"}, "an unmoved lane may be attested again"

    add_post_approval_commit(mission)
    with pytest.raises(AttestationError) as refused:
        _plan(mission, ["WP01"])
    text = str(refused.value)
    assert "cannot be repeated for WP01: lane lane-a" in text and f"move-task WP01 --to in_progress --mission {mission.slug}" in text
    assert len(_attestation_events(mission)) == 1, "a refused repeat records nothing"


@pytest.mark.integration
@pytest.mark.git_repo
def test_the_planner_refuses_when_a_lane_cannot_be_read_to_check_the_earlier_attestation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mission = build_post_approval_lanes_mission(tmp_path)
    strip_approval_stamps(mission, "WP01")
    _record(mission)

    def _unreadable(*_args: object, **_kwargs: object) -> object:
        raise GitProbeError("lane tip does not resolve")

    monkeypatch.setattr(aa, "check_lane", _unreadable)

    expected = r"could not read lane lane-a to check the earlier attestation of WP01: lane tip does not resolve\. Nothing was recorded\."
    with pytest.raises(AttestationError, match=expected):
        _plan(mission, ["WP01"])


@pytest.mark.integration
@pytest.mark.git_repo
def test_the_executor_records_an_approved_attestation_and_the_lane_head_becomes_the_bound(tmp_path: Path) -> None:
    from specify_cli.consolidation import executor

    mission = build_post_approval_lanes_mission(tmp_path)
    strip_approval_stamps(mission, "WP01")
    lane_tip = git_rev(mission.repo, mission.lane_branches["WP01"])

    recorded = executor._record_operator_attestations(
        mission.repo,
        mission.slug,
        wp_ids=(),
        reason=_REASON,
        acceptably_canceled=frozenset(),
        approved_wp_ids=("WP01",),
        feature_dir=mission.feature_dir,
        lanes_manifest=_manifest(mission),
    )

    assert recorded == ("WP01",)
    (attestation,) = _attestation_events(mission)
    assert attestation.force is True and (attestation.policy_metadata or {}).get("lane_head") == lane_tip
    assert executor._record_operator_attestations(mission.repo, mission.slug, wp_ids=(), reason=None, acceptably_canceled=frozenset()) == ()


@pytest.mark.parametrize(
    ("canceled", "approved"),
    [pytest.param((), ("WP01", "WP09"), id="approved-request-invalid"), pytest.param(("WP02",), ("WP01",), id="canceled-request-invalid")],
)
@pytest.mark.integration
@pytest.mark.git_repo
def test_a_refused_attestation_request_records_nothing_for_either_flag(tmp_path: Path, canceled: tuple[str, ...], approved: tuple[str, ...]) -> None:
    from specify_cli.consolidation import executor

    mission = build_post_approval_lanes_mission(tmp_path)
    strip_approval_stamps(mission, "WP01")
    log_before = read_events(mission.feature_dir)

    with pytest.raises(typer.Exit) as exited:
        executor._record_operator_attestations(
            mission.repo,
            mission.slug,
            wp_ids=canceled,
            reason=_REASON,
            acceptably_canceled=frozenset(),
            approved_wp_ids=approved,
            feature_dir=mission.feature_dir,
            lanes_manifest=_manifest(mission),
        )

    assert exited.value.exit_code == 1
    assert read_events(mission.feature_dir) == log_before


@pytest.mark.unit
def test_the_cli_refuses_an_approved_attestation_without_a_reason() -> None:
    from specify_cli.cli.commands.consolidate import _validated_approved_attestation_flags

    with pytest.raises(typer.Exit) as exited:
        _validated_approved_attestation_flags(["WP01"], "  ")

    assert exited.value.exit_code == 2
    assert _validated_approved_attestation_flags(["WP01", "WP01", " "], "checked") == ("WP01",)
    assert _validated_approved_attestation_flags(None, None) == ()
