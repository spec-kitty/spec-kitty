"""Tests for validate_synthesis_state() fresh-seed early-exit (T007/T008).

Two scenarios:

1. ``built_in_only: true, artifacts: []`` manifest with NO sidecar files
   → synthesis_state_present is True, no errors.

2. ``built_in_only: true, artifacts: []`` manifest WITH stale sidecar files
   (the pre-fix state: stale fixture sidecars + seeded manifest) →
   early-exit still fires; no errors raised.

The second test directly reproduces the bug fixed by this WP: stale
``adapter_id: fixture`` sidecars committed in 0b6e2d7d9 combined with the
seeded ``built_in_only: true`` manifest caused ``validate_synthesis_state()``
to find provenance files, skip the original early-exit, and then fail because
those sidecars had no corresponding doctrine artifact.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from charter.bundle import validate_synthesis_state
from charter.activation.synthesizer.synthesize_pipeline import canonical_yaml

pytestmark = [pytest.mark.fast]


def _write_fresh_seed_manifest(repo_root: Path) -> Path:
    """Write a fresh-seed synthesis-manifest.yaml (built_in_only=True, artifacts=[]).

    Mirrors the file produced by ``spec-kitty init`` on first project setup.
    The manifest_hash must be the SHA-256 of canonical_yaml(all non-hash fields)
    so that load_yaml() + verify_manifest_hash() do not reject the file if the
    early-exit were removed.
    """
    data_without_hash: dict[str, object] = {
        "schema_version": "2",
        "mission_id": None,
        "created_at": "1970-01-01T00:00:00+00:00",
        "run_id": "fresh-project-seed",
        "adapter_id": "fresh-seed",
        "adapter_version": "3.2.0rc44",
        "synthesizer_version": "3.2.0rc44",
        "artifacts": [],
        "built_in_only": True,
    }
    manifest_hash = hashlib.sha256(canonical_yaml(data_without_hash)).hexdigest()  # noqa: TID251 — manifest self-hash uses SHA-256 over canonical_yaml, not charter.hasher freshness

    manifest_dir = repo_root / ".kittify" / "charter"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = manifest_dir / "synthesis-manifest.yaml"
    manifest_path.write_text(
        "adapter_id: fresh-seed\n"
        "adapter_version: 3.2.0rc44\n"
        "artifacts: []\n"
        "built_in_only: true\n"
        "created_at: '1970-01-01T00:00:00+00:00'\n"
        f"manifest_hash: {manifest_hash}\n"
        "mission_id: null\n"
        "run_id: fresh-project-seed\n"
        "schema_version: '2'\n"
        "synthesizer_version: 3.2.0rc44\n",
        encoding="utf-8",
    )
    return manifest_path


def _write_stale_fixture_sidecar(repo_root: Path, kind: str, slug: str) -> Path:
    """Write a stale adapter_id=fixture provenance sidecar with no matching artifact.

    Replicates the files committed in 0b6e2d7d9 that caused the pre-fix
    validation failure.
    """
    prov_dir = repo_root / ".kittify" / "charter" / "provenance"
    prov_dir.mkdir(parents=True, exist_ok=True)
    sidecar = prov_dir / f"{kind}-{slug}.yaml"
    sidecar.write_text(
        f"schema_version: '2'\n"
        f"artifact_urn: '{kind}:{slug}'\n"
        f"artifact_kind: {kind}\n"
        f"artifact_slug: {slug}\n"
        f"artifact_content_hash: {'a' * 64}\n"
        f"inputs_hash: {'b' * 64}\n"
        f"adapter_id: fixture\n"
        f"adapter_version: 1.0.0\n"
        f"synthesizer_version: '3.2.0a5'\n"
        f"source_section: null\n"
        f"source_urns: []\n"
        f"source_input_ids: []\n"
        f"generated_at: '2026-04-30T00:00:00+00:00'\n"
        f"produced_at: '2026-01-01T00:00:00+00:00'\n"
        f"corpus_snapshot_id: '(none)'\n"
        f"synthesis_run_id: '01HTEST00000000000000TEST01'\n",
        encoding="utf-8",
    )
    return sidecar


def test_fresh_seed_manifest_no_sidecars_passes(tmp_path: Path) -> None:
    """built_in_only=True, artifacts=[], no sidecar files → no errors.

    Covers the canonical fresh-checkout state after the stale sidecars are
    removed: only the seeded synthesis-manifest.yaml is present.
    """
    _write_fresh_seed_manifest(tmp_path)

    result = validate_synthesis_state(tmp_path)

    assert result.synthesis_state_present is True, (
        "synthesis_state_present must be True when the manifest exists"
    )
    assert result.errors == [], (
        f"No errors expected for fresh-seed state; got: {result.errors}"
    )


def test_fresh_seed_manifest_with_stale_sidecars_passes(tmp_path: Path) -> None:
    """built_in_only=True, artifacts=[], WITH stale sidecars → early-exit fires, no errors.

    Reproduces the pre-fix bug (Defect 3):
    - synthesis-manifest.yaml has built_in_only=True and artifacts=[]
    - Three stale adapter_id=fixture sidecar files are present with no
      corresponding .kittify/charter-packs/ artifacts
    - Before the fix, validate_synthesis_state() found the sidecar files,
      skipped the original (all-absent) early-exit, and raised errors because
      the sidecars referenced non-existent artifacts.
    - After the fix, _manifest_is_fresh_seed() fires first and returns success.
    """
    _write_fresh_seed_manifest(tmp_path)

    # Replicate the three stale sidecars from commit 0b6e2d7d9.
    _write_stale_fixture_sidecar(tmp_path, "directive", "mission-type-scope-directive")
    _write_stale_fixture_sidecar(tmp_path, "directive", "neutrality-posture-directive")
    _write_stale_fixture_sidecar(tmp_path, "tactic", "testing-philosophy-tactic")

    # No .kittify/charter-packs/ artifacts exist — the sidecars are orphaned.
    assert not (tmp_path / ".kittify" / "charter-packs").exists(), (
        "Precondition: no doctrine artifacts exist"
    )

    result = validate_synthesis_state(tmp_path)

    assert result.synthesis_state_present is True, (
        "synthesis_state_present must be True when the manifest exists"
    )
    assert result.errors == [], (
        f"Early-exit must suppress stale-sidecar errors for built_in_only manifest; "
        f"got: {result.errors}"
    )


def test_manifest_with_real_artifacts_gets_full_validation(tmp_path: Path) -> None:
    """built_in_only=True but artifacts non-empty → NOT an early-exit candidate.

    An inconsistent manifest (built_in_only=True but with artifacts listed)
    should not early-exit — full validation must run and catch missing files.
    """
    # Write a manifest with built_in_only=True but a non-empty artifacts list.
    # The artifact is not on disk → full validation finds a hash mismatch or
    # missing file error.
    data_without_hash: dict[str, object] = {
        "schema_version": "2",
        "mission_id": None,
        "created_at": "1970-01-01T00:00:00+00:00",
        "run_id": "test-run",
        "adapter_id": "test",
        "adapter_version": "1.0.0",
        "synthesizer_version": "3.2.0rc44",
        "artifacts": [
            {
                "kind": "tactic",
                "slug": "some-tactic",
                "path": ".kittify/charter-packs/tactic/some-tactic.tactic.yaml",
                "provenance_path": ".kittify/charter/provenance/tactic-some-tactic.yaml",
                "content_hash": "a" * 64,
            }
        ],
        "built_in_only": True,
    }
    manifest_hash = hashlib.sha256(canonical_yaml(data_without_hash)).hexdigest()  # noqa: TID251 — manifest self-hash uses SHA-256 over canonical_yaml, not charter.hasher freshness

    manifest_dir = tmp_path / ".kittify" / "charter"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = manifest_dir / "synthesis-manifest.yaml"
    manifest_path.write_text(
        "adapter_id: test\n"
        "adapter_version: 1.0.0\n"
        "artifacts:\n"
        "- content_hash: " + "a" * 64 + "\n"
        "  kind: tactic\n"
        "  path: .kittify/charter-packs/tactic/some-tactic.tactic.yaml\n"
        "  provenance_path: .kittify/charter/provenance/tactic-some-tactic.yaml\n"
        "  slug: some-tactic\n"
        "built_in_only: true\n"
        "created_at: '1970-01-01T00:00:00+00:00'\n"
        f"manifest_hash: {manifest_hash}\n"
        "mission_id: null\n"
        "run_id: test-run\n"
        "schema_version: '2'\n"
        "synthesizer_version: 3.2.0rc44\n",
        encoding="utf-8",
    )

    result = validate_synthesis_state(tmp_path)

    # Full validation runs and produces errors because the listed artifact is absent.
    assert result.synthesis_state_present is True
    assert result.errors, (
        "Errors expected: manifest lists an artifact that does not exist on disk"
    )
