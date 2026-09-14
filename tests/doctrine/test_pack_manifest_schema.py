"""Unit tests for the unified ``pack-manifest`` schema (WP01 / T001).

Covers the :class:`PackManifest` / :class:`Constituent` / :class:`CharterProfile`
models, the single-hasher reuse, deterministic ``(kind, id)`` ordering, the
``generated_at`` / ``generated_by`` hash exclusion, and the reader round-trip.
All synthetic (tmp_path only) — no on-disk corpus is read.
"""

from __future__ import annotations

import json

import pytest
from pydantic import TypeAdapter, ValidationError

from charter.offering.artifact_kinds import ArtifactKind
from specify_cli.doctrine.pack_manifest import (
    HASH_EXCLUDED_FIELDS,
    SCHEMA_VERSION,
    CharterProfile,
    Constituent,
    PackManifest,
    compute_pack_manifest_hash,
    dump_pack_manifest_bytes,
    finalize_pack_manifest,
    load_pack_manifest,
    sort_constituents,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast, pytest.mark.doctrine]


def _c(kind: ArtifactKind, cid: str, content_hash: str = "h") -> Constituent:
    return Constituent(kind=kind, id=cid, path=f"{kind.plural}/{cid}.yaml", content_hash=content_hash)


class TestConstituent:
    def test_kind_widened_to_full_artifact_kind_universe(self) -> None:
        # Every ArtifactKind is accepted — not just the charter 3-kind literal.
        for kind in ArtifactKind:
            c = _c(kind, "x")
            assert c.kind is kind

    def test_provenance_path_optional_and_defaults_none(self) -> None:
        assert _c(ArtifactKind.DIRECTIVE, "d").provenance_path is None
        c = Constituent(
            kind=ArtifactKind.DIRECTIVE, id="d", path="p", content_hash="h", provenance_path="x"
        )
        assert c.provenance_path == "x"

    def test_extra_fields_forbidden(self) -> None:
        with pytest.raises(ValidationError):
            Constituent(kind=ArtifactKind.DIRECTIVE, id="d", path="p", content_hash="h", bogus=1)  # type: ignore[call-arg]


class TestOrderingAndHash:
    def test_sort_is_by_kind_then_id(self) -> None:
        cs = [
            _c(ArtifactKind.TACTIC, "b"),
            _c(ArtifactKind.DIRECTIVE, "z"),
            _c(ArtifactKind.DIRECTIVE, "a"),
        ]
        ordered = sort_constituents(cs)
        assert [(c.kind.value, c.id) for c in ordered] == [
            ("directive", "a"),
            ("directive", "z"),
            ("tactic", "b"),
        ]

    def test_finalize_sets_64_char_hash_and_orders(self) -> None:
        m = finalize_pack_manifest(
            PackManifest(constituents=[_c(ArtifactKind.TACTIC, "b"), _c(ArtifactKind.DIRECTIVE, "a")])
        )
        assert m.manifest_hash is not None and len(m.manifest_hash) == 64
        assert [c.id for c in m.constituents] == ["a", "b"]

    def test_hash_excludes_generated_provenance(self) -> None:
        assert frozenset(
            {"manifest_hash", "generated_at", "generated_by"}
        ) == HASH_EXCLUDED_FIELDS
        base = PackManifest(constituents=[_c(ArtifactKind.DIRECTIVE, "a")])
        h1 = compute_pack_manifest_hash(base.model_copy(update={"generated_by": "x", "generated_at": "t1"}))
        h2 = compute_pack_manifest_hash(base.model_copy(update={"generated_by": "y", "generated_at": "t2"}))
        assert h1 == h2

    def test_hash_is_order_independent(self) -> None:
        a = finalize_pack_manifest(
            PackManifest(constituents=[_c(ArtifactKind.DIRECTIVE, "a"), _c(ArtifactKind.TACTIC, "b")])
        )
        b = finalize_pack_manifest(
            PackManifest(constituents=[_c(ArtifactKind.TACTIC, "b"), _c(ArtifactKind.DIRECTIVE, "a")])
        )
        assert a.manifest_hash == b.manifest_hash

    def test_hash_changes_when_a_constituent_changes(self) -> None:
        a = finalize_pack_manifest(PackManifest(constituents=[_c(ArtifactKind.DIRECTIVE, "a", "h1")]))
        b = finalize_pack_manifest(PackManifest(constituents=[_c(ArtifactKind.DIRECTIVE, "a", "h2")]))
        assert a.manifest_hash != b.manifest_hash


