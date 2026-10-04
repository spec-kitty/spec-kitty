"""Tests for charter status FR-009/FR-010/FR-011 — bundle compatibility reader blocks.

Covers:
- T019: v1 bundle blocks charter status / bundle validate
- T019: future bundle (version > MAX) blocks status
- T019: v2 bundle passes through status (exit 0)
- T019: charter status --json --provenance regression: synthesizer_version and
         produced_at must be present in provenance entries (FR-010)
- T019: bundle validate fails on sidecar missing synthesizer_version (FR-006)
- T019: bundle validate passes for a complete v2 bundle (FR-011)
"""

from __future__ import annotations

import hashlib
import io
import json
from collections.abc import Callable
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from ruamel.yaml import YAML
from typer.testing import CliRunner

from specify_cli.cli.commands.charter import app as charter_app
from specify_cli.cli.commands.charter._status_collectors import _collect_manifest_status
from specify_cli.cli.commands.charter_bundle import app as charter_bundle_app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

pytestmark = [pytest.mark.unit, pytest.mark.fast]
runner = CliRunner()

_yaml = YAML()
_yaml.default_flow_style = False
_yaml.explicit_start = False


def _write_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    buf = io.BytesIO()
    _yaml.dump(data, buf)
    path.write_bytes(buf.getvalue())


def _compute_manifest_hash(fields: dict) -> str:
    from charter.offering.yaml_utils import canonical_yaml
    return hashlib.sha256(canonical_yaml(fields)).hexdigest()  # noqa: TID251 — provenance manifest-hash mirror (synthesizer scheme), not charter.hasher.hash_content() freshness


def _setup_charter_v1_project(project_path: Path) -> None:
    """Create a minimal v1 charter bundle (bundle_schema_version: 1).

    consolidate-charter-bundle (#2773) retired the compiled ``metadata.yaml``
    and folded ``bundle_schema_version`` under ``charter.yaml``'s ``metadata:``
    section — the file/section ``get_bundle_schema_version`` now reads and the
    ``charter status`` compat gate keys off (it only fires when ``charter.yaml``
    exists). Stamping v1 here keeps the gate firing so the reader still blocks
    with the upgrade hint (v1 → NEEDS_MIGRATION → exit 1).
    """
    charter_dir = project_path / ".kittify" / "charter"

    # charter.yaml stamped v1 → compat gate treats as NEEDS_MIGRATION.
    _write_yaml(
        charter_dir / "charter.yaml",
        {"metadata": {"bundle_schema_version": 1}},
    )

    # Minimal provenance sidecar — v1 schema
    _write_yaml(
        charter_dir / "provenance" / "directive-review-policy.yaml",
        {
            "schema_version": "1",
            "artifact_urn": "drg:directive:review-policy",
            "artifact_kind": "directive",
            "artifact_slug": "review-policy",
            "artifact_content_hash": "a" * 64,
            "inputs_hash": "b" * 64,
            "adapter_id": "fixture",
            "adapter_version": "1.0.0",
            "generated_at": "2026-01-01T00:00:00Z",
            "source_section": "review_policy",
            "source_urns": [],
            "corpus_snapshot_id": None,
        },
    )

    # charter.md so status() can resolve charter path
    (charter_dir / "charter.md").write_text("# Test Charter\n", encoding="utf-8")


def _setup_charter_project_with_version(
    project_path: Path, *, bundle_schema_version: int
) -> None:
    """Create a charter bundle with a specific bundle_schema_version.

    consolidate-charter-bundle (#2773): ``bundle_schema_version`` now lives
    under ``charter.yaml``'s ``metadata:`` section (the source
    ``get_bundle_schema_version`` reads and the compat gate keys off).
    """
    charter_dir = project_path / ".kittify" / "charter"

    _write_yaml(
        charter_dir / "charter.yaml",
        {"metadata": {"bundle_schema_version": bundle_schema_version}},
    )

    (charter_dir / "charter.md").write_text("# Test Charter\n", encoding="utf-8")


