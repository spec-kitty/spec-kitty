"""Consolidation-written status events carry the structured system actor (#6722, FR-004..FR-006).

Four families, each asserted through the production function that builds the write:

* the merge-time approval replay and the done mark (``done_bookkeeping``);
* the done-write refusal probe (``preflight.refuse_protected_status_target``), which must
  build the *same* shape the real write will;
* the ``--skip-review-artifact-check`` override annotation, whose **event** actor becomes
  the system actor while its pinned ``ReviewOverride.actor`` slot stays a plain string;
* both operator attestations, which keep their identity in ``tool`` and their kind in
  ``policy_metadata`` — never in ``role``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest

from specify_cli.consolidation.done_bookkeeping import MERGE_ACTOR, _mark_wp_merged_done, _resolve_merge_actor
from specify_cli.consolidation.preflight import _record_review_artifact_skip_evidence
from specify_cli.status import InnerStateChanged, ReviewOverride, WPInnerStateDelta
from specify_cli.status._unsafe import append_annotations_atomic_verified
from specify_cli.status.actor import build_system_actor

pytestmark = pytest.mark.fast

_SYSTEM_MERGE_ACTOR = {"tool": "merge", "role": "system", "profile": None, "model": None}


def _write_minimal_meta(feature_dir: Path) -> None:
    (feature_dir / "meta.json").write_text(
        json.dumps({"mission_id": "01TEST00000000000000000000", "mission_slug": "021-test"}),
        encoding="utf-8",
    )


def _write_wp(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "---",
                'work_package_id: "WP01"',
                'title: "Test WP"',
                "dependencies: []",
                "subtasks: []",
                "---",
                "# WP01",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _seed_runtime(feature_dir: Path, *, review_actor: str = "reviewer-1") -> None:
    append_annotations_atomic_verified(
        feature_dir,
        [
            InnerStateChanged(
                event_id="01H11111111111111111111111",
                wp_id="WP01",
                at="2026-07-21T00:00:00+00:00",
                actor=review_actor,
                delta=WPInnerStateDelta(review=ReviewOverride(at="2026-07-21T00:00:00+00:00", actor=review_actor, wp_id="WP01", reason="approved")),
            )
        ],
    )


def _mission(tmp_path: Path) -> tuple[Path, Path]:
    repo_root = tmp_path
    feature_dir = repo_root / "kitty-specs" / "021-test"
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    _write_minimal_meta(feature_dir)
    _write_wp(tasks_dir / "WP01-test.md")
    return repo_root, feature_dir


# ---------------------------------------------------------------------------
# T001 — the done mark and the approval replay
# ---------------------------------------------------------------------------


def test_merge_identity_constant_is_the_string_the_readers_project() -> None:
    """The constant stays an identity string; only the emitted actor is structured."""
    assert MERGE_ACTOR == "merge"
    assert build_system_actor(MERGE_ACTOR) == _SYSTEM_MERGE_ACTOR


def test_done_mark_records_the_system_merge_actor(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo_root, feature_dir = _mission(tmp_path)
    _seed_runtime(feature_dir)

    emit_mock = Mock()
    monkeypatch.setattr("specify_cli.coordination.status_transition.emit_status_transition_transactional", emit_mock)
    monkeypatch.setattr("specify_cli.status.lane_reader.get_wp_lane", lambda *_a, **_kw: "approved")

    _mark_wp_merged_done(repo_root, "021-test", "WP01", "main")

    emit_mock.assert_called_once()
    request = emit_mock.call_args.args[0]
    assert request.actor == _SYSTEM_MERGE_ACTOR
    # Only the actor moved: the lane, the reason and the evidence are unchanged.
    assert request.to_lane == "done"
    assert request.reason == "Merged WP01 into main"
    assert request.evidence["review"]["reviewer"] == "reviewer-1"


# ---------------------------------------------------------------------------
# T002 — the refusal probe builds the same shape as the write
# ---------------------------------------------------------------------------


def test_done_refusal_probe_builds_the_system_merge_actor(tmp_path: Path) -> None:
    """The probe is a dry request; a guard that reads ``request.actor`` must see the write's value."""
    from specify_cli.consolidation import preflight as preflight_module
    from specify_cli.lanes.models import ExecutionLane, LanesManifest

    repo_root, feature_dir = _mission(tmp_path)
    _seed_runtime(feature_dir)
    manifest = LanesManifest(
        version=1,
        mission_slug="021-test",
        mission_id="01TEST00000000000000000000",
        mission_branch="kitty/mission-021-test",
        target_branch="main",
        lanes=[
            ExecutionLane(
                lane_id="lane-a",
                wp_ids=("WP01",),
                write_scope=("src/**",),
                predicted_surfaces=(),
                depends_on_lanes=(),
                parallel_group=0,
            )
        ],
        computed_at="2026-10-30T00:00:00+00:00",
        computed_from="test",
    )

    seen: list[Any] = []

    def _capture(request: Any) -> None:
        seen.append(request)
        return None

    monkeypatch_target = "specify_cli.coordination.status_transition.status_write_refusal"
    import specify_cli.coordination.status_transition as status_transition_module

    original = status_transition_module.status_write_refusal
    status_transition_module.status_write_refusal = _capture
    try:
        assert preflight_module.refuse_protected_status_target(repo_root, "021-test", manifest) is None
    finally:
        status_transition_module.status_write_refusal = original

    assert seen, "the probe must have built a request, or nothing is asserted"
    assert seen[0].actor == _SYSTEM_MERGE_ACTOR
    assert monkeypatch_target  # keeps the import used and names the seam under test


