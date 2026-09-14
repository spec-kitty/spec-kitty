"""Tests for mission dossier event types and emission (namespaced envelope).

These tests pin the wire shape produced by the four dossier event emitters
against the canonical ``spec_kitty_events>=5.0.0`` server schemas. The
legacy flat envelope (``mission_slug, artifact_key, content_hash_sha256, …``)
was rejected by the deployed SaaS with ``Additional properties are not
allowed``; the migration is tracked under
Priivacy-ai/spec-kitty#1047 and the launch evidence lives in
Priivacy-ai/spec-kitty-end-to-end-testing#37.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import jsonschema
import pytest
from pydantic import ValidationError
from spec_kitty_events.schemas import load_schema

from spec_kitty_events import (
    ArtifactIdentity,
    ContentHashRef,
    LocalNamespaceTuple,
    MissionDossierArtifactIndexedPayload,
    MissionDossierArtifactMissingPayload,
    MissionDossierParityDriftDetectedPayload,
    MissionDossierSnapshotComputedPayload,
    ProvenanceRef,
)
from specify_cli.dossier.events import (
    emit_artifact_indexed,
    emit_artifact_missing,
    emit_parity_drift_detected,
    emit_snapshot_computed,
)

pytestmark = pytest.mark.fast


# ── Schema helpers ─────────────────────────────────────────────────────


def _server_schema(name: str) -> dict[str, Any]:
    return load_schema(name)


def _assert_valid(payload: dict[str, Any], schema_name: str) -> None:
    jsonschema.validate(payload, _server_schema(schema_name))


@pytest.fixture
def namespace() -> LocalNamespaceTuple:
    return LocalNamespaceTuple(
        project_uuid="11111111-2222-3333-4444-555555555555",
        mission_slug="042-feature",
        target_branch="main",
        mission_type="software-dev",
        manifest_version="1.0.0",
    )


@pytest.fixture
def captured_emissions(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    captured: list[dict[str, Any]] = []

    def _fake(event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        captured.append(
            # canonical-event-exempt(comparison): test double records the exact args the producer passed to the no-transport drop seam
            {
                "event_type": event_type,
                "payload": payload,
            }
        )
        return {"ok": True, "event_id": f"fake-{len(captured)}"}

    monkeypatch.setattr("specify_cli.dossier.events._undelivered", _fake)
    return captured


# ── Sub-object models ──────────────────────────────────────────────────


class TestLocalNamespaceTuple:
    def test_valid(self) -> None:
        LocalNamespaceTuple(
            project_uuid="p",
            mission_slug="m",
            target_branch="main",
            mission_type="software-dev",
            manifest_version="1.0.0",
        )

    def test_rejects_extra(self) -> None:
        with pytest.raises(ValidationError):
            LocalNamespaceTuple(  # type: ignore[call-arg]
                project_uuid="p",
                mission_slug="m",
                target_branch="main",
                mission_type="software-dev",
                manifest_version="1.0.0",
                bogus="x",
            )

    def test_step_id_optional(self) -> None:
        ns = LocalNamespaceTuple(
            project_uuid="p",
            mission_slug="m",
            target_branch="main",
            mission_type="software-dev",
            manifest_version="1.0.0",
            step_id="planning",
        )
        assert ns.step_id == "planning"


class TestArtifactIdentity:
    def test_valid(self) -> None:
        ArtifactIdentity(mission_type="software-dev", path="spec.md", artifact_class="input")

    def test_rejects_unknown_class(self) -> None:
        with pytest.raises(ValidationError):
            ArtifactIdentity(mission_type="software-dev", path="spec.md", artifact_class="bogus")

    def test_rejects_other_class(self) -> None:
        # The new server schema dropped the legacy ``other`` enum value.
        with pytest.raises(ValidationError):
            ArtifactIdentity(mission_type="software-dev", path="spec.md", artifact_class="other")


class TestContentHashRef:
    # Retired: `test_lowercases_hash` pinned a `field_validator` that lived only
    # on the local Pydantic mirror this mission deletes (FR-001); canonical
    # `spec_kitty_events.ContentHashRef` has no such validator, so an uppercase
    # value now survives unchanged. No FR requires hash-case normalization, and
    # no production caller can reach this: every construction path
    # (`hasher.py::hash_file`, `hash_file_with_validation`,
    # `drift_detector.py`) feeds a value from `hashlib.sha256(...).hexdigest()`,
    # already lowercase. `dossier/models.py::ArtifactRef`'s own
    # `content_hash_sha256` validator checks hex format/length but never
    # normalized case either, so this was never a domain-level guarantee.
    # Preserving it was *possible*, not impossible — `_build_content_ref` in
    # `events.py` could `.lower()` the hash exactly as `_normalize_artifact_class`
    # already does for the analogous `artifact_class` legacy-value problem — but
    # doing so would add behavior no FR requires, which is scope widening beyond
    # this mission's spec. Retired deliberately rather than re-added.
    def test_valid(self) -> None:
        ContentHashRef(algorithm="sha256", hash="a" * 64, size_bytes=10)

    def test_rejects_unknown_algorithm(self) -> None:
        with pytest.raises(ValidationError):
            ContentHashRef(algorithm="crc32", hash="abc")


# ── End-to-end emitter behavior + schema parity ────────────────────────


class TestEmitArtifactIndexed:
    def test_emits_namespaced_envelope(self, captured_emissions: list[dict[str, Any]], namespace: LocalNamespaceTuple) -> None:
        result = emit_artifact_indexed(
            mission_slug="042-feature",
            artifact_key="input.spec.main",
            artifact_class="input",
            relative_path="spec.md",
            content_hash_sha256="a" * 64,
            size_bytes=1024,
            wp_id="WP01",
            step_id="planning",
            required_status="required",
            namespace=namespace,
        )
        assert result is not None
        assert len(captured_emissions) == 1  # (call-count; content pinned below)
        evt = captured_emissions[0]
        assert evt["event_type"] == "MissionDossierArtifactIndexed"

        payload = evt["payload"]
        assert set(payload.keys()).issubset({"namespace", "artifact_id", "content_ref", "indexed_at", "provenance", "step_id", "context_diagnostics", "supersedes"})
        assert payload["namespace"]["mission_slug"] == "042-feature"
        assert payload["namespace"]["mission_type"] == "software-dev"
        assert payload["artifact_id"] == {
            "mission_type": "software-dev",
            "path": "spec.md",
            "artifact_class": "input",
            "wp_id": "WP01",
        }
        assert payload["content_ref"] == {
            "algorithm": "sha256",
            "hash": "a" * 64,
            "size_bytes": 1024,
        }
        assert payload["step_id"] == "planning"
        assert payload["context_diagnostics"]["artifact_key"] == "input.spec.main"
        assert payload["context_diagnostics"]["required_status"] == "required"

        _assert_valid(payload, "mission_dossier_artifact_indexed_payload")

    def test_legacy_other_class_maps_to_runtime(self, captured_emissions: list[dict[str, Any]], namespace: LocalNamespaceTuple) -> None:
        emit_artifact_indexed(
            mission_slug="042-feature",
            artifact_key="legacy.other",
            artifact_class="other",
            relative_path="legacy.md",
            content_hash_sha256="a" * 64,
            size_bytes=1,
            namespace=namespace,
        )
        payload = captured_emissions[0]["payload"]
        assert payload["artifact_id"]["artifact_class"] == "runtime"
        _assert_valid(payload, "mission_dossier_artifact_indexed_payload")

    def test_accepts_dict_namespace(self, captured_emissions: list[dict[str, Any]], namespace: LocalNamespaceTuple) -> None:
        ns_dict = namespace.model_dump(exclude_none=True)
        emit_artifact_indexed(
            mission_slug="042-feature",
            artifact_key="input.spec.main",
            artifact_class="input",
            relative_path="spec.md",
            content_hash_sha256="a" * 64,
            size_bytes=1,
            namespace=ns_dict,
        )
        assert captured_emissions
        _assert_valid(captured_emissions[0]["payload"], "mission_dossier_artifact_indexed_payload")

    def test_missing_namespace_refuses_to_emit(self, captured_emissions: list[dict[str, Any]], caplog: pytest.LogCaptureFixture) -> None:
        caplog.set_level(logging.ERROR, logger="specify_cli.dossier.events")
        result = emit_artifact_indexed(
            mission_slug="042-feature",
            artifact_key="input.spec.main",
            artifact_class="input",
            relative_path="spec.md",
            content_hash_sha256="a" * 64,
            size_bytes=1,
            namespace=None,
        )
        assert result is None
        assert not captured_emissions
        assert any("MissionDossierArtifactIndexed" in record.message for record in caplog.records)

    def test_invalid_artifact_class_returns_none(self, captured_emissions: list[dict[str, Any]], namespace: LocalNamespaceTuple) -> None:
        result = emit_artifact_indexed(
            mission_slug="042-feature",
            artifact_key="x",
            artifact_class="bogus",
            relative_path="x.md",
            content_hash_sha256="a" * 64,
            size_bytes=1,
            namespace=namespace,
        )
        assert result is None
        assert not captured_emissions

    def test_payload_is_canonical_class_instance(
        self,
        monkeypatch: pytest.MonkeyPatch,
        captured_emissions: list[dict[str, Any]],
        namespace: LocalNamespaceTuple,
    ) -> None:
        """FR-001/Acceptance Scenario 1: the pre-serialization payload the
        emitter builds must actually be an instance of the canonical
        ``spec_kitty_events`` class, not merely a dict/mirror-shaped object
        that happens to serialize identically. A jsonschema shape-only check
        (as used elsewhere in this file) cannot distinguish the two; this
        isinstance check is the binding identity proof.
        """
        captured_payload_objects: list[object] = []
        original_model_dump = MissionDossierArtifactIndexedPayload.model_dump

        def _capturing_model_dump(self: Any, *args: Any, **kwargs: Any) -> dict[str, Any]:
            captured_payload_objects.append(self)
            return original_model_dump(self, *args, **kwargs)

        monkeypatch.setattr(MissionDossierArtifactIndexedPayload, "model_dump", _capturing_model_dump)

        emit_artifact_indexed(
            mission_slug="042-feature",
            artifact_key="input.spec.main",
            artifact_class="input",
            relative_path="spec.md",
            content_hash_sha256="a" * 64,
            size_bytes=1,
            namespace=namespace,
        )

        assert captured_payload_objects
        assert isinstance(captured_payload_objects[0], MissionDossierArtifactIndexedPayload)

    def test_provenance_ref_shaped_dict_round_trips(self, captured_emissions: list[dict[str, Any]], namespace: LocalNamespaceTuple) -> None:
        """PR-CONTRACT-001 (non-None path): a dict matching the canonical
        ``ProvenanceRef`` shape (actor_id/actor_kind/git_ref/git_sha/
        revised_at/source_event_ids) is accepted and round-trips into the
        emitted payload -- proving the advertised type actually works, not
        just that the wrong shape fails loudly (covered below).
        """
        result = emit_artifact_indexed(
            mission_slug="042-feature",
            artifact_key="input.spec.main",
            artifact_class="input",
            relative_path="spec.md",
            content_hash_sha256="a" * 64,
            size_bytes=1,
            namespace=namespace,
            provenance={"actor_id": "agent-ivan", "actor_kind": "llm"},
        )
        assert result is not None
        payload = captured_emissions[0]["payload"]
        assert payload["provenance"] == {"actor_id": "agent-ivan", "actor_kind": "llm"}
        _assert_valid(payload, "mission_dossier_artifact_indexed_payload")

    def test_provenance_ref_instance_round_trips(self, captured_emissions: list[dict[str, Any]], namespace: LocalNamespaceTuple) -> None:
        """A pre-built ``ProvenanceRef`` instance is also accepted directly."""
        result = emit_artifact_indexed(
            mission_slug="042-feature",
            artifact_key="input.spec.main",
            artifact_class="input",
            relative_path="spec.md",
            content_hash_sha256="a" * 64,
            size_bytes=1,
            namespace=namespace,
            provenance=ProvenanceRef(actor_id="agent-ivan", actor_kind="llm"),
        )
        assert result is not None
        payload = captured_emissions[0]["payload"]
        assert payload["provenance"] == {"actor_id": "agent-ivan", "actor_kind": "llm"}

    def test_dossier_shaped_provenance_raises_loudly_instead_of_dropping(
        self, captured_emissions: list[dict[str, Any]], namespace: LocalNamespaceTuple
    ) -> None:
        """PR-CONTRACT-001: this package's own artifact-level provenance
        shape (``source_kind``/``actor_id``/``captured_at``, see
        ``dossier.models.ArtifactRef.provenance``) is NOT the canonical
        ``ProvenanceRef`` shape (``extra="forbid"``). Passing it must raise
        ``pydantic.ValidationError`` -- not be swallowed by the broad
        ``except (TypeError, ValueError)`` further down and silently return
        ``None``, which is the defect this test pins closed.
        """
        with pytest.raises(ValidationError):
            emit_artifact_indexed(
                mission_slug="042-feature",
                artifact_key="input.spec.main",
                artifact_class="input",
                relative_path="spec.md",
                content_hash_sha256="a" * 64,
                size_bytes=1,
                namespace=namespace,
                provenance={"source_kind": "git", "actor_id": "x", "captured_at": "2026-08-22T12:00:00Z"},
            )
        assert not captured_emissions


class TestEmitArtifactMissing:
    def test_blocking_emits_namespaced_envelope(self, captured_emissions: list[dict[str, Any]], namespace: LocalNamespaceTuple) -> None:
        emit_artifact_missing(
            mission_slug="042-feature",
            artifact_key="output.dossier.indexed",
            artifact_class="output",
            expected_path_pattern="dossier.json",
            reason_code="not_found",
            reason_detail="never produced by the indexer",
            blocking=True,
            namespace=namespace,
            manifest_step="indexing",
        )
        assert captured_emissions
        payload = captured_emissions[0]["payload"]
        _assert_valid(payload, "mission_dossier_artifact_missing_payload")
        assert payload["expected_identity"]["path"] == "dossier.json"
        assert payload["manifest_step"] == "indexing"
        assert payload["context_diagnostics"]["reason_code"] == "not_found"
        assert payload["context_diagnostics"]["reason_detail"] == "never produced by the indexer"

    def test_non_blocking_skips(self, captured_emissions: list[dict[str, Any]], namespace: LocalNamespaceTuple) -> None:
        result = emit_artifact_missing(
            mission_slug="042-feature",
            artifact_key="optional.body",
            artifact_class="output",
            expected_path_pattern="body.md",
            reason_code="not_found",
            blocking=False,
            namespace=namespace,
        )
        assert result is None
        assert not captured_emissions

    def test_payload_is_canonical_class_instance(
        self,
        monkeypatch: pytest.MonkeyPatch,
        captured_emissions: list[dict[str, Any]],
        namespace: LocalNamespaceTuple,
    ) -> None:
        """FR-001/Acceptance Scenario 1: same binding identity proof as
        ``TestEmitArtifactIndexed.test_payload_is_canonical_class_instance``,
        for ``emit_artifact_missing``'s payload class.
        """
        captured_payload_objects: list[object] = []
        original_model_dump = MissionDossierArtifactMissingPayload.model_dump

        def _capturing_model_dump(self: Any, *args: Any, **kwargs: Any) -> dict[str, Any]:
            captured_payload_objects.append(self)
            return original_model_dump(self, *args, **kwargs)

        monkeypatch.setattr(MissionDossierArtifactMissingPayload, "model_dump", _capturing_model_dump)

        emit_artifact_missing(
            mission_slug="042-feature",
            artifact_key="output.dossier.indexed",
            artifact_class="output",
            expected_path_pattern="dossier.json",
            reason_code="not_found",
            blocking=True,
            namespace=namespace,
        )

        assert captured_payload_objects
        assert isinstance(captured_payload_objects[0], MissionDossierArtifactMissingPayload)


class TestEmitSnapshotComputed:
    def test_emits_namespaced_envelope(self, captured_emissions: list[dict[str, Any]], namespace: LocalNamespaceTuple) -> None:
        emit_snapshot_computed(
            mission_slug="042-feature",
            parity_hash_sha256="b" * 64,
            total_artifacts=10,
            required_artifacts=5,
            required_present=5,
            required_missing=0,
            optional_artifacts=5,
            optional_present=4,
            completeness_status="complete",
            snapshot_id="snap-01",
            namespace=namespace,
        )
        assert captured_emissions
        payload = captured_emissions[0]["payload"]
        _assert_valid(payload, "mission_dossier_snapshot_computed_payload")
        assert payload["snapshot_hash"] == "b" * 64
        assert payload["artifact_count"] == 10
        assert payload["anomaly_count"] == 0
        assert payload["context_diagnostics"]["snapshot_id"] == "snap-01"
        assert payload["context_diagnostics"]["completeness_status"] == "complete"

    def test_preserves_legacy_positional_order(self, captured_emissions: list[dict[str, Any]], namespace: LocalNamespaceTuple) -> None:
        emit_snapshot_computed(
            "042-feature",
            "b" * 64,
            10,
            6,
            4,
            2,
            4,
            3,
            "incomplete",
            "snap-positional",
            namespace,
        )

        payload = captured_emissions[0]["payload"]
        assert payload["artifact_count"] == 10
        assert payload["anomaly_count"] == 2
        assert payload["context_diagnostics"] == {
            "snapshot_id": "snap-positional",
            "completeness_status": "incomplete",
            "required_artifacts": "6",
            "required_present": "4",
            "optional_artifacts": "4",
            "optional_present": "3",
        }


class TestEmitParityDriftDetected:
    def test_emits_when_hashes_differ(self, captured_emissions: list[dict[str, Any]], namespace: LocalNamespaceTuple) -> None:
        emit_parity_drift_detected(
            mission_slug="042-feature",
            local_parity_hash="c" * 64,
            baseline_parity_hash="d" * 64,
            missing_in_local=["foo.md"],
            missing_in_baseline=["bar.md"],
            severity="warning",
            namespace=namespace,
        )
        assert captured_emissions
        payload = captured_emissions[0]["payload"]
        _assert_valid(payload, "mission_dossier_parity_drift_detected_payload")
        assert payload["actual_hash"] == "c" * 64
        assert payload["expected_hash"] == "d" * 64
        assert payload["drift_kind"] == "anomaly_introduced"
        paths = {item["path"] for item in payload["artifact_ids_changed"]}
        assert paths == {"foo.md", "bar.md"}
        assert payload["context_diagnostics"]["severity"] == "warning"

    def test_identical_hashes_skip(self, captured_emissions: list[dict[str, Any]], namespace: LocalNamespaceTuple) -> None:
        result = emit_parity_drift_detected(
            mission_slug="042-feature",
            local_parity_hash="c" * 64,
            baseline_parity_hash="c" * 64,
            severity="warning",
            namespace=namespace,
        )
        assert result is None
        assert not captured_emissions


# ── Wire-payload Pydantic models reject extras (parity with server) ────


class TestWirePayloadModelsRejectExtras:
    @pytest.mark.parametrize(
        "model_cls",
        [
            MissionDossierArtifactIndexedPayload,
            MissionDossierArtifactMissingPayload,
            MissionDossierSnapshotComputedPayload,
            MissionDossierParityDriftDetectedPayload,
        ],
    )
    def test_extras_rejected(self, model_cls: type) -> None:
        with pytest.raises(ValidationError):
            model_cls(bogus="x")  # type: ignore[call-arg]


class TestPayloadJsonRoundTrip:
    def test_indexed_payload_is_json_serializable(self, captured_emissions: list[dict[str, Any]], namespace: LocalNamespaceTuple) -> None:
        emit_artifact_indexed(
            mission_slug="042-feature",
            artifact_key="input.spec.main",
            artifact_class="input",
            relative_path="spec.md",
            content_hash_sha256="a" * 64,
            size_bytes=1,
            namespace=namespace,
        )
        payload = captured_emissions[0]["payload"]
        json.dumps(payload)


class TestNoTransportDrop:
    def test_unpatched_emitter_returns_none(self, namespace: LocalNamespaceTuple) -> None:
        result = emit_artifact_indexed(
            mission_slug="042-feature",
            artifact_key="input.spec.main",
            artifact_class="input",
            relative_path="spec.md",
            content_hash_sha256="a" * 64,
            size_bytes=1024,
            namespace=namespace,
        )
        assert result is None
