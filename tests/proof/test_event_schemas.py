from __future__ import annotations

import pytest

from pydantic import ValidationError

from specify_cli.proof.events import (
    MAX_PROOF_PAYLOAD_BYTES,
    PROOF_EVENT_TYPES,
    PROOF_EVENT_REQUIRED_FIELDS,
    build_proof_payload,
    proof_idempotency_key,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def _base_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "subject": {
            "subject_type": "work_package",
            "subject_id": "WP04",
            "mission_id": "01JTJ8M3Z3ZV4A6J3B1Q4JQ8RM",
            "mission_slug": "1223-cli-evidence-event-schema",
            "wp_id": "WP04",
        },
        "source": "pytest",
        "actor": {
            "actor_id": "codex",
            "actor_type": "llm",
            "display_name": "Codex",
        },
        "confidence": 0.93,
        "occurred_at": "2026-06-09T12:00:00+00:00",
        "observed_at": "2026-06-09T12:00:05+00:00",
        "artifact_refs": [
            {
                "kind": "junit",
                "uri": "artifacts/test-results.xml",
                "sha256": "a" * 64,
                "size_bytes": 512,
            }
        ],
        "summary": {"status": "passed", "tests": 12},
    }
    payload.update(overrides)
    return payload


def test_every_proof_event_type_has_a_payload_model() -> None:
    assert frozenset(
        {
            "ProofItemRecorded",
            "ReviewProofRecorded",
            "TestEvidenceCaptured",
            "BenchmarkEvidenceAttached",
            "SecurityScanCompleted",
            "PullRequestLineageRecorded",
            "HumanApprovalRecorded",
        }
    ) == PROOF_EVENT_TYPES
    assert set(PROOF_EVENT_REQUIRED_FIELDS) == set(PROOF_EVENT_TYPES)


def test_all_proof_payload_models_emit_required_fields() -> None:
    event_payloads = {
        "ProofItemRecorded": _base_payload(proof_kind="artifact"),
        "ReviewProofRecorded": _base_payload(review_kind="code_review", verdict="approved"),
        "TestEvidenceCaptured": _base_payload(
            test_command="pytest",
            exit_code=0,
            status="passed",
        ),
        "BenchmarkEvidenceAttached": _base_payload(benchmark_name="cold-start"),
        "SecurityScanCompleted": _base_payload(
            scanner="bandit",
            status="passed",
            findings_summary={"critical": 0, "high": 0},
        ),
        "PullRequestLineageRecorded": _base_payload(
            provider="github",
            repository="Priivacy-ai/spec-kitty",
            pull_request_url="https://github.com/Priivacy-ai/spec-kitty/pull/1",
        ),
        "HumanApprovalRecorded": _base_payload(
            approver="lynn",
            approval_status="approved",
        ),
    }

    for event_type, payload in event_payloads.items():
        serialized = build_proof_payload(event_type, payload)
        missing = PROOF_EVENT_REQUIRED_FIELDS[event_type] - set(serialized)
        assert not missing, f"{event_type} missing {missing}"
        subject = payload["subject"]
        assert serialized["mission_id"] == subject["mission_id"]
        assert serialized["mission_slug"] == subject["mission_slug"]
        assert serialized["wp_id"] == subject["wp_id"]


def test_build_test_evidence_payload_serializes_required_contract_fields() -> None:
    payload = build_proof_payload(
        "TestEvidenceCaptured",
        _base_payload(
            test_command="pytest tests/sync/test_events.py",
            exit_code=0,
            status="passed",
            runner="pytest",
            total_tests=12,
            failed_tests=0,
        ),
    )

    assert payload["proof_schema_version"] == "1.0.0"
    assert payload["subject"]["wp_id"] == "WP04"
    assert payload["mission_id"] == "01JTJ8M3Z3ZV4A6J3B1Q4JQ8RM"
    assert payload["mission_slug"] == "1223-cli-evidence-event-schema"
    assert payload["wp_id"] == "WP04"
    assert payload["source"] == "pytest"
    assert payload["actor"]["actor_id"] == "codex"
    assert payload["confidence"] == 0.93
    assert payload["occurred_at"] == "2026-06-09T12:00:00Z"
    assert payload["observed_at"] == "2026-06-09T12:00:05Z"
    assert payload["artifact_refs"][0]["uri"] == "artifacts/test-results.xml"
    assert isinstance(payload["idempotency_key"], str)
    assert len(payload["idempotency_key"]) == 64


def test_idempotency_key_is_deterministic_and_ignores_observed_at() -> None:
    first = build_proof_payload(
        "ReviewProofRecorded",
        _base_payload(review_kind="code_review", verdict="approved"),
    )
    second = build_proof_payload(
        "ReviewProofRecorded",
        _base_payload(
            review_kind="code_review",
            verdict="approved",
            observed_at="2026-06-09T12:10:00+00:00",
        ),
    )

    assert first["idempotency_key"] == second["idempotency_key"]
    assert first["idempotency_key"] == proof_idempotency_key("ReviewProofRecorded", first)


def test_matching_idempotency_key_is_accepted() -> None:
    canonical = build_proof_payload(
        "ProofItemRecorded",
        _base_payload(proof_kind="artifact"),
    )
    payload = build_proof_payload(
        "ProofItemRecorded",
        _base_payload(
            proof_kind="artifact",
            idempotency_key=canonical["idempotency_key"],
        ),
    )

    assert payload["idempotency_key"] == canonical["idempotency_key"]


def test_mismatched_idempotency_key_is_rejected() -> None:
    try:
        build_proof_payload(
            "ProofItemRecorded",
            _base_payload(
                proof_kind="artifact",
                idempotency_key="b" * 64,
            ),
        )
    except ValueError as exc:
        assert "idempotency_key must match deterministic digest" in str(exc)
    else:
        raise AssertionError("mismatched idempotency key was accepted")


def test_oversized_summary_is_rejected() -> None:
    oversized = "x" * (MAX_PROOF_PAYLOAD_BYTES + 1)

    try:
        build_proof_payload(
            "ProofItemRecorded",
            _base_payload(proof_kind="artifact", summary={"raw": oversized}),
        )
    except ValidationError as exc:
        assert "summary must be artifact-backed" in str(exc)
    else:
        raise AssertionError("oversized proof summary was accepted")


def test_inline_artifact_content_is_rejected() -> None:
    try:
        build_proof_payload(
            "ProofItemRecorded",
            _base_payload(
                proof_kind="artifact",
                artifact_refs=[
                    {
                        "kind": "log",
                        "uri": "artifacts/run.log",
                        "content": "raw logs do not belong in the event",
                    }
                ],
            ),
        )
    except ValidationError as exc:
        assert "Extra inputs are not permitted" in str(exc)
    else:
        raise AssertionError("inline artifact content was accepted")


def test_unknown_proof_event_type_is_rejected() -> None:
    try:
        build_proof_payload("NotAProofEvent", _base_payload())
    except ValueError as exc:
        assert "Unknown proof event type" in str(exc)
    else:
        raise AssertionError("unknown proof event type was accepted")