# ---------------------------------------------------------------------------
# T003 — the review-artifact override: structured event actor, plain-string slot
# ---------------------------------------------------------------------------


def test_skip_evidence_records_the_system_actor_and_keeps_the_override_slot(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.post_merge.review_artifact_consistency import ReviewArtifactFinding

    _, feature_dir = _mission(tmp_path)
    captured: list[dict[str, Any]] = []

    def _capture(*args: Any, **kwargs: Any) -> None:
        captured.append({"args": args, "kwargs": kwargs})
        return None

    monkeypatch.setattr("specify_cli.coordination.status_transition.emit_inner_state_changed_transactional", _capture)
    monkeypatch.setenv("SPEC_KITTY_AGENT", "operator-ivan")

    _record_review_artifact_skip_evidence(
        repo_root=tmp_path,
        feature_dir=feature_dir,
        mission_slug="021-test",
        findings=[ReviewArtifactFinding(wp_id="WP01", lane="approved", artifact_path=None, cycle_number=1, verdict="rejected")],
        note="content is the reviewed content",
    )

    assert len(captured) == 1
    call = captured[0]
    actor = call["kwargs"]["actor"]
    delta = call["args"][2]
    assert actor == {"tool": "operator-ivan", "role": "system", "profile": None, "model": None}
    # The pinned four-field slot keeps the plain operator identity.
    assert delta.review == ReviewOverride(at=delta.review.at, actor="operator-ivan", wp_id="WP01", reason="content is the reviewed content")
    assert isinstance(delta.review.actor, str)


def test_resolved_merge_actor_is_the_identity_the_system_actor_carries(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SPEC_KITTY_AGENT", "operator-ivan")
    identity = _resolve_merge_actor(tmp_path)
    assert identity == "operator-ivan"
    assert build_system_actor(identity)["tool"] == identity


# ---------------------------------------------------------------------------
# T004 — both attestations
# ---------------------------------------------------------------------------


def _attestation_fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Mock]:
    from specify_cli.status.emit import emit_status_transition

    feature_dir = tmp_path / "kitty-specs" / "021-test"
    feature_dir.mkdir(parents=True)
    _write_minimal_meta(feature_dir)

    emit_mock = Mock()
    monkeypatch.setattr("specify_cli.coordination.status_transition.emit_status_transition_transactional", emit_mock)
    assert callable(emit_status_transition)
    return feature_dir, emit_mock


def test_approved_attestation_records_the_system_actor(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.consolidation.approved_attestation import record_approved_reviewed_attestation
    from specify_cli.consolidation.canceled_attestation import ATTESTATION_KEY
    from specify_cli.consolidation.approved_bound import APPROVED_REVIEWED

    feature_dir, emit_mock = _attestation_fixture(tmp_path, monkeypatch)
    record_approved_reviewed_attestation(
        repo_root=tmp_path,
        feature_dir=feature_dir,
        mission_slug="021-test",
        wp_id="WP01",
        current_lane="approved",
        reason="the lane content is the reviewed content",
        actor="operator-ivan",
    )

    emit_mock.assert_called_once()
    request = emit_mock.call_args.args[0]
    assert request.actor == {"tool": "operator-ivan", "role": "system", "profile": None, "model": None}
    assert request.policy_metadata[ATTESTATION_KEY] == APPROVED_REVIEWED


def test_canceled_attestation_records_the_system_actor(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.consolidation.canceled_attestation import ATTESTATION_KEY, CANCELED_SUPERSEDED, record_canceled_superseded_attestation

    feature_dir, emit_mock = _attestation_fixture(tmp_path, monkeypatch)
    record_canceled_superseded_attestation(
        repo_root=tmp_path,
        feature_dir=feature_dir,
        mission_slug="021-test",
        wp_id="WP01",
        reason="content is absent or superseded",
        actor="operator-ivan",
    )

    emit_mock.assert_called_once()
    request = emit_mock.call_args.args[0]
    assert request.actor == {"tool": "operator-ivan", "role": "system", "profile": None, "model": None}
    assert request.policy_metadata[ATTESTATION_KEY] == CANCELED_SUPERSEDED


def test_attestation_is_still_recognised_by_its_kind_not_its_role(tmp_path: Path) -> None:
    """The reviewer read skips an attestation on ``policy_metadata``; ``role: system`` must not change that."""
    from specify_cli.consolidation.approved_bound import APPROVED_REVIEWED
    from specify_cli.consolidation.canceled_attestation import ATTESTATION_KEY
    from specify_cli.consolidation.preflight import _is_operator_attestation

    assert _is_operator_attestation({ATTESTATION_KEY: APPROVED_REVIEWED}) is True
    # A system actor with no attestation kind is not an attestation.
    assert _is_operator_attestation({"lane_head": "abc"}) is False
    assert _is_operator_attestation(None) is False