def _setup_charter_v2_project(project_path: Path) -> None:
    """Create a complete v2 charter bundle suitable for status tests."""
    charter_dir = project_path / ".kittify" / "charter"

    _write_yaml(
        charter_dir / "metadata.yaml",
        {
            "bundle_schema_version": 2,
            "timestamp_utc": "2026-01-01T00:00:00Z",
        },
    )

    _write_yaml(
        charter_dir / "provenance" / "directive-review-policy.yaml",
        {
            "schema_version": "2",
            "artifact_urn": "drg:directive:review-policy",
            "artifact_kind": "directive",
            "artifact_slug": "review-policy",
            "artifact_content_hash": "a" * 64,
            "inputs_hash": "b" * 64,
            "adapter_id": "fixture",
            "adapter_version": "1.0.0",
            "generated_at": "2026-01-01T00:00:00Z",
            "source_section": "review_policy",
            "source_urns": ["drg:directive:DIR-001"],
            "synthesizer_version": "3.2.6",
            "synthesis_run_id": "01TEST000000000000000000001",
            "produced_at": "2026-01-01T00:00:00+00:00",
            "source_input_ids": ["drg:directive:DIR-001"],
            "corpus_snapshot_id": "(none)",
        },
    )

    # synthesis-manifest.yaml — v2
    manifest_fields = {
        "schema_version": "2",
        "created_at": "2026-01-01T00:00:00Z",
        "run_id": "01TEST000000000000000000001",
        "adapter_id": "fixture",
        "adapter_version": "1.0.0",
        "synthesizer_version": "3.2.6",
        "artifacts": [],
    }
    manifest_hash = _compute_manifest_hash(manifest_fields)
    _write_yaml(
        charter_dir / "synthesis-manifest.yaml",
        {**manifest_fields, "manifest_hash": manifest_hash},
    )

    (charter_dir / "charter.md").write_text("# Test Charter\n", encoding="utf-8")


def _setup_charter_v2_project_missing_field(
    project_path: Path, *, remove_field: str
) -> None:
    """Create a v2 charter bundle with one required field removed from the sidecar."""
    _setup_charter_v2_project(project_path)
    sidecar_path = (
        project_path
        / ".kittify"
        / "charter"
        / "provenance"
        / "directive-review-policy.yaml"
    )
    data = _yaml.load(sidecar_path)
    data.pop(remove_field, None)

    buf = io.BytesIO()
    _yaml.dump(data, buf)
    sidecar_path.write_bytes(buf.getvalue())


def _make_sync_result_mock(repo_root: Path) -> MagicMock:
    """Return a mock EnsureCharteFreshResult with canonical_root set."""
    m = MagicMock()
    m.canonical_root = repo_root
    return m


def _make_evidence_summary() -> dict:
    return {
        "warnings": [],
        "code": None,
        "configured_urls": [],
        "configured_url_count": 0,
        "corpus_snapshot_id": None,
        "corpus_entry_count": 0,
    }


# ---------------------------------------------------------------------------
# FR-009: reader blocks — charter status
# ---------------------------------------------------------------------------


def test_status_v1_bundle_exits_1_with_upgrade_message(
    tmp_path: Path, charter_cwd_isolation: Callable[..., Path]
) -> None:
    """FR-009: charter status blocks with an actionable error on a v1 bundle."""
    _setup_charter_v1_project(tmp_path)
    charter_cwd_isolation(tmp_path)
    result = runner.invoke(charter_app, ["status"])
    assert result.exit_code == 1, (
        f"Expected exit code 1 for v1 bundle; got {result.exit_code}.\nOutput: {result.output}"
    )
    # Rich may wrap long lines; normalize whitespace before checking.
    normalized = " ".join(result.output.split())
    assert "spec-kitty upgrade" in normalized, (
        f"Expected upgrade hint in output.\nOutput: {result.output}"
    )


def test_status_future_bundle_exits_1(
    tmp_path: Path, charter_cwd_isolation: Callable[..., Path]
) -> None:
    """FR-009: charter status blocks when bundle version is newer than CLI supports."""
    _setup_charter_project_with_version(tmp_path, bundle_schema_version=99)
    charter_cwd_isolation(tmp_path)
    result = runner.invoke(charter_app, ["status"])
    assert result.exit_code == 1, (
        f"Expected exit code 1 for future bundle; got {result.exit_code}.\nOutput: {result.output}"
    )


