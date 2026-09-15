"""Charter-manifest absorption + reader-surface pin (WP01 / T002, T003).

T002 proves the charter ``SynthesisManifest`` absorbs losslessly into the
unified :class:`PackManifest` — the full charter field-set (including the
load-bearing ``built_in_only``) lands on :class:`CharterProfile` and every
artifact's ``provenance_path`` survives on its :class:`Constituent`.

T003 pins the charter-manifest reader surface green. Those readers
(``doctrine_synthesizer/{apply,provenance,__init__}``,
``charter_runtime/freshness/computer``, ``charter_runtime/preflight/runner``,
``charter_runtime/lint/findings``, ``cli/commands/charter_bundle``,
``doctrine/versioning``, and the two ``m_3_2_0rc35_charter_*`` migrations) all
depend solely on the public ``charter.activation.synthesizer.manifest`` contract
(``SynthesisManifest`` schema, ``load_yaml`` / ``dump_yaml``,
``compute_manifest_hash`` / ``finalize_manifest`` / ``verify_manifest_hash``).
Absorption must not perturb that contract, so these tests assert the on-disk
format round-trips unchanged and the hasher refactor is behaviour-preserving.
Read-only: no reader module is edited.
"""

from __future__ import annotations

import pytest

from charter.activation.synthesizer.manifest import (
    ManifestArtifactEntry,
    SynthesisManifest,
    compute_manifest_hash,
    dump_yaml,
    finalize_manifest,
    load_yaml,
    verify_manifest_hash,
)
from charter.offering.artifact_kinds import ArtifactKind
from specify_cli.doctrine.pack_manifest import (
    CharterProfile,
    absorb_synthesis_manifest,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast, pytest.mark.doctrine]

_CHARTER_FIELDS = (
    "mission_id",
    "bundle_content_hash",
    "synthesizer_version",
    "run_id",
    "adapter_id",
    "adapter_version",
    "created_at",
    "schema_version",
    "built_in_only",
)


def _entry(kind: str, slug: str) -> ManifestArtifactEntry:
    return ManifestArtifactEntry(
        kind=kind,
        slug=slug,
        path=f".kittify/doctrine/{kind}/{slug}.yaml",
        provenance_path=f".kittify/charter/provenance/{kind}/{slug}.yaml",
        content_hash="c" * 64,
    )


def _manifest(*, built_in_only: bool = False) -> SynthesisManifest:
    return finalize_manifest(
        SynthesisManifest(
            mission_id="mission-01",
            created_at="2026-08-16T00:00:00Z",
            run_id="01RUN",
            adapter_id="adp",
            adapter_version="9.9",
            synthesizer_version="1.0.0",
            bundle_content_hash="sha256:abc",
            manifest_hash="0" * 64,
            built_in_only=built_in_only,
            artifacts=[_entry("directive", "d1"), _entry("tactic", "t1"), _entry("styleguide", "s1")],
        )
    )


class TestAbsorption:
    def test_all_charter_fields_land_on_profile(self) -> None:
        sm = _manifest(built_in_only=True)
        pm = absorb_synthesis_manifest(sm)
        assert isinstance(pm.charter, CharterProfile)
        profile = pm.charter.model_dump()
        for field in _CHARTER_FIELDS:
            assert profile[field] == getattr(sm, field), field
        # The load-bearing flag is not silently coerced.
        assert pm.charter.built_in_only is True

    def test_constituents_widen_kind_and_preserve_provenance(self) -> None:
        sm = _manifest()
        pm = absorb_synthesis_manifest(sm)
        by_id = {c.id: c for c in pm.constituents}
        assert set(by_id) == {"d1", "t1", "s1"}
        assert by_id["d1"].kind is ArtifactKind.DIRECTIVE
        assert by_id["s1"].kind is ArtifactKind.STYLEGUIDE
        for entry in sm.artifacts:
            c = by_id[entry.slug]
            assert c.provenance_path == entry.provenance_path
            assert c.content_hash == entry.content_hash
            assert c.path == entry.path

    def test_nothing_dropped_field_count(self) -> None:
        # CharterProfile carries exactly the charter-only field-set (no gaps).
        assert set(CharterProfile.model_fields) == set(_CHARTER_FIELDS)

    def test_absorbed_manifest_is_finalized(self) -> None:
        pm = absorb_synthesis_manifest(_manifest())
        assert pm.manifest_hash is not None and len(pm.manifest_hash) == 64


class TestReaderContractUnchanged:
    """T003: the public contract every pinned reader depends on stays green."""

    def test_on_disk_format_round_trips_unchanged(self, tmp_path) -> None:
        # dump_yaml uses a PathGuard; route it through a permissive stub that
        # writes plain bytes so we exercise the real serialize + load path.
        class _Guard:
            def write_text(self, path, text, *, encoding, caller):  # noqa: ANN001
                path.write_text(text, encoding=encoding)

        sm = _manifest()
        path = tmp_path / "synthesis-manifest.yaml"
        dump_yaml(sm, path, _Guard())  # type: ignore[arg-type]
        reloaded = load_yaml(path)
        assert reloaded.model_dump() == sm.model_dump()
        # The self-hash still verifies after a real dump/load round-trip.
        verify_manifest_hash(reloaded)

    def test_hasher_refactor_is_behaviour_preserving(self) -> None:
        # finalize_manifest + compute_manifest_hash must agree, and the hash is
        # the canonical SHA over all fields except manifest_hash.
        sm = _manifest()
        assert compute_manifest_hash(sm) == sm.manifest_hash
        # Mapping input path (used by readers) resolves to the same digest.
        data = sm.model_dump(mode="python")
        assert compute_manifest_hash(data) == sm.manifest_hash

    def test_built_in_only_survives_disk_round_trip(self, tmp_path) -> None:
        class _Guard:
            def write_text(self, path, text, *, encoding, caller):  # noqa: ANN001
                path.write_text(text, encoding=encoding)

        sm = _manifest(built_in_only=True)
        path = tmp_path / "synthesis-manifest.yaml"
        dump_yaml(sm, path, _Guard())  # type: ignore[arg-type]
        assert load_yaml(path).built_in_only is True
