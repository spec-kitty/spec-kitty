"""``orchestrator-api consolidate-mission`` refuses a lane holding a post-approval commit (#5668).

The orchestrator-api merges code lanes directly (``consolidate_lane_into_mission``,
then ``integrate_mission_into_target``) with no reconciliation claim and no gate, so it
landed a content commit made on a lane after review approved it. It must evaluate the
approved bound before its first lane merge and fail with the ``PREFLIGHT_FAILED``
envelope, carrying the refusal code machine-readably in ``data["preflight_error_code"]``,
with no branch moved. The same mission without the late commit still consolidates.

Driven through the REAL ``spec-kitty orchestrator-api`` CLI over real git.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from tests.terminus.conftest import CoordMission, blob_present_at, run_terminus
from tests.terminus.post_approval_support import (
    LATE_PATH,
    WP01_PATH,
    add_post_approval_commit,
    strip_approval_stamps,
    build_post_approval_coord_mission,
    build_post_approval_lanes_mission,
)
from tests.terminus.rollback_harness import flat, ref_shas

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_REFUSAL_CODE = "LANE_MOVED_AFTER_APPROVAL"
_TARGET = "develop"


def _consolidate_mission(mission: CoordMission) -> subprocess.CompletedProcess[str]:
    return run_terminus(mission, ["orchestrator-api", "consolidate-mission", "--mission", mission.slug, "--strategy", "squash"])


def _envelope(result: subprocess.CompletedProcess[str]) -> dict[str, object]:
    """The JSON envelope: the last non-empty stdout line (the success path's branch cleanup prints first)."""
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    assert lines, f"expected a JSON envelope on stdout. output={flat(result)}"
    envelope = json.loads(lines[-1])
    assert isinstance(envelope, dict)
    return envelope


def _build(tmp_path: Path, topology: str) -> CoordMission:
    if topology == "coord":
        return build_post_approval_coord_mission(tmp_path, target_branch=_TARGET)
    return build_post_approval_lanes_mission(tmp_path, target_branch=_TARGET)


@pytest.mark.parametrize("topology", ["lanes", "coord"])
def test_post_approval_commit_is_refused_before_any_lane_merges(tmp_path: Path, topology: str) -> None:
    mission = _build(tmp_path, topology)
    add_post_approval_commit(mission)
    before = ref_shas(mission)

    result = _consolidate_mission(mission)

    output = flat(result)
    assert result.returncode != 0, f"a post-approval commit must be refused. output={output}"
    envelope = _envelope(result)
    assert envelope["success"] is False, envelope
    data = envelope["data"]
    assert isinstance(data, dict)
    assert envelope["error_code"] == "PREFLIGHT_FAILED", envelope
    assert data["preflight_error_code"] == _REFUSAL_CODE, envelope
    assert ref_shas(mission) == before, f"no branch tip may move. output={output}"
    assert not blob_present_at(mission.repo, _TARGET, LATE_PATH), "the unreviewed file must not be on the target"
    assert not blob_present_at(mission.repo, mission.coord_branch, LATE_PATH), "the unreviewed file must not be on the mission branch"


def test_an_unstamped_approval_says_attestation_is_a_cli_only_step(tmp_path: Path) -> None:
    mission = _build(tmp_path, "lanes")
    strip_approval_stamps(mission, "WP01")

    result = _consolidate_mission(mission)

    envelope = _envelope(result)
    data = envelope["data"]
    assert isinstance(data, dict)
    assert result.returncode != 0 and data["preflight_error_code"] == "APPROVAL_STAMP_MISSING", envelope
    assert "consolidate-mission has no attestation flag: attestation is done with `spec-kitty consolidate` (CLI only)" in str(data["errors"])


@pytest.mark.parametrize("topology", ["lanes", "coord"])
def test_control_untouched_approved_mission_consolidates(tmp_path: Path, topology: str) -> None:
    mission = _build(tmp_path, topology)

    result = _consolidate_mission(mission)

    output = flat(result)
    assert result.returncode == 0, output
    assert _envelope(result)["success"] is True, output
    assert blob_present_at(mission.repo, _TARGET, WP01_PATH), output


def test_a_placement_failure_of_any_kind_falls_back_to_the_mission_branch_base(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The base resolution tolerates what the executor tolerates: an unresolvable placement (not only a git error) reads as "no coordination tip"."""
    import mission_runtime
    from specify_cli.lanes.persistence import read_lanes_json
    from specify_cli.orchestrator_api.consolidation import _approved_bound_claim_base

    mission = _build(tmp_path, "lanes")
    manifest = read_lanes_json(mission.feature_dir)
    assert manifest is not None

    def _boom(*_args: object, **_kwargs: object) -> object:
        raise ValueError("placement cannot be resolved")

    monkeypatch.setattr(mission_runtime, "resolve_placement_only", _boom)

    assert _approved_bound_claim_base(mission.repo, mission.slug, manifest) == ref_shas(mission)["coord"]


# ---------------------------------------------------------------------------
# in-process: the refusal helper and its text (the subprocess cells above collect no coverage)
# ---------------------------------------------------------------------------


def _refuse(mission: CoordMission) -> None:
    from specify_cli.lanes.persistence import read_lanes_json
    from specify_cli.orchestrator_api.consolidation import _refuse_post_approval_lane_content

    manifest = read_lanes_json(mission.feature_dir)
    assert manifest is not None
    _refuse_post_approval_lane_content(mission.repo, mission.feature_dir, mission.slug, manifest)


def test_the_refusal_helper_passes_an_untouched_mission_and_names_a_late_commit_with_its_code(tmp_path: Path) -> None:
    from specify_cli.orchestrator_api.consolidation import ApprovedBoundRefused

    mission = _build(tmp_path, "lanes")
    _refuse(mission)

    late = add_post_approval_commit(mission)
    with pytest.raises(ApprovedBoundRefused) as refused:
        _refuse(mission)

    assert refused.value.error_code == _REFUSAL_CODE
    assert str(refused.value).startswith(f"{_REFUSAL_CODE}: ") and late[:7] in str(refused.value)
    assert "no attestation flag" not in str(refused.value), "only an unstamped approval, which has a CLI attestation, carries the note"


def test_the_refusal_helper_adds_the_cli_only_sentence_for_an_unstamped_approval(tmp_path: Path) -> None:
    from specify_cli.orchestrator_api.consolidation import ApprovedBoundRefused

    mission = _build(tmp_path, "lanes")
    strip_approval_stamps(mission, "WP01")

    with pytest.raises(ApprovedBoundRefused) as refused:
        _refuse(mission)

    assert refused.value.error_code == "APPROVAL_STAMP_MISSING"
    assert str(refused.value).endswith(
        "consolidate-mission has no attestation flag: attestation is done with `spec-kitty consolidate` (CLI only), not with this command."
    )


@pytest.mark.parametrize(("text", "code"), [("LANE_MOVED_AFTER_APPROVAL: x", "LANE_MOVED_AFTER_APPROVAL"), ("SOMETHING_ELSE: x", None), ("no colon at all", None)])
@pytest.mark.unit
def test_the_refusal_code_is_the_leading_known_code_or_none(text: str, code: str | None) -> None:
    from specify_cli.orchestrator_api.consolidation import _bound_refusal_code

    assert _bound_refusal_code(text) == code


def test_an_unreadable_event_log_refuses_without_a_code_and_an_unreadable_snapshot_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Both stop the check from answering, so both refuse before any lane merges; only the first is a lane-check text (and carries no code)."""
    from specify_cli.orchestrator_api.consolidation import ApprovedBoundRefused
    from specify_cli.status import StoreError

    def _unreadable(*_args: object, **_kwargs: object) -> object:
        raise StoreError("status.events.jsonl is unreadable")

    mission = _build(tmp_path, "lanes")
    monkeypatch.setattr("specify_cli.status.read_events", _unreadable)
    with pytest.raises(ApprovedBoundRefused, match=r"the status event log could not be read") as refused:
        _refuse(mission)
    assert refused.value.error_code is None

    monkeypatch.setattr("specify_cli.status.materialize_snapshot", _unreadable)
    with pytest.raises(RuntimeError, match=r"could not be checked against what review approved \(.*unreadable.*\); no lane was merged\."):
        _refuse(mission)


def test_a_claim_base_that_does_not_resolve_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """No coordination tip and a mission branch that is gone: the base cannot be named, so the check raises instead of reading "nothing to refuse"."""
    from dataclasses import replace

    from specify_cli.consolidation.git_probes import GitProbeError
    from specify_cli.lanes.persistence import read_lanes_json
    from specify_cli.orchestrator_api import consolidation

    mission = _build(tmp_path, "lanes")
    manifest = read_lanes_json(mission.feature_dir)
    assert manifest is not None
    monkeypatch.setattr(consolidation, "_status_placement_tip", lambda *_args, **_kwargs: None)

    with pytest.raises(GitProbeError):
        consolidation._approved_bound_claim_base(mission.repo, mission.slug, replace(manifest, mission_branch="kitty/mission-no-such-branch"))