def test_status_v2_bundle_exits_0(
    tmp_path: Path, charter_cwd_isolation: Callable[..., Path]
) -> None:
    """FR-011: charter status exits 0 for a fully-migrated v2 bundle."""
    _setup_charter_v2_project(tmp_path)
    charter_cwd_isolation(tmp_path)
    with (
        patch(
            "specify_cli.cli.commands.charter.ensure_charter_bundle_fresh",
            return_value=_make_sync_result_mock(tmp_path),
        ),
        patch(
            "specify_cli.cli.commands.charter._summarize_evidence",
            return_value=_make_evidence_summary(),
        ),
        patch(
            "charter.hasher.is_stale",
            return_value=(False, "abc123", "abc123"),
        ),
    ):
        result = runner.invoke(charter_app, ["status"])
    assert result.exit_code == 0, (
        f"Expected exit code 0 for v2 bundle; got {result.exit_code}.\nOutput: {result.output}"
    )


def test_manifest_status_counts_singular_live_artifacts_only(tmp_path: Path) -> None:
    """Live project doctrine status must not accept legacy plural dirs."""
    singular = tmp_path / ".kittify" / "doctrine" / "tactic"
    plural = tmp_path / ".kittify" / "doctrine" / "tactics"
    singular.mkdir(parents=True)
    plural.mkdir(parents=True)
    (singular / "live.tactic.yaml").write_text("id: live\n", encoding="utf-8")
    (plural / "legacy.tactic.yaml").write_text("id: legacy\n", encoding="utf-8")

    status, manifest = _collect_manifest_status(tmp_path)

    assert manifest is None
    assert status["state"] == "partial"
    assert status["live_artifact_count"] == 1


# ---------------------------------------------------------------------------
# FR-010: regression guard — --provenance --json output
# ---------------------------------------------------------------------------


def test_status_provenance_json_includes_synthesizer_version(
    tmp_path: Path, charter_cwd_isolation: Callable[..., Path]
) -> None:
    """FR-010: synthesizer_version must appear in --json --provenance entries."""
    _setup_charter_v2_project(tmp_path)
    charter_cwd_isolation(tmp_path)
    with (
        patch(
            "specify_cli.cli.commands.charter.ensure_charter_bundle_fresh",
            return_value=_make_sync_result_mock(tmp_path),
        ),
        patch(
            "specify_cli.cli.commands.charter._summarize_evidence",
            return_value=_make_evidence_summary(),
        ),
        patch(
            "charter.hasher.is_stale",
            return_value=(False, "abc123", "abc123"),
        ),
    ):
        result = runner.invoke(charter_app, ["status", "--provenance", "--json"])
    assert result.exit_code == 0, (
        f"Expected exit 0; got {result.exit_code}.\nOutput: {result.output}"
    )
    data = json.loads(result.output)
    # Payload shape: {"synthesis": {"provenance": {"entries": [...]}}}
    provenance_entries = data["synthesis"]["provenance"]["entries"]
    assert isinstance(provenance_entries, list), (
        "Expected synthesis.provenance.entries to be a list"
    )
    assert any(
        "synthesizer_version" in entry for entry in provenance_entries
    ), f"synthesizer_version not found in any provenance entry.\nEntries: {provenance_entries}"


def test_status_provenance_json_includes_produced_at(
    tmp_path: Path, charter_cwd_isolation: Callable[..., Path]
) -> None:
    """FR-010: produced_at must appear in --json --provenance entries."""
    _setup_charter_v2_project(tmp_path)
    charter_cwd_isolation(tmp_path)
    with (
        patch(
            "specify_cli.cli.commands.charter.ensure_charter_bundle_fresh",
            return_value=_make_sync_result_mock(tmp_path),
        ),
        patch(
            "specify_cli.cli.commands.charter._summarize_evidence",
            return_value=_make_evidence_summary(),
        ),
        patch(
            "charter.hasher.is_stale",
            return_value=(False, "abc123", "abc123"),
        ),
    ):
        result = runner.invoke(charter_app, ["status", "--provenance", "--json"])
    assert result.exit_code == 0, (
        f"Expected exit 0; got {result.exit_code}.\nOutput: {result.output}"
    )
    data = json.loads(result.output)
    provenance_entries = data["synthesis"]["provenance"]["entries"]
    assert isinstance(provenance_entries, list)
    assert any(
        "produced_at" in entry for entry in provenance_entries
    ), f"produced_at not found in any provenance entry.\nEntries: {provenance_entries}"


# ---------------------------------------------------------------------------
# FR-006 / FR-007: bundle validate — provenance sidecar content validation
# ---------------------------------------------------------------------------


