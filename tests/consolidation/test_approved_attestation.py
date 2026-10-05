"""Unit tests for the operator attestation of an unstamped approval (#5668, plan D-5).

``specify_cli.consolidation.approved_attestation``: the validation branches and the
record shape that the end-to-end replays in
``tests/terminus/test_unstamped_approval_attestation.py`` do not reach (a work package
outside the approved claim, a work package already ``done``).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.consolidation import approved_attestation as aa
from specify_cli.consolidation.approved_bound import APPROVED_REVIEWED
from specify_cli.consolidation.canceled_attestation import ATTESTATION_KEY, AttestationError
from specify_cli.status import Lane, TransitionRequest

pytestmark = [pytest.mark.unit]


def test_a_work_package_outside_the_approved_claim_is_refused() -> None:
    with pytest.raises(AttestationError, match=r"applies only to an approved work package; not approved: WP09\. Nothing was recorded\."):
        aa.validate_approved_attestation_request(["WP01", "WP09"], "checked", events=[], claim_lanes={"WP01": "approved"})


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
