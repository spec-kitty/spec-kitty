"""Producer conformance tests for canonical event emission.

Phase 2 of issues Priivacy-ai/spec-kitty#1198 / #1200.

For every SaaS-bound producer surface in the CLI (the lifecycle module's
``emit_*`` helpers), this test enumerates a minimal valid argument set,
captures the resulting payload, and asserts that the canonical
``spec_kitty_events.conformance.validate_event(..., strict=True)`` passes
with zero ``model_violations`` and zero ``schema_violations``.

(The former second section pinned the sync ``EventEmitter``'s ``emit_*``
methods; that producer died with the sync transport, issue #5. Epic E3's
runtime-moment producer, registered via
``runtime.next._internal_runtime.events.register_runtime_emitter_factory``
(#3929), rejoins this file in the second section below.)

The intent: bind every producer's payload shape to the canonical contract
so future drift is an emit-time error caught here in CI, not an RC-canary
failure days later. See start-here.md C-007 and
docs/architecture/spec-kitty-mission-workflow.md non-negotiables.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

pytestmark = pytest.mark.fast


# ---------------------------------------------------------------------------
# Lifecycle-module producers (specify_cli.status.lifecycle_events)
# ---------------------------------------------------------------------------


def _strict_validate(event_type: str, payload: dict[str, Any]) -> None:
    """Strict canonical validation; fails the test on any violation."""
    from spec_kitty_events.conformance import validate_event

    result = validate_event(payload, event_type, strict=True)
    assert not result.model_violations, f"{event_type}: model_violations={[(v.field, v.message) for v in result.model_violations]}"
    assert not result.schema_violations, f"{event_type}: schema_violations={[(v.json_path, v.message) for v in result.schema_violations]}"


def _strict_validate_saas_projection(event_type: str, payload: dict[str, Any]) -> None:
    from specify_cli.status.lifecycle_events import _canonical_lifecycle_payload_for_saas

    _strict_validate(event_type, _canonical_lifecycle_payload_for_saas(event_type, payload))


def test_emit_project_initialized_payload_passes_strict_validation(tmp_path: Path) -> None:
    from specify_cli.status.lifecycle_events import emit_project_initialized

    envelope = emit_project_initialized(
        tmp_path,
        project_uuid="00000000-0000-0000-0000-000000000001",
        project_slug="demo",
        actor="cli",
        runtime_version="3.2.0rc23",
    )
    assert envelope is not None
    _strict_validate("ProjectInitialized", envelope["payload"])


def test_emit_mission_created_local_payload_passes_strict_validation(tmp_path: Path) -> None:
    from specify_cli.status.lifecycle_events import emit_mission_created_local

    feature_dir = tmp_path / "kitty-specs" / "demo-mission"
    feature_dir.mkdir(parents=True)

    envelope = emit_mission_created_local(
        feature_dir,
        mission_slug="demo-mission",
        mission_id="01ULIDEXAMPLE0000000000000",
        mission_number=None,
        mission_type="software-dev",
        target_branch="main",
        wp_count=3,
        friendly_name="Demo Mission",
        purpose_tldr="A demo mission",
        purpose_context="Used for conformance test.",
    )
    assert envelope is not None
    _strict_validate("MissionCreated", envelope["payload"])


@pytest.mark.parametrize(
    "event_type",
    ["SpecifyStarted", "PlanStarted", "TasksStarted"],
)
def test_emit_artifact_phase_started_payload_passes_strict_validation(tmp_path: Path, event_type: str) -> None:
    from specify_cli.status.lifecycle_events import emit_artifact_phase

    feature_dir = tmp_path / "kitty-specs" / "demo-mission"
    feature_dir.mkdir(parents=True)

    envelope = emit_artifact_phase(
        feature_dir,
        event_type=event_type,
        mission_slug="demo-mission",
        mission_number=1,
        actor="cli",
    )
    assert envelope is not None
    _strict_validate_saas_projection(event_type, envelope["payload"])


def test_emit_artifact_phase_specify_completed_payload_passes_strict_validation(
    tmp_path: Path,
) -> None:
    from specify_cli.status.lifecycle_events import emit_artifact_phase

    feature_dir = tmp_path / "kitty-specs" / "demo-mission"
    feature_dir.mkdir(parents=True)

    envelope = emit_artifact_phase(
        feature_dir,
        event_type="SpecifyCompleted",
        mission_slug="demo-mission",
        actor="cli",
        artifact_path="kitty-specs/demo-mission/spec.md",
        summary="initial spec",
    )
    assert envelope is not None
    _strict_validate("SpecifyCompleted", envelope["payload"])


def test_emit_artifact_phase_plan_completed_payload_passes_strict_validation(
    tmp_path: Path,
) -> None:
    from specify_cli.status.lifecycle_events import emit_artifact_phase

    feature_dir = tmp_path / "kitty-specs" / "demo-mission"
    feature_dir.mkdir(parents=True)

    envelope = emit_artifact_phase(
        feature_dir,
        event_type="PlanCompleted",
        mission_slug="demo-mission",
        actor="cli",
        artifact_path="kitty-specs/demo-mission/plan.md",
    )
    assert envelope is not None
    _strict_validate("PlanCompleted", envelope["payload"])


def test_emit_artifact_phase_tasks_completed_payload_passes_strict_validation(
    tmp_path: Path,
) -> None:
    from specify_cli.status.lifecycle_events import emit_artifact_phase

    feature_dir = tmp_path / "kitty-specs" / "demo-mission"
    feature_dir.mkdir(parents=True)

    envelope = emit_artifact_phase(
        feature_dir,
        event_type="TasksCompleted",
        mission_slug="demo-mission",
        actor="cli",
        artifact_path="kitty-specs/demo-mission/tasks.md",
        wp_count=3,
        summary="3 WPs",
    )
    assert envelope is not None
    _strict_validate("TasksCompleted", envelope["payload"])


def test_emit_artifact_phase_started_keeps_local_artifact_path_but_saas_projection_is_strict(
    tmp_path: Path,
) -> None:
    """Started events keep local artifact metadata without leaking it to SaaS."""
    from specify_cli.status.lifecycle_events import emit_artifact_phase

    feature_dir = tmp_path / "kitty-specs" / "demo-mission"
    feature_dir.mkdir(parents=True)

    envelope = emit_artifact_phase(
        feature_dir,
        event_type="SpecifyStarted",
        mission_slug="demo-mission",
        actor="cli",
        artifact_path="kitty-specs/demo-mission/spec.md",
    )
    assert envelope is not None
    assert envelope["payload"]["artifact_path"] == "kitty-specs/demo-mission/spec.md"
    _strict_validate_saas_projection("SpecifyStarted", envelope["payload"])


def test_emit_wp_created_local_payload_passes_strict_validation(tmp_path: Path) -> None:
    from specify_cli.status.lifecycle_events import emit_wp_created_local

    feature_dir = tmp_path / "kitty-specs" / "demo-mission"
    feature_dir.mkdir(parents=True)

    envelope = emit_wp_created_local(
        feature_dir,
        mission_slug="demo-mission",
        wp_id="WP01",
        wp_title="Scaffold project",
        wp_path="kitty-specs/demo-mission/tasks/WP01.md",
        depends_on=[],
        actor="cli",
    )
    assert envelope is not None
    _strict_validate("WPCreated", envelope["payload"])


# ---------------------------------------------------------------------------
# Runtime-moment producer (specify_cli.events.runtime_moments, E3 #3929)
# ---------------------------------------------------------------------------

_RUNTIME_RUN_ID = "0123456789abcdef0123456789abcdef"
_RUNTIME_MISSION_ULID = "01KNRQK0R1ZDS8Z57M1TRXF0XR"
_RUNTIME_EMIT_METHOD = {
    "MissionRunStarted": "emit_mission_run_started",
    "NextStepIssued": "emit_next_step_issued",
    "NextStepAutoCompleted": "emit_next_step_auto_completed",
    "DecisionInputRequested": "emit_decision_input_requested",
    "DecisionInputAnswered": "emit_decision_input_answered",
    "MissionRunCompleted": "emit_mission_run_completed",
}


def _runtime_payload(event_type: str) -> Any:
    from spec_kitty_events.mission_next import (
        DecisionInputAnsweredPayload,
        DecisionInputRequestedPayload,
        MissionRunCompletedPayload,
        MissionRunStartedPayload,
        NextStepAutoCompletedPayload,
        NextStepIssuedPayload,
        RuntimeActorIdentity,
    )

    actor = RuntimeActorIdentity(actor_id="claude", actor_type="llm")
    run_id = _RUNTIME_RUN_ID
    return {
        "MissionRunStarted": lambda: MissionRunStartedPayload(run_id=run_id, mission_type="software-dev", actor=actor),
        "NextStepIssued": lambda: NextStepIssuedPayload(run_id=run_id, step_id="specify", agent_id="claude", actor=actor),
        "NextStepAutoCompleted": lambda: NextStepAutoCompletedPayload(run_id=run_id, step_id="specify", agent_id="claude", result="success", actor=actor),
        "DecisionInputRequested": lambda: DecisionInputRequestedPayload(
            run_id=run_id,
            decision_id="input:approval",
            step_id="collect_input",
            question="Proceed?",
            options=("yes", "no"),
            input_key="approval",
            actor=actor,
        ),
        "DecisionInputAnswered": lambda: DecisionInputAnsweredPayload(run_id=run_id, decision_id="input:approval", answer="yes", actor=actor),
        "MissionRunCompleted": lambda: MissionRunCompletedPayload(run_id=run_id, mission_type="software-dev", actor=actor),
    }[event_type]()


@pytest.mark.parametrize("event_type", sorted(_RUNTIME_EMIT_METHOD))
def test_runtime_moment_producer_payload_passes_strict_validation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, event_type: str) -> None:
    """The payload the E3 producer publishes (identity stamped) is canonical."""
    import json

    from specify_cli.events.runtime_moments import RuntimeMomentProducer

    feature_dir = tmp_path / "kitty-specs" / "demo-mission"
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(json.dumps({"mission_id": _RUNTIME_MISSION_ULID}), encoding="utf-8")
    run_dir = tmp_path / ".kittify" / "runtime" / "runs" / _RUNTIME_RUN_ID
    run_dir.mkdir(parents=True)
    payload = _runtime_payload(event_type)
    record = {"event_type": event_type, "timestamp": "2026-09-13T21:00:00+00:00", "payload": payload.model_dump(mode="json")}
    (run_dir / "run.events.jsonl").write_text(json.dumps(record, sort_keys=True) + "\n", encoding="utf-8")
    published: list[dict[str, Any]] = []
    monkeypatch.setattr("specify_cli.status.fire_lifecycle_saas_fanout", lambda **kwargs: published.append(kwargs))

    producer = RuntimeMomentProducer.for_mission(feature_dir=feature_dir, mission_slug="demo-mission", mission_type="software-dev")
    getattr(producer, _RUNTIME_EMIT_METHOD[event_type])(payload)

    assert len(published) == 1
    published_payload = published[0]["envelope"]["payload"]
    assert (published_payload["mission_slug"], published_payload["mission_id"]) == ("demo-mission", _RUNTIME_MISSION_ULID)
    _strict_validate(event_type, published_payload)
