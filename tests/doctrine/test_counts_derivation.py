"""Derived per-kind pack counts + reader pin (WP01 / T006, T007).

T006 retires the *stored* per-kind ``artifact_counts`` block as the authority in
favour of the derived view (``counts_by_kind`` over ``constituents``), with
transitional precedence (derive-when-present, else stored fallback) so a pack
whose generator has not yet run does not read ``0``.

T007 pins the two genuine **pack** per-kind counts readers green:
``pack_assembler._has_recognisable_pack_manifest`` and
``cli/commands/_profile_health_render._render_doctrine_pack`` — proving the
derived view yields the identical ``dict[str, int]`` they consume.

Deliberately NOT pinned: ``_doctrine_collect._count_pack_artifacts`` (an
independent on-disk counter that never reads the stored block — a "derived ==
stored" assertion there is vacuous, paula SF-1) and the ``dossier``
``{total, required, required_present}`` counts (a different domain fed by
``snapshot.total_artifacts`` — explicitly out of scope).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from charter.offering.artifact_kinds import ArtifactKind
from charter.offering.packs.pack_manifest import (
    Constituent,
    counts_by_kind,
    resolve_counts,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast, pytest.mark.doctrine]


def _cons() -> list[Constituent]:
    def c(kind: ArtifactKind, cid: str) -> Constituent:
        return Constituent(kind=kind, id=cid, path=f"{kind.plural}/{cid}.yaml", content_hash="h")

    return [
        c(ArtifactKind.DIRECTIVE, "d1"),
        c(ArtifactKind.DIRECTIVE, "d2"),
        c(ArtifactKind.TACTIC, "t1"),
        c(ArtifactKind.STYLEGUIDE, "s1"),
    ]


#: The stored ``artifact_counts`` an org snapshot would persist for ``_cons()``
#: (plural bucket keys — the existing on-disk convention the readers consume).
_STORED = {"directives": 2, "tactics": 1, "styleguides": 1}


class TestDerivation:
    def test_counts_by_kind_uses_plural_keys(self) -> None:
        assert counts_by_kind(_cons()) == _STORED

    def test_derived_equals_stored_values(self) -> None:
        derived = counts_by_kind(_cons())
        assert derived == _STORED
        assert all(derived[k] == _STORED[k] for k in _STORED)

    def test_resolve_counts_precedence(self) -> None:
        # constituents present (even empty) → derive
        assert resolve_counts([], {"directives": 9}) == {}
        assert resolve_counts(_cons(), {"directives": 9}) == _STORED
        # constituents absent (legacy manifest) → stored fallback (not 0)
        assert resolve_counts(None, {"directives": 9}) == {"directives": 9}
        assert resolve_counts(None, None) == {}


class TestPinPackAssemblerReader:
    """``_has_recognisable_pack_manifest`` accepts a manifest carrying derived counts."""

    def test_recognises_manifest_with_derived_counts(self, tmp_path) -> None:
        import yaml

        from charter.offering.packs.pack_assembler import _has_recognisable_pack_manifest

        payload = {
            "pack_version": "1.0.0",
            "fetched_at": "2026-08-16T00:00:00Z",
            "source_type": "assemble",
            "source_url": "",
            "artifact_counts": counts_by_kind(_cons()),
        }
        (tmp_path / "pack-manifest.yaml").write_text(yaml.safe_dump(payload), encoding="utf-8")
        assert _has_recognisable_pack_manifest(tmp_path) is True


class TestPinProfileHealthReader:
    """``_render_doctrine_pack`` consumes the derived counts identically."""

    def test_render_consumes_derived_counts(self) -> None:
        from specify_cli.cli.commands._profile_health_render import _render_doctrine_pack

        pack_entry = {
            "name": "acme",
            "snapshot_present": True,
            "pack_version": "1.0.0",
            "is_git_pack": False,
            "artifact_counts": counts_by_kind(_cons()),
            "pack_health": {"healthy": True},
        }
        # The reader iterates ``artifact_counts.items()`` — feeding the derived
        # dict must not raise and must expose the same per-kind items.
        _render_doctrine_pack(pack_entry, 0)
        assert dict(pack_entry["artifact_counts"]) == _STORED


class TestSnapshotWriteStaysRecognisable:
    """T006 write side: snapshot output (routed through resolve_counts) stays
    recognisable to the pinned pack_assembler reader (NFR-002)."""

    def test_write_pack_manifest_is_recognisable(self, tmp_path) -> None:
        from charter.offering.packs.pack_assembler import _has_recognisable_pack_manifest
        from charter.offering.packs.pack_manifest import write_pack_manifest

        local = tmp_path / "snap"
        (local / "directives").mkdir(parents=True)
        (local / "directives" / "a.directive.yaml").write_text("id: A\n", encoding="utf-8")
        write_pack_manifest(local, pack_version="git", etag=None, source_url="https://x/y", source_type="git")

        manifest = Path(local) / "pack-manifest.yaml"
        assert manifest.is_file()
        assert "artifact_counts" in manifest.read_text(encoding="utf-8")
        assert _has_recognisable_pack_manifest(local) is True
