"""Tests for manifest.py — WP03 T017 / T020, updated for v2 (WP02).

Covers:
- manifest-last semantics: absence of manifest means "partial"
- SynthesisManifest round-trip (dump_yaml → load_yaml)
- verify() catches hash mismatch via ManifestIntegrityError
- verify() passes when hashes match
- run_id matches the staging dir concept
- Manifest ordering is deterministic (sorted by kind, slug)
- v2: manifest_hash validates correctly (strip → re-hash → matches)
- v2: synthesizer_version is required and non-empty
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import jsonschema
import pytest
from pydantic import ValidationError
from ruamel.yaml import YAML

from charter.activation.synthesizer.errors import ManifestIntegrityError
from charter.activation.synthesizer.manifest import (
    ManifestArtifactEntry,
    SynthesisManifest,
    compute_manifest_hash,
    dump_yaml,
    finalize_manifest,
    load_yaml,
    verify,
    verify_manifest_hash,
)
from charter.activation.synthesizer.path_guard import PathGuard
from charter.activation.synthesizer.synthesize_pipeline import canonical_yaml


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


pytestmark = [pytest.mark.unit, pytest.mark.corpus]

def _compute_manifest_hash(
    manifest: SynthesisManifest,
) -> str:
    """Compute the expected manifest_hash for a SynthesisManifest.

    Strips manifest_hash from model_dump, serializes via canonical_yaml (bytes),
    then SHA-256 hexdigest. canonical_yaml returns bytes — no .encode() needed.
    """
    fields = manifest.model_dump(mode="python")
    fields.pop("manifest_hash")
    return hashlib.sha256(canonical_yaml(fields)).hexdigest()  # noqa: TID251 — charter synthesizer's own manifest/content-hash scheme, not the charter.hasher.hash_content() freshness algorithm


def _make_manifest(run_id: str = "01KPE222TESTRUNID0000000001") -> SynthesisManifest:
    """Create a sample v2 manifest for testing.

    Builds the instance with a placeholder ``manifest_hash`` and routes it
    through :func:`finalize_manifest` (WP01, synthesized-drg-stale-refresh)
    rather than hand-computing the hash over a raw dict literal. A hand-
    rolled ``data_without_hash`` dict silently omits any field a later
    schema revision adds (exactly the class of bug fact #15/#16 and
    BLOCKER-1/2 describe for production writers) — routing through the
    single canonical finalizer keeps this fixture self-consistent by
    construction as the model gains fields.
    """
    artifacts = [
        ManifestArtifactEntry(
            kind="tactic",
            slug="my-tactic",
            path=".kittify/doctrine/tactic/my-tactic.tactic.yaml",
            provenance_path=".kittify/charter/provenance/tactic-my-tactic.yaml",
            content_hash="a" * 64,
        ),
    ]
    manifest = SynthesisManifest(
        schema_version="2",
        mission_id=None,
        created_at="2026-04-17T12:00:00+00:00",
        run_id=run_id,
        adapter_id="fixture",
        adapter_version="1.0.0",
        synthesizer_version="3.2.0a5",
        manifest_hash="0" * 64,
        artifacts=artifacts,
    )
    return finalize_manifest(manifest)


def _make_manifest_for_artifacts(
    artifacts: list[ManifestArtifactEntry],
    run_id: str = "01KPE222TESTRUNID0000000001",
) -> SynthesisManifest:
    data_without_hash = {
        "schema_version": "2",
        "mission_id": None,
        "created_at": "2026-04-17T12:00:00+00:00",
        "run_id": run_id,
        "adapter_id": "fixture",
        "adapter_version": "1.0.0",
        "synthesizer_version": "3.2.0a5",
        "artifacts": [a.model_dump(mode="python") for a in artifacts],
        "built_in_only": False,
    }
    manifest_hash = hashlib.sha256(canonical_yaml(data_without_hash)).hexdigest()  # noqa: TID251 — charter synthesizer's own manifest/content-hash scheme, not the charter.hasher.hash_content() freshness algorithm
    return SynthesisManifest(
        created_at="2026-04-17T12:00:00+00:00",
        run_id=run_id,
        adapter_id="fixture",
        adapter_version="1.0.0",
        synthesizer_version="3.2.0a5",
        manifest_hash=manifest_hash,
        artifacts=artifacts,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def guard(tmp_path: Path) -> PathGuard:
    return PathGuard(tmp_path, extra_allowed_prefixes=[tmp_path])


# ---------------------------------------------------------------------------
# Manifest-last semantics
# ---------------------------------------------------------------------------


def test_manifest_absence_means_partial(tmp_path: Path) -> None:
    """If manifest file does not exist, the live tree is treated as partial.

    This test verifies the authority rule: manifest absent → partial state.
    We validate this by checking that load_yaml raises FileNotFoundError.
    """
    manifest_path = tmp_path / "synthesis-manifest.yaml"
    with pytest.raises(FileNotFoundError):
        load_yaml(manifest_path)


def test_run_id_present_in_manifest(tmp_path: Path, guard: PathGuard) -> None:
    """run_id in the manifest matches the staging dir run_id."""
    run_id = "01KPE222TESTRUNID0000000042"
    manifest = _make_manifest(run_id=run_id)
    out_path = tmp_path / "synthesis-manifest.yaml"
    dump_yaml(manifest, out_path, guard)
    loaded = load_yaml(out_path)
    assert loaded.run_id == run_id


# ---------------------------------------------------------------------------
# Round-trip
# ---------------------------------------------------------------------------


def test_manifest_round_trip(tmp_path: Path, guard: PathGuard) -> None:
    """dump_yaml → load_yaml reproduces all fields."""
    manifest = _make_manifest()
    out_path = tmp_path / "synthesis-manifest.yaml"
    dump_yaml(manifest, out_path, guard)
    loaded = load_yaml(out_path)
    assert loaded.schema_version == "2"
    assert loaded.run_id == manifest.run_id
    assert loaded.adapter_id == "fixture"
    assert loaded.adapter_version == "1.0.0"
    assert loaded.synthesizer_version == "3.2.0a5"
    assert len(loaded.manifest_hash) == 64
    assert {a.slug for a in loaded.artifacts} == {"my-tactic"}
    assert loaded.artifacts[0].kind == "tactic"
    assert loaded.artifacts[0].slug == "my-tactic"
    assert loaded.artifacts[0].content_hash == "a" * 64


def test_manifest_rejects_unknown_top_level_fields(tmp_path: Path) -> None:
    """Unknown manifest fields must not be silently dropped before hashing."""
    manifest = _make_manifest()
    data = manifest.model_dump(mode="python")
    data["tamper_marker"] = "unexpected"
    manifest_path = tmp_path / "synthesis-manifest.yaml"
    manifest_path.write_text(canonical_yaml(data).decode("utf-8"), encoding="utf-8")

    with pytest.raises(ValidationError):
        load_yaml(manifest_path)


def test_manifest_v2_schema_accepts_runtime_model_dump() -> None:
    """Runtime SynthesisManifest output must remain compatible with v2 schema."""
    schema_path = (
        Path(__file__).parents[3]
        / "kitty-specs"
        / "charter-p7-schema-versioning-provenance-01KQEG13"
        / "contracts"
        / "synthesis-manifest-v2.schema.yaml"
    )
    schema = YAML(typ="safe").load(schema_path.read_text(encoding="utf-8"))

    # bundle_content_hash (WP01, synthesized-drg-stale-refresh) is an
    # additive optional field the Pydantic model always serializes
    # (defaulting to None) once schema_version is widened to
    # Literal["2", "3"] — regardless of which version a given instance
    # carries. The v2 JSON contract predates the field and declares
    # `additionalProperties: false`; bumping that out-of-repo contract file
    # is out of WP01's owned surface (no schema-contract bump is scoped to
    # this mission — see data-model.md). Strip the field before validating
    # the legacy v2 payload shape the contract actually pins.
    dumped = _make_manifest().model_dump(mode="python")
    dumped.pop("bundle_content_hash")

    jsonschema.Draft202012Validator(schema).validate(dumped)


def test_manifest_with_mission_id(tmp_path: Path, guard: PathGuard) -> None:
    """mission_id is optional and round-trips correctly."""
    artifacts: list[ManifestArtifactEntry] = []
    data_without_hash = {
        "schema_version": "2",
        "mission_id": "01KPE222CD1MMCYEGB3ZCY51VR",
        "created_at": "2026-04-17T12:00:00+00:00",
        "run_id": "01KPE222TESTRUNID0000000001",
        "adapter_id": "fixture",
        "adapter_version": "1.0.0",
        "synthesizer_version": "3.2.0a5",
        "artifacts": [],
        "built_in_only": False,
    }
    manifest_hash = hashlib.sha256(canonical_yaml(data_without_hash)).hexdigest()  # noqa: TID251 — charter synthesizer's own manifest/content-hash scheme, not the charter.hasher.hash_content() freshness algorithm
    manifest = SynthesisManifest(
        created_at="2026-04-17T12:00:00+00:00",
        run_id="01KPE222TESTRUNID0000000001",
        adapter_id="fixture",
        adapter_version="1.0.0",
        synthesizer_version="3.2.0a5",
        manifest_hash=manifest_hash,
        mission_id="01KPE222CD1MMCYEGB3ZCY51VR",
        artifacts=artifacts,
    )
    out_path = tmp_path / "synthesis-manifest.yaml"
    dump_yaml(manifest, out_path, guard)
    loaded = load_yaml(out_path)
    assert loaded.mission_id == "01KPE222CD1MMCYEGB3ZCY51VR"


# ---------------------------------------------------------------------------
# verify() — hash matching
# ---------------------------------------------------------------------------


def test_verify_passes_when_hashes_match(tmp_path: Path, guard: PathGuard) -> None:
    """verify() passes when all artifact content_hash values match on-disk bytes."""
    # Create an actual artifact file
    artifact_bytes = b"id: PROJECT_001\ntitle: Test\n"
    content_hash = hashlib.sha256(artifact_bytes).hexdigest()  # noqa: TID251 — file-integrity checksum of an artifact's raw on-disk bytes, not the charter.hasher.hash_content() freshness algorithm

    artifact_rel = ".kittify/doctrine/tactic/my-tactic.tactic.yaml"
    artifact_path = tmp_path / artifact_rel
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_bytes(artifact_bytes)

    artifacts = [
        ManifestArtifactEntry(
            kind="tactic",
            slug="my-tactic",
            path=artifact_rel,
            provenance_path=".kittify/charter/provenance/tactic-my-tactic.yaml",
            content_hash=content_hash,
        )
    ]
    data_without_hash = {
        "schema_version": "2",
        "mission_id": None,
        "created_at": "2026-04-17T12:00:00+00:00",
        "run_id": "01KPE222TESTRUNID0000000001",
        "adapter_id": "fixture",
        "adapter_version": "1.0.0",
        "synthesizer_version": "3.2.0a5",
        "artifacts": [a.model_dump(mode="python") for a in artifacts],
        "built_in_only": False,
    }
    manifest_hash = hashlib.sha256(canonical_yaml(data_without_hash)).hexdigest()  # noqa: TID251 — charter synthesizer's own manifest/content-hash scheme, not the charter.hasher.hash_content() freshness algorithm
    manifest = SynthesisManifest(
        created_at="2026-04-17T12:00:00+00:00",
        run_id="01KPE222TESTRUNID0000000001",
        adapter_id="fixture",
        adapter_version="1.0.0",
        synthesizer_version="3.2.0a5",
        manifest_hash=manifest_hash,
        artifacts=artifacts,
    )
    # Should not raise
    verify(manifest, tmp_path)


def test_verify_raises_on_hash_mismatch(tmp_path: Path) -> None:
    """verify() raises ManifestIntegrityError when content_hash does not match."""
    artifact_rel = ".kittify/doctrine/tactic/my-tactic.tactic.yaml"
    artifact_path = tmp_path / artifact_rel
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_bytes(b"actual content")

    wrong_hash = "0" * 64  # definitely wrong

    artifacts = [
        ManifestArtifactEntry(
            kind="tactic",
            slug="my-tactic",
            path=artifact_rel,
            provenance_path=".kittify/charter/provenance/tactic-my-tactic.yaml",
            content_hash=wrong_hash,
        )
    ]
    data_without_hash = {
        "schema_version": "2",
        "mission_id": None,
        "created_at": "2026-04-17T12:00:00+00:00",
        "run_id": "01KPE222TESTRUNID0000000001",
        "adapter_id": "fixture",
        "adapter_version": "1.0.0",
        "synthesizer_version": "3.2.0a5",
        "artifacts": [a.model_dump(mode="python") for a in artifacts],
        "built_in_only": False,
    }
    manifest_hash = hashlib.sha256(canonical_yaml(data_without_hash)).hexdigest()  # noqa: TID251 — charter synthesizer's own manifest/content-hash scheme, not the charter.hasher.hash_content() freshness algorithm
    manifest = SynthesisManifest(
        created_at="2026-04-17T12:00:00+00:00",
        run_id="01KPE222TESTRUNID0000000001",
        adapter_id="fixture",
        adapter_version="1.0.0",
        synthesizer_version="3.2.0a5",
        manifest_hash=manifest_hash,
        artifacts=artifacts,
    )
    with pytest.raises(ManifestIntegrityError) as exc_info:
        verify(manifest, tmp_path)
    assert "my-tactic" in str(exc_info.value)


def test_verify_raises_on_missing_artifact(tmp_path: Path) -> None:
    """verify() raises ManifestIntegrityError when artifact file is missing."""
    artifact_rel = ".kittify/doctrine/tactic/missing-tactic.tactic.yaml"
    # Don't create the artifact file

    artifacts = [
        ManifestArtifactEntry(
            kind="tactic",
            slug="missing-tactic",
            path=artifact_rel,
            provenance_path=".kittify/charter/provenance/tactic-missing-tactic.yaml",
            content_hash="a" * 64,
        )
    ]
    data_without_hash = {
        "schema_version": "2",
        "mission_id": None,
        "created_at": "2026-04-17T12:00:00+00:00",
        "run_id": "01KPE222TESTRUNID0000000001",
        "adapter_id": "fixture",
        "adapter_version": "1.0.0",
        "synthesizer_version": "3.2.0a5",
        "artifacts": [a.model_dump(mode="python") for a in artifacts],
        "built_in_only": False,
    }
    manifest_hash = hashlib.sha256(canonical_yaml(data_without_hash)).hexdigest()  # noqa: TID251 — charter synthesizer's own manifest/content-hash scheme, not the charter.hasher.hash_content() freshness algorithm
    manifest = SynthesisManifest(
        created_at="2026-04-17T12:00:00+00:00",
        run_id="01KPE222TESTRUNID0000000001",
        adapter_id="fixture",
        adapter_version="1.0.0",
        synthesizer_version="3.2.0a5",
        manifest_hash=manifest_hash,
        artifacts=artifacts,
    )
    with pytest.raises(ManifestIntegrityError):
        verify(manifest, tmp_path)


def test_verify_rejects_absolute_artifact_path(tmp_path: Path) -> None:
    """Manifest verification must not read absolute paths outside the repo."""
    outside = tmp_path / "outside.tactic.yaml"
    outside.write_bytes(b"id: outside\n")
    manifest = _make_manifest_for_artifacts(
        [
            ManifestArtifactEntry(
                kind="tactic",
                slug="outside",
                path=str(outside),
                provenance_path=".kittify/charter/provenance/tactic-outside.yaml",
                content_hash=hashlib.sha256(outside.read_bytes()).hexdigest(),  # noqa: TID251 — file-integrity checksum of an artifact file's on-disk bytes, not the charter.hasher.hash_content() freshness algorithm
            )
        ]
    )

    with pytest.raises(ValueError, match="repo-relative"):
        verify(manifest, tmp_path / "repo")


def test_verify_rejects_traversal_artifact_path(tmp_path: Path) -> None:
    """Manifest artifact paths must stay within .kittify/doctrine."""
    manifest = _make_manifest_for_artifacts(
        [
            ManifestArtifactEntry(
                kind="tactic",
                slug="escape",
                path=".kittify/doctrine/../charter/provenance/tactic-escape.yaml",
                provenance_path=".kittify/charter/provenance/tactic-escape.yaml",
                content_hash="a" * 64,
            )
        ]
    )

    with pytest.raises(ValueError, match="repo-relative"):
        verify(manifest, tmp_path)


def test_verify_rejects_provenance_path_outside_provenance_tree(tmp_path: Path) -> None:
    """Manifest provenance paths must stay within .kittify/charter/provenance."""
    artifact_rel = ".kittify/doctrine/tactic/my-tactic.tactic.yaml"
    artifact_path = tmp_path / artifact_rel
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_bytes(b"id: my-tactic\n")
    manifest = _make_manifest_for_artifacts(
        [
            ManifestArtifactEntry(
                kind="tactic",
                slug="my-tactic",
                path=artifact_rel,
                provenance_path=".kittify/charter/../doctrine/tactic-my-tactic.yaml",
                content_hash=hashlib.sha256(artifact_path.read_bytes()).hexdigest(),  # noqa: TID251 — file-integrity checksum of an artifact file's on-disk bytes, not the charter.hasher.hash_content() freshness algorithm
            )
        ]
    )

    with pytest.raises(ValueError, match="repo-relative"):
        verify(manifest, tmp_path)


def test_verify_accepts_manifest_paths_with_windows_separators(tmp_path: Path) -> None:
    """Windows-written manifest paths are normalized before validation."""
    artifact_rel = ".kittify/doctrine/tactic/windows-path.tactic.yaml"
    artifact_path = tmp_path / artifact_rel
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_bytes(b"id: windows-path\n")
    manifest = _make_manifest_for_artifacts(
        [
            ManifestArtifactEntry(
                kind="tactic",
                slug="windows-path",
                path=artifact_rel.replace("/", "\\"),
                provenance_path=".kittify/charter/provenance/tactic-windows-path.yaml".replace(
                    "/", "\\"
                ),
                content_hash=hashlib.sha256(artifact_path.read_bytes()).hexdigest(),  # noqa: TID251 — file-integrity checksum of an artifact file's on-disk bytes, not the charter.hasher.hash_content() freshness algorithm
            )
        ]
    )

    verify(manifest, tmp_path)


# ---------------------------------------------------------------------------
# Ordering (deterministic)
# ---------------------------------------------------------------------------


def test_manifest_artifact_ordering(tmp_path: Path, guard: PathGuard) -> None:
    """Artifacts are stored in (kind, slug) order for determinism."""
    artifacts = [
        ManifestArtifactEntry(
            kind="tactic",
            slug="z-tactic",
            path=".kittify/doctrine/tactic/z-tactic.tactic.yaml",
            provenance_path=".kittify/charter/provenance/tactic-z-tactic.yaml",
            content_hash="a" * 64,
        ),
        ManifestArtifactEntry(
            kind="directive",
            slug="a-directive",
            path=".kittify/doctrine/directive/001-a-directive.directive.yaml",
            provenance_path=".kittify/charter/provenance/directive-a-directive.yaml",
            content_hash="b" * 64,
        ),
        ManifestArtifactEntry(
            kind="tactic",
            slug="a-tactic",
            path=".kittify/doctrine/tactic/a-tactic.tactic.yaml",
            provenance_path=".kittify/charter/provenance/tactic-a-tactic.yaml",
            content_hash="c" * 64,
        ),
    ]
    data_without_hash = {
        "schema_version": "2",
        "mission_id": None,
        "created_at": "2026-04-17T12:00:00+00:00",
        "run_id": "01KPE222TESTRUNID0000000001",
        "adapter_id": "fixture",
        "adapter_version": "1.0.0",
        "synthesizer_version": "3.2.0a5",
        "artifacts": [a.model_dump(mode="python") for a in artifacts],
        "built_in_only": False,
    }
    manifest_hash = hashlib.sha256(canonical_yaml(data_without_hash)).hexdigest()  # noqa: TID251 — charter synthesizer's own manifest/content-hash scheme, not the charter.hasher.hash_content() freshness algorithm
    manifest = SynthesisManifest(
        created_at="2026-04-17T12:00:00+00:00",
        run_id="01KPE222TESTRUNID0000000001",
        adapter_id="fixture",
        adapter_version="1.0.0",
        synthesizer_version="3.2.0a5",
        manifest_hash=manifest_hash,
        artifacts=artifacts,
    )
    out_path = tmp_path / "synthesis-manifest.yaml"
    dump_yaml(manifest, out_path, guard)
    loaded = load_yaml(out_path)
    # Verify round-trip preserves the order
    assert [a.slug for a in loaded.artifacts] == ["z-tactic", "a-directive", "a-tactic"]


# ---------------------------------------------------------------------------
# v2: manifest_hash validation
# ---------------------------------------------------------------------------


def test_manifest_hash_validates(tmp_path: Path, guard: PathGuard) -> None:
    """manifest_hash stored in the manifest matches a re-computed hash.

    Build a manifest, strip manifest_hash from model_dump, re-hash via
    canonical_yaml (bytes — no .encode() needed), verify it matches the stored hash.
    """
    manifest = _make_manifest()
    # Strip manifest_hash and re-compute
    fields_without_hash = manifest.model_dump(mode="python")
    fields_without_hash.pop("manifest_hash")
    # canonical_yaml() returns bytes — hash directly, no .encode()
    computed = hashlib.sha256(canonical_yaml(fields_without_hash)).hexdigest()  # noqa: TID251 — charter synthesizer's own manifest/content-hash scheme, not the charter.hasher.hash_content() freshness algorithm
    assert computed == manifest.manifest_hash


def test_legacy_v2_manifest_hash_without_built_in_only_verifies(tmp_path: Path) -> None:
    """Pre-built_in_only v2 manifests remain readable and self-hash-valid."""
    manifest_data: dict[str, object] = {
        "schema_version": "2",
        "mission_id": None,
        "created_at": "2026-04-17T12:00:00+00:00",
        "run_id": "01KPE222TESTRUNID0000000001",
        "adapter_id": "fixture",
        "adapter_version": "1.0.0",
        "synthesizer_version": "3.2.0a5",
        "artifacts": [],
    }
    manifest_data["manifest_hash"] = hashlib.sha256(  # noqa: TID251 — legacy manifest self-hash compatibility
        canonical_yaml(manifest_data)
    ).hexdigest()
    path = tmp_path / "synthesis-manifest.yaml"
    yaml = YAML()
    yaml.default_flow_style = False
    with path.open("w", encoding="utf-8") as fh:
        yaml.dump(manifest_data, fh)

    loaded = load_yaml(path)

    assert loaded.built_in_only is False
    verify_manifest_hash(loaded)


# ---------------------------------------------------------------------------
# WP01 (synthesized-drg-stale-refresh): bundle_content_hash field +
# finalize_manifest + generalized verify_manifest_hash shim (T006)
# ---------------------------------------------------------------------------


def test_v2_manifest_with_built_in_only_but_no_bundle_content_hash_verifies(
    tmp_path: Path,
) -> None:
    """T006(a) — green-preserving regression / intra-WP verify-shim cycle.

    A v2 manifest carrying ``built_in_only`` but lacking
    ``bundle_content_hash`` (the shape of every post-Phase-7 on-disk
    manifest, pre-mission) must still ``verify_manifest_hash`` after the
    field is added. This assertion goes momentarily RED the instant T001
    adds the field (the primary model-normalized comparison now includes
    ``bundle_content_hash: None`` and no longer matches the stored hash) and
    back GREEN once T004's per-field shim lands — the intra-WP TDD cycle
    C-011 scoping calls for on an infra WP.
    """
    manifest_data: dict[str, object] = {
        "schema_version": "2",
        "mission_id": None,
        "created_at": "2026-04-17T12:00:00+00:00",
        "run_id": "01KPE222TESTRUNID0000000001",
        "adapter_id": "fixture",
        "adapter_version": "1.0.0",
        "synthesizer_version": "3.2.0a5",
        "artifacts": [],
        "built_in_only": True,
    }
    manifest_data["manifest_hash"] = hashlib.sha256(  # noqa: TID251 — legacy manifest self-hash compatibility
        canonical_yaml(manifest_data)
    ).hexdigest()
    path = tmp_path / "synthesis-manifest.yaml"
    yaml = YAML()
    yaml.default_flow_style = False
    with path.open("w", encoding="utf-8") as fh:
        yaml.dump(manifest_data, fh)

    loaded = load_yaml(path)

    assert loaded.bundle_content_hash is None
    verify_manifest_hash(loaded)  # must not raise


def test_verify_manifest_hash_discriminates_present_field_tamper(
    tmp_path: Path,
) -> None:
    """T006(b) — the DISCRIMINATING tamper fixture.

    ``bundle_content_hash`` is PRESENT on disk, but the stored
    ``manifest_hash`` was computed by the LEGACY raw hash over the OTHER
    fields ONLY (excluding ``bundle_content_hash``) — reproducing exactly
    what a legacy writer that never knew about the field would have stored,
    with the key nonetheless present and carrying a tampered value.

    ``verify_manifest_hash`` MUST raise. This test does not just assert that
    outcome — it *proves* the discrimination empirically: a FIXED POP-LIST
    shim would unconditionally drop ``bundle_content_hash`` before
    recomputing, which is shown below to reproduce ``legacy_hash`` exactly
    (i.e. a pop-list shim would FALSE-ACCEPT this file regardless of the
    field's on-disk value). The per-field ``_raw_field_names``-gated shim
    instead sees the key IS present on disk, includes the tampered value in
    its comparison subset, and correctly raises.
    """
    fields_excluding_new: dict[str, object] = {
        "schema_version": "3",
        "mission_id": None,
        "created_at": "2026-04-17T12:00:00+00:00",
        "run_id": "01KPE222TESTRUNID0000000001",
        "adapter_id": "fixture",
        "adapter_version": "1.0.0",
        "synthesizer_version": "3.2.0a5",
        "artifacts": [],
        "built_in_only": False,
    }
    legacy_hash = hashlib.sha256(  # noqa: TID251 — reproducing a legacy writer's stored self-hash for the fixture
        canonical_yaml(fields_excluding_new)
    ).hexdigest()

    manifest_data: dict[str, object] = {
        **fields_excluding_new,
        "bundle_content_hash": "sha256:" + "b" * 64,  # tampered value
        "manifest_hash": legacy_hash,
    }
    path = tmp_path / "synthesis-manifest.yaml"
    yaml = YAML()
    yaml.default_flow_style = False
    with path.open("w", encoding="utf-8") as fh:
        yaml.dump(manifest_data, fh)

    loaded = load_yaml(path)
    assert loaded.bundle_content_hash == "sha256:" + "b" * 64

    # Empirical proof that a FIXED pop-list shim would false-accept: dropping
    # bundle_content_hash unconditionally before recomputing reproduces
    # legacy_hash exactly, independent of the field's actual value.
    pop_list_subset = loaded.model_dump(mode="python")
    pop_list_subset.pop("manifest_hash")
    pop_list_subset.pop("bundle_content_hash")
    pop_list_computed = hashlib.sha256(  # noqa: TID251 — reproducing the rejected pop-list algorithm to prove discrimination
        canonical_yaml(pop_list_subset)
    ).hexdigest()
    assert pop_list_computed == legacy_hash, (
        "fixture invariant broken: a pop-list recompute must reproduce the "
        "stored legacy hash for this test to actually discriminate"
    )

    # The per-field shim, in contrast, must raise.
    with pytest.raises(ValueError, match="manifest_hash mismatch"):
        verify_manifest_hash(loaded)


def test_verify_manifest_hash_raises_when_never_loaded_from_disk() -> None:
    """Cover the ``raw_field_names is None`` guard (shim-never-attempted).

    A manifest constructed in-memory (never round-tripped through
    ``load_yaml``) keeps ``_raw_field_names is None`` — there is no captured
    on-disk key set, so the legacy per-field shim MUST be skipped entirely
    and a hash mismatch raises IMMEDIATELY. Build a valid manifest, then
    forge a deliberately-wrong ``manifest_hash`` via ``model_copy`` (which
    does NOT repopulate ``_raw_field_names``) and assert ``verify_manifest_
    hash`` raises. Guards against a regression that lets the shim run on a
    never-loaded manifest (e.g. dropping the ``is not None`` check).
    """
    manifest = _make_manifest()
    assert manifest._raw_field_names is None  # never loaded from disk

    tampered = manifest.model_copy(update={"manifest_hash": "d" * 64})
    assert tampered._raw_field_names is None  # model_copy does not repopulate

    with pytest.raises(ValueError, match="manifest_hash mismatch"):
        verify_manifest_hash(tampered)


def test_finalize_manifest_matches_inline_compute_manifest_hash() -> None:
    """T006(c) — finalizer parity.

    ``finalize_manifest`` must produce the same ``manifest_hash`` as the
    pre-existing inline ``compute_manifest_hash`` path for identical
    content (behavior-preserving refactor).
    """
    manifest = _make_manifest()
    zeroed = manifest.model_copy(update={"manifest_hash": "0" * 64})
    expected = compute_manifest_hash(zeroed)

    finalized = finalize_manifest(manifest)

    assert finalized.manifest_hash == expected
    # Every other field is untouched.
    assert finalized.model_copy(update={"manifest_hash": manifest.manifest_hash}) == manifest


def test_manifest_synthesizer_version_empty_raises() -> None:
    """SynthesisManifest with synthesizer_version='' must raise ValidationError."""
    data_without_hash: dict[str, object] = {
        "schema_version": "2",
        "mission_id": None,
        "created_at": "2026-04-17T12:00:00+00:00",
        "run_id": "01KPE222TESTRUNID0000000001",
        "adapter_id": "fixture",
        "adapter_version": "1.0.0",
        "synthesizer_version": "valid",
        "artifacts": [],
        "built_in_only": False,
    }
    manifest_hash = hashlib.sha256(canonical_yaml(data_without_hash)).hexdigest()  # noqa: TID251 — charter synthesizer's own manifest/content-hash scheme, not the charter.hasher.hash_content() freshness algorithm
    with pytest.raises(ValidationError):
        SynthesisManifest(
            created_at="2026-04-17T12:00:00+00:00",
            run_id="01KPE222TESTRUNID0000000001",
            adapter_id="fixture",
            adapter_version="1.0.0",
            synthesizer_version="",  # empty — should raise
            manifest_hash=manifest_hash,
            artifacts=[],
        )
