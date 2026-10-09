"""Deterministic generator for the built-in pack's ``pack-manifest.yaml``.

Enumerates the doctrine artifacts shipped under ``packs/built-in/`` and emits
the single canonical :class:`~charter.offering.packs.pack_manifest.PackManifest`
(WP01 / IC-02). It emits **only** ``pack-manifest.yaml`` — never the authored
``pack.yaml`` (reserved for WP04) and never a ``pack_version`` field (the
built-in reads that from the authored descriptor, WP04).

Enumeration is **file-first** (DRG graph nodes carry no source path): for each
of the nine artifact kinds that ship a content directory
(:attr:`ArtifactKind.has_built_in_content_dir`) it globs the kind's files,
reads each artifact's canonical id, and records a
:class:`~charter.offering.packs.pack_manifest.Constituent`. Because every shipped
DRG artifact node is minted from exactly these files, enumerating the files
enumerates 100 % of the artifact nodes (SC-002).

Determinism (NFR-003 / T005): constituents are sorted by ``(kind, id)``;
``content_hash`` is taken over **LF-normalized** bytes (cross-platform, DIR-001)
via the single sanctioned hasher; and the volatile ``generated_at`` /
``generated_by`` provenance is excluded from the ``manifest_hash`` and the
byte-diff. ``generated_at`` is never populated here — it is still emitted as a
present null key in the serialized YAML, not dropped — and ``generated_by`` is
a constant, so re-generating an unchanged pack is byte-identical.
"""

from __future__ import annotations

from pathlib import Path

from ruamel.yaml import YAML

from charter.offering.packs.hashing import hash_content_bytes
from charter.offering.artifact_kinds import ArtifactKind
from charter.offering.packs.presets import enumerate_presets

from .pack_manifest import (
    Constituent,
    PackManifest,
    dump_pack_manifest_bytes,
    finalize_pack_manifest,
)

#: Name of the generated manifest file at the pack root.
MANIFEST_FILENAME = "pack-manifest.yaml"

#: Stable provenance marker. Kept constant (and ``generated_at`` left unset —
#: emitted as a present null key, excluded from the hash + byte-diff) so the
#: committed built-in manifest is byte-identical on every regeneration.
GENERATED_BY = "spec-kitty doctrine regenerate-graph"

#: The artifact id field is ``id`` for every kind except agent profiles, whose
#: canonical id lives under ``profile-id`` (codified by the DRG extractor).
_AGENT_PROFILE_ID_KEY = "profile-id"


def _lf_normalized(raw: bytes) -> bytes:
    """Normalize CRLF / CR line endings to LF for cross-platform hashes."""
    return raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def _read_artifact_id(path: Path, *, id_key: str) -> str:
    """Return the canonical id declared inside an artifact YAML file."""
    yaml = YAML(typ="safe")
    data = yaml.load(path.read_text(encoding="utf-8"))
    artifact_id = "" if not isinstance(data, dict) else str(data.get(id_key, "")).strip()
    if not artifact_id:
        raise ValueError(f"artifact file {path} is missing its {id_key!r} id field; cannot enumerate it as a pack constituent (fail-closed, no silent drop)")
    return artifact_id


def _enumerate_kind(pack_root: Path, kind: ArtifactKind) -> list[Constituent]:
    """Enumerate one kind's artifact files under *pack_root* as constituents."""
    kind_dir = pack_root / kind.plural
    if not kind_dir.is_dir():
        return []
    id_key = _AGENT_PROFILE_ID_KEY if kind is ArtifactKind.AGENT_PROFILE else "id"
    constituents: list[Constituent] = []
    # rglob: tactics / styleguides / toolguides / assets nest under subdirs.
    for path in kind_dir.rglob(kind.glob_pattern):
        if not path.is_file():
            continue
        raw = path.read_bytes()
        constituents.append(
            Constituent(
                kind=kind,
                id=_read_artifact_id(path, id_key=id_key),
                path=path.relative_to(pack_root).as_posix(),
                content_hash=hash_content_bytes(_lf_normalized(raw)),
                provenance_path=None,
            )
        )
    return constituents


def enumerate_constituents(pack_root: Path) -> list[Constituent]:
    """Return every built-in artifact as a constituent (unsorted).

    Covers exactly the nine kinds with a shipped content directory
    (:attr:`ArtifactKind.has_built_in_content_dir`); graph-only kinds
    (``mission_step_contract``, ``template``, ``anti_pattern``) and the
    non-artifact DRG node kinds (``mission_type``, ``action``) have no
    standalone artifact file and are intentionally not constituents.
    """
    constituents: list[Constituent] = []
    for kind in ArtifactKind:
        if kind.has_built_in_content_dir:
            constituents.extend(_enumerate_kind(pack_root, kind))
    return constituents


def build_builtin_manifest(pack_root: Path) -> PackManifest:
    """Build (without writing) the built-in pack manifest for *pack_root*."""
    manifest = PackManifest(
        generated_by=GENERATED_BY,
        source_type="built-in",
        constituents=enumerate_constituents(pack_root),
        presets=enumerate_presets(pack_root) or None,
    )
    return finalize_pack_manifest(manifest)


def generate_builtin_manifest(pack_root: Path) -> PackManifest:
    """Generate and write ``pack-manifest.yaml`` under *pack_root*.

    Writes only the generated manifest — never ``pack.yaml`` and never a
    ``pack_version`` field. Returns the finalized manifest.
    """
    pack_root = Path(pack_root)
    manifest = build_builtin_manifest(pack_root)
    (pack_root / MANIFEST_FILENAME).write_bytes(dump_pack_manifest_bytes(manifest))
    return manifest


def builtin_manifest_is_fresh(pack_root: Path) -> bool:
    """Return whether the committed built-in manifest matches a fresh build.

    Byte-compares the freshly-built manifest against the committed
    ``pack-manifest.yaml`` (both provenance-stable), the operator-facing twin of
    the DRG graph freshness gate. Missing committed file → not fresh.
    """
    pack_root = Path(pack_root)
    committed = pack_root / MANIFEST_FILENAME
    if not committed.is_file():
        return False
    return committed.read_bytes() == dump_pack_manifest_bytes(build_builtin_manifest(pack_root))


__all__ = [
    "MANIFEST_FILENAME",
    "GENERATED_BY",
    "enumerate_constituents",
    "build_builtin_manifest",
    "generate_builtin_manifest",
    "builtin_manifest_is_fresh",
]