def test_bundle_validate_fails_on_missing_synthesizer_version(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FR-006: bundle validate exits 1 when sidecar is missing synthesizer_version."""
    _setup_charter_v2_project_missing_field(tmp_path, remove_field="synthesizer_version")
    monkeypatch.chdir(tmp_path)
    with patch(
        "specify_cli.cli.commands.charter_bundle.resolve_canonical_repo_root",
        return_value=tmp_path,
    ):
        result = runner.invoke(charter_bundle_app, ["validate"])
    assert result.exit_code == 1, (
        f"Expected exit 1 for incomplete sidecar; got {result.exit_code}.\nOutput: {result.output}"
    )
    assert "synthesizer_version" in result.output, (
        f"Expected 'synthesizer_version' in output.\nOutput: {result.output}"
    )


def test_bundle_validate_fails_on_non_mapping_sidecar(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FR-006: bundle validate exits 1 when a sidecar is not a YAML mapping."""
    _setup_charter_v2_project(tmp_path)
    sidecar_path = (
        tmp_path
        / ".kittify"
        / "charter"
        / "provenance"
        / "directive-review-policy.yaml"
    )
    sidecar_path.write_text("- not\n- a\n- mapping\n", encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    with patch(
        "specify_cli.cli.commands.charter_bundle.resolve_canonical_repo_root",
        return_value=tmp_path,
    ):
        result = runner.invoke(charter_bundle_app, ["validate"])

    assert result.exit_code == 1, (
        f"Expected exit 1 for malformed sidecar; got {result.exit_code}.\nOutput: {result.output}"
    )
    assert "must be a YAML mapping" in result.output, (
        f"Expected mapping error in output.\nOutput: {result.output}"
    )


def test_bundle_validate_passes_complete_v2_bundle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FR-011: bundle validate does not emit provenance errors for a complete v2 bundle."""
    _setup_charter_v2_project(tmp_path)
    monkeypatch.chdir(tmp_path)
    with patch(
        "specify_cli.cli.commands.charter_bundle.resolve_canonical_repo_root",
        return_value=tmp_path,
    ), patch(
        "specify_cli.cli.commands.charter_bundle._is_git_tracked",
        return_value=True,
    ):
        result = runner.invoke(charter_bundle_app, ["validate"])
    # The validate command may still exit 1 if tracked files are missing from
    # the canonical manifest, but it must NOT emit a "Provenance validation error".
    assert "Provenance validation error" not in result.output, (
        f"Unexpected provenance error for complete v2 bundle.\nOutput: {result.output}"
    )


def test_bundle_validate_fails_when_manifest_artifact_has_missing_sidecar(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FR-007: bundle validate exits 1 when a manifest artifact has no sidecar file."""
    # Set up a v2 bundle whose synthesis-manifest.yaml declares an artifact
    # but the corresponding provenance sidecar is absent.
    charter_dir = tmp_path / ".kittify" / "charter"
    _write_yaml(
        charter_dir / "metadata.yaml",
        {"bundle_schema_version": 2, "timestamp_utc": "2026-01-01T00:00:00Z"},
    )
    (charter_dir / "charter.md").write_text("# Test Charter\n", encoding="utf-8")

    # synthesis-manifest.yaml references a provenance sidecar that does NOT exist.
    manifest_fields: dict = {
        "schema_version": "2",
        "created_at": "2026-01-01T00:00:00Z",
        "run_id": "01TEST000000000000000000002",
        "adapter_id": "fixture",
        "adapter_version": "1.0.0",
        "synthesizer_version": "3.2.6",
        "artifacts": [
            {
                "kind": "directive",
                "slug": "orphan-directive",
                "path": ".kittify/doctrine/directive/orphan-directive.yaml",
                "provenance_path": ".kittify/charter/provenance/orphan-directive.yaml",
                "content_hash": "c" * 64,
            }
        ],
    }
    manifest_hash = _compute_manifest_hash(manifest_fields)
    _write_yaml(
        charter_dir / "synthesis-manifest.yaml",
        {**manifest_fields, "manifest_hash": manifest_hash},
    )

    monkeypatch.chdir(tmp_path)
    with patch(
        "specify_cli.cli.commands.charter_bundle.resolve_canonical_repo_root",
        return_value=tmp_path,
    ):
        result = runner.invoke(charter_bundle_app, ["validate"])

    assert result.exit_code == 1, (
        f"Expected exit 1 for missing sidecar; got {result.exit_code}.\nOutput: {result.output}"
    )
    assert "orphan-directive" in result.output, (
        f"Expected artifact slug in error output.\nOutput: {result.output}"
    )
