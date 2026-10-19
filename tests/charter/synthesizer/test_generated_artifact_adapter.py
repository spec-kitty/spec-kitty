"""Tests for the harness-owned generated artifact adapter and evidence roundtrips."""

from __future__ import annotations

import json
import hashlib
from pathlib import Path

import pytest

from charter.activation.synthesizer.errors import (
    GeneratedArtifactLoadError,
    GeneratedArtifactMissingError,
)
from charter.activation.synthesizer.evidence import CodeSignals, CorpusEntry, CorpusSnapshot, EvidenceBundle
from charter.activation.synthesizer.generated_artifact_adapter import GeneratedArtifactAdapter
from charter.activation.synthesizer.provenance import load_yaml as load_provenance
from charter.activation.synthesizer.request import SynthesisRequest, SynthesisTarget, _evidence_to_jsonable
from charter.activation.synthesizer.resynthesize_pipeline import run as resynthesize_run
from charter.activation.synthesizer.orchestrator import synthesize


pytestmark = [pytest.mark.unit]

VALID_DIRECTIVE_BODY = {
    "id": "PROJECT_001",
    "schema_version": "1.0",
    "title": "Mission Scope Directive",
    "intent": "Capture project mission scope for governance synthesis tests.",
    "enforcement": "required",
}


def _directive_request(evidence: EvidenceBundle | None = None) -> SynthesisRequest:
    target = SynthesisTarget(
        kind="directive",
        slug="project-intent-directive",
        title="Project Intent Directive",
        artifact_id="PROJECT_001",
        source_section="mission_type",
    )
    return SynthesisRequest(
        target=target,
        interview_snapshot={},
        doctrine_snapshot={"directives": {}, "tactics": {}, "styleguides": {}},
        drg_snapshot={"nodes": [], "edges": [], "schema_version": "1"},
        run_id="01KTESTGENERATEDARTIFACT0001",
        evidence=evidence,
    )


def _generated_directive_path(repo_root: Path) -> Path:
    return (
        repo_root
        / ".kittify"
        / "charter"
        / "generated"
        / "directives"
        / "001-project-intent-directive.directive.yaml"
    )


def _write_generated_directive(repo_root: Path, body: dict[str, object]) -> Path:
    path = _generated_directive_path(repo_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    import ruamel.yaml

    yaml = ruamel.yaml.YAML()
    with path.open("w", encoding="utf-8") as fh:
        yaml.dump(body, fh)
    return path


def _evidence_hash(bundle: EvidenceBundle) -> str:
    raw = json.dumps(_evidence_to_jsonable(bundle), sort_keys=True, ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()  # noqa: TID251 — charter synthesizer generated-artifact hash (own scheme), not charter.hasher.hash_content() freshness


def test_generated_adapter_missing_file_raises(tmp_path: Path) -> None:
    request = _directive_request()
    adapter = GeneratedArtifactAdapter(repo_root=tmp_path)

    with pytest.raises(GeneratedArtifactMissingError) as exc_info:
        adapter.generate(request)

    assert "001-project-intent-directive.directive.yaml" in exc_info.value.expected_path
    assert exc_info.value.expected_id == "PROJECT_001"
    assert "PROJECT_001" in str(exc_info.value)


def test_generated_adapter_rejects_identity_mismatch(tmp_path: Path) -> None:
    request = _directive_request()
    adapter = GeneratedArtifactAdapter(repo_root=tmp_path)
    body = dict(VALID_DIRECTIVE_BODY)
    body["id"] = "PROJECT_999"
    _write_generated_directive(tmp_path, body)

    with pytest.raises(GeneratedArtifactLoadError) as exc_info:
        adapter.generate(request)

    assert exc_info.value.expected_id == "PROJECT_001"
    assert exc_info.value.actual_id == "PROJECT_999"
    assert "artifact id mismatch" in str(exc_info.value)
    assert "PROJECT_001" in str(exc_info.value)
    assert "PROJECT_999" in str(exc_info.value)


def test_evidence_hash_survives_synthesize_and_resynthesize_roundtrip(tmp_path: Path) -> None:
    evidence = EvidenceBundle(
        code_signals=CodeSignals(
            stack_id="python",
            primary_language="python",
            frameworks=("django",),
            test_frameworks=("pytest",),
            scope_tag="python",
            representative_files=("src/app.py",),
            detected_at="2026-04-19T00:00:00+00:00",
        ),
        url_list=("https://example.com/governance",),
        corpus_snapshot=CorpusSnapshot(
            profile_key="python",
            snapshot_id="python-v1.0.0",
            entries=(
                CorpusEntry(
                    topic="testing",
                    guidance="Prefer fast deterministic tests.",
                    tags=("python", "testing"),
                ),
            ),
            loaded_at="2026-04-19T00:00:00+00:00",
        ),
        collected_at="2026-04-19T00:00:00+00:00",
    )
    expected_hash = _evidence_hash(evidence)

    request = _directive_request(evidence=evidence)
    adapter = GeneratedArtifactAdapter(repo_root=tmp_path)
    _write_generated_directive(tmp_path, VALID_DIRECTIVE_BODY)

    synthesize(request, adapter=adapter, repo_root=tmp_path)

    prov_path = (
        tmp_path
        / ".kittify"
        / "charter"
        / "provenance"
        / "directive-project-intent-directive.yaml"
    )
    first_prov = load_provenance(prov_path)
    assert first_prov.artifact_urn == "directive:PROJECT_001"
    assert first_prov.evidence_bundle_hash == expected_hash
    assert first_prov.corpus_snapshot_id == "python-v1.0.0"

    resynthesize_run(
        request=request,
        adapter=adapter,
        topic="directive:PROJECT_001",
        repo_root=tmp_path,
    )

    second_prov = load_provenance(prov_path)
    assert second_prov.artifact_urn == "directive:PROJECT_001"
    assert second_prov.evidence_bundle_hash == expected_hash
    assert second_prov.corpus_snapshot_id == "python-v1.0.0"