class TestSchemaVersionAndRoundTrip:
    def test_default_schema_version(self) -> None:
        assert PackManifest().schema_version == SCHEMA_VERSION

    def test_dump_load_round_trip(self, tmp_path) -> None:
        m = finalize_pack_manifest(
            PackManifest(
                generated_by="t",
                source_type="built-in",
                constituents=[_c(ArtifactKind.DIRECTIVE, "a"), _c(ArtifactKind.TACTIC, "b")],
            )
        )
        path = tmp_path / "pack-manifest.yaml"
        path.write_bytes(dump_pack_manifest_bytes(m))
        loaded = load_pack_manifest(path)
        assert loaded.manifest_hash == m.manifest_hash
        assert [(c.kind, c.id) for c in loaded.constituents] == [
            (ArtifactKind.DIRECTIVE, "a"),
            (ArtifactKind.TACTIC, "b"),
        ]

    def test_dump_is_byte_deterministic(self) -> None:
        m = finalize_pack_manifest(
            PackManifest(generated_by="t", constituents=[_c(ArtifactKind.DIRECTIVE, "a")])
        )
        first = dump_pack_manifest_bytes(m)
        second = dump_pack_manifest_bytes(m)
        assert first == second

    def test_builtin_variant_omits_fetched_nulls_on_all_pydantic_paths(self) -> None:
        manifest = PackManifest(source_type="built-in", constituents=[])
        forbidden = {"pack_version", "etag", "artifact_counts"}

        assert forbidden.isdisjoint(manifest.model_dump())
        assert forbidden.isdisjoint(json.loads(manifest.model_dump_json()))
        assert forbidden.isdisjoint(TypeAdapter(PackManifest).dump_python(manifest))

    def test_generated_variant_retains_null_pack_version(self) -> None:
        manifest = PackManifest(source_type="https", artifact_counts={})

        assert manifest.model_dump()["pack_version"] is None
        assert json.loads(manifest.model_dump_json())["pack_version"] is None
        assert TypeAdapter(PackManifest).dump_python(manifest)["pack_version"] is None

    def test_serialization_schema_preserves_validation_field_contract(self) -> None:
        validation = PackManifest.model_json_schema(mode="validation")
        serialization = PackManifest.model_json_schema(mode="serialization")
        adapter = TypeAdapter(PackManifest).json_schema(mode="serialization")

        assert set(serialization["properties"]) == set(validation["properties"])
        assert serialization["additionalProperties"] is False
        assert set(adapter["properties"]) == set(validation["properties"])
        assert adapter["additionalProperties"] is False

    def test_non_null_provenance_changes_hash_without_artifact_counts(self) -> None:
        first = PackManifest(
            source_type="custom",
            pack_version="v1",
            etag="e1",
            constituents=[_c(ArtifactKind.DIRECTIVE, "a")],
        )
        second = first.model_copy(update={"pack_version": "v2", "etag": "e2"})

        assert first.model_dump()["pack_version"] == "v1"
        assert first.model_dump()["etag"] == "e1"
        assert compute_pack_manifest_hash(first) != compute_pack_manifest_hash(second)


class TestCharterProfile:
    def test_full_field_set_including_built_in_only(self) -> None:
        p = CharterProfile(
            mission_id="m",
            bundle_content_hash="bh",
            synthesizer_version="1.2.3",
            run_id="r",
            adapter_id="a",
            adapter_version="v",
            created_at="t",
            schema_version="3",
            built_in_only=True,
        )
        assert p.built_in_only is True
        assert p.model_dump()["built_in_only"] is True
