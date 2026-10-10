"""Unified ``pack-manifest`` schema, reader, and derived per-kind counts.

This module defines the **single canonical** pack-metadata manifest schema that
replaces the two divergent formats that shipped previously (WP01 / IC-01):

* per-kind ``artifact_counts`` for org / fetched packs
  (:func:`write_pack_manifest`), and
* the enumerated ``artifacts[]`` list of the charter bundle
  (``charter.activation.synthesizer.manifest.SynthesisManifest``).

The enumerated shape is promoted to the canonical ``constituents[]`` inventory.
A charter pack additionally carries a :class:`CharterProfile` block preserving
the **entire** charter-only field-set of ``SynthesisManifest`` so no working
field is dropped during absorption (PP-M2).

Design references:
* ADR ``docs/adr/3.x/2026-08-16-1-pack-metadata-manifest-unification.md``
* ``kitty-specs/pack-metadata-manifest-unification-01M052PT/data-model.md``

Hashing is delegated to the **single** canonical manifest hasher
(:func:`charter.offering.packs.hashing.hash_manifest_payload`) — this module
never introduces a second SHA-256 implementation (RR-SF2 / T005). The
``generated_at`` / ``generated_by`` provenance fields are excluded from both
the ``manifest_hash`` and the byte-diff assertion so re-generating an unchanged
pack is byte-identical (NFR-003).
"""

from __future__ import annotations

import hashlib
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any
from urllib.parse import SplitResult, urlsplit, urlunsplit

from pydantic import (
    BaseModel,
    ConfigDict,
    GetJsonSchemaHandler,
    SerializerFunctionWrapHandler,
    model_serializer,
)
from ruamel.yaml import YAML

from charter.offering.artifact_kinds import ArtifactKind
from charter.offering.packs.hashing import hash_manifest_payload
from charter.offering.packs.presets import PresetEntry, enumerate_presets
from charter.offering.yaml_utils import canonical_yaml
from kernel.clock import now_utc_stamp

#: Current unified pack-manifest schema version (DIR-018 shape gate).
SCHEMA_VERSION = "1"

#: Fields excluded from ``manifest_hash`` **and** the deterministic byte-diff
#: assertion. ``manifest_hash`` is excluded because it is the self field;
#: ``generated_at`` / ``generated_by`` are volatile provenance that must not
#: perturb a re-generation of otherwise-identical content (NFR-003).
HASH_EXCLUDED_FIELDS: frozenset[str] = frozenset({"manifest_hash", "generated_at", "generated_by"})

_FETCHED_PROVENANCE_FIELDS: frozenset[str] = frozenset(
    {
        "pack_version",
        "etag",
        "source_fingerprint",
        "source_uses_query",
        "snapshot_sha256",
        "artifact_counts",
    }
)

_GENERATED_PACK_SOURCE_TYPES: frozenset[str] = frozenset({"api", "artifactory", "assemble", "git", "https"})


class Constituent(BaseModel):
    """One artifact enumerated in a pack manifest (data-model.md § Constituent)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: ArtifactKind
    """Canonical artifact kind — widened from the charter manifest's 3-kind
    literal to the shared :class:`~charter.offering.artifact_kinds.ArtifactKind` so the
    built-in pack's kinds pass the shared model (PP-S4)."""

    id: str
    """Canonical artifact id within its kind (URN local part or bare id)."""

    path: str
    """POSIX repo-relative path to the artifact source file."""

    content_hash: str
    """SHA-256 hex digest over the **LF-normalized** artifact bytes
    (cross-platform-stable, DIR-001 / #2539)."""

    provenance_path: str | None = None
    """Repo-relative provenance sidecar path. Required for charter
    constituents (relocated from ``ManifestArtifactEntry.provenance_path``);
    ``None`` for non-charter packs."""


class CharterProfile(BaseModel):
    """Charter-only manifest field-set carried on a charter pack (PP-M2).

    Carries the **entire** charter-only contract of
    ``charter.activation.synthesizer.manifest.SynthesisManifest`` so absorption drops no
    working field. ``built_in_only`` is load-bearing across the
    ``charter_runtime`` freshness / preflight / lint readers and MUST survive.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    mission_id: str | None = None
    bundle_content_hash: str | None = None
    synthesizer_version: str
    run_id: str
    adapter_id: str
    adapter_version: str
    created_at: str
    schema_version: str
    built_in_only: bool = False


class PackManifest(BaseModel):
    """The single canonical generated pack manifest (``pack-manifest.yaml``)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str = SCHEMA_VERSION
    generated_by: str | None = None
    generated_at: str | None = None
    source_url: str | None = None
    source_type: str | None = None
    fetched_at: str | None = None
    pack_version: str | None = None
    etag: str | None = None
    source_fingerprint: str | None = None
    source_uses_query: bool | None = None
    snapshot_sha256: str | None = None
    artifact_counts: dict[str, int] | None = None
    manifest_hash: str | None = None
    constituents: list[Constituent] | None = None
    charter: CharterProfile | None = None
    presets: list[PresetEntry] | None = None
    """Activation presets the pack ships (``presets/<name>.yaml``), sorted by
    name. ``None`` (and absent from the serialized manifest) for a pack without
    presets, so such a manifest stays byte-identical (FR-019)."""

    @model_serializer(mode="wrap")
    def _serialize_manifest(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        """Serialize manifest variants consistently on every Pydantic path."""
        data: dict[str, Any] = handler(self)
        for field_name in _FETCHED_PROVENANCE_FIELDS:
            if data.get(field_name) is not None:
                continue
            if field_name == "pack_version" and self.source_type in _GENERATED_PACK_SOURCE_TYPES:
                continue
            data.pop(field_name, None)
        if self.constituents is None:
            data.pop("constituents", None)
        if self.presets is None:
            data.pop("presets", None)
        return data

    @classmethod
    def __get_pydantic_json_schema__(cls, core_schema: Any, handler: GetJsonSchemaHandler) -> dict[str, Any]:
        """Keep the declared serialization schema as strict as validation."""
        schema = dict(core_schema)
        if handler.mode == "serialization":
            schema.pop("serialization", None)
        return handler(schema)


# ---------------------------------------------------------------------------
# Determinism + hashing
# ---------------------------------------------------------------------------


def _manifest_payload(manifest: PackManifest) -> dict[str, object]:
    """Return canonical data without leaking fetched-only null fields.

    Built-in and charter manifests keep their historical bytes and hashes.
    Generated fetched/assembled variants retain an explicit
    ``pack_version: null`` required by pack recognisability. Non-null
    provenance is always retained and therefore bound into the manifest hash.
    """
    return manifest.model_dump(mode="json")


def sort_constituents(constituents: Sequence[Constituent]) -> list[Constituent]:
    """Sort constituents deterministically by ``(kind, id)`` (T005)."""
    return sorted(constituents, key=lambda c: (c.kind.value, c.id))


def compute_pack_manifest_hash(manifest: PackManifest) -> str:
    """Compute ``manifest_hash`` via the single canonical hasher.

    Delegates to :func:`charter.offering.packs.hashing.hash_manifest_payload`
    (the one SHA-256 + ``canonical_yaml`` primitive) over every field except
    :data:`HASH_EXCLUDED_FIELDS`. ``mode="json"`` normalizes the
    :class:`ArtifactKind` enum members to their string values so the payload is
    plain data.
    """
    data = _manifest_payload(manifest)
    return hash_manifest_payload(data, exclude_keys=HASH_EXCLUDED_FIELDS)


def finalize_pack_manifest(manifest: PackManifest) -> PackManifest:
    """Return a copy of *manifest* with ``manifest_hash`` recomputed.

    Constituents are normalized to canonical ``(kind, id)`` order first so the
    hash and serialized bytes are order-independent of the caller.
    """
    ordered_constituents = None if manifest.constituents is None else sort_constituents(manifest.constituents)
    ordered = manifest.model_copy(update={"constituents": ordered_constituents})
    return ordered.model_copy(update={"manifest_hash": compute_pack_manifest_hash(ordered)})


# ---------------------------------------------------------------------------
# Serialization + reader
# ---------------------------------------------------------------------------


def dump_pack_manifest_bytes(manifest: PackManifest) -> bytes:
    """Serialize *manifest* to deterministic canonical YAML bytes.

    Reuses :func:`charter.activation.synthesizer.synthesize_pipeline.canonical_yaml` (the
    single source of truth for YAML serialization) so the bytes are stable
    under identical inputs. Constituents are canonically ordered first.
    """
    ordered_constituents = None if manifest.constituents is None else sort_constituents(manifest.constituents)
    ordered = manifest.model_copy(update={"constituents": ordered_constituents})
    serialized: bytes = canonical_yaml(_manifest_payload(ordered))
    return serialized


def load_pack_manifest(path: Path) -> PackManifest:
    """Read and validate a ``pack-manifest.yaml`` from *path*."""
    yaml = YAML(typ="safe")
    raw = yaml.load(Path(path).read_text(encoding="utf-8"))
    return PackManifest.model_validate(raw)


# ---------------------------------------------------------------------------
# Derived per-kind counts (IC-03)
# ---------------------------------------------------------------------------


def counts_by_kind(constituents: Sequence[Constituent]) -> dict[str, int]:
    """Return per-kind artifact counts derived from *constituents*.

    Keyed by the artifact kind's **plural** directory name (``directives``,
    ``tactics``, …), shaped like the retired stored ``artifact_counts`` block
    (IC-03 / T006). Kinds with zero constituents are simply absent, matching the
    stored convention.

    **NOT count-equivalent to the stored block across every kind-domain.** The
    derived view only ever contains kinds present in ``constituents``, and the
    built-in enumeration (``builtin_manifest.enumerate_constituents``) *excludes*
    graph-only kinds (``mission_step_contract``, ``template``, ``anti_pattern``)
    and never emits a ``drg_fragments`` bucket, whereas the stored view
    (:func:`count_snapshot_artifacts`) includes ``mission_step_contracts`` and folds
    DRG fragments into ``drg_fragments``. So for a pack carrying those kinds this
    is *not* a silent drop-in — the deferred integration WP must reconcile the two
    enumeration domains **before** flipping any snapshot from stored to derived
    (:func:`resolve_counts`), or those buckets vanish silently.
    """
    counts: Counter[str] = Counter()
    for constituent in constituents:
        counts[constituent.kind.plural] += 1
    return dict(counts)


def resolve_counts(
    constituents: Sequence[Constituent] | None,
    stored_counts: Mapping[str, int] | None,
) -> dict[str, int]:
    """Per-kind counts with transitional precedence (IC-03 / PP-S1).

    Derive from ``constituents`` when the unified manifest carries them (a
    non-``None`` list, even if empty); otherwise fall back to the stored
    ``artifact_counts`` block (migration input) so a pack whose generator has
    not yet run does not read ``0``.

    **Caution (deferred integration):** the two branches are not count-equivalent
    for graph-only kinds / DRG fragments — see :func:`counts_by_kind`. Flipping a
    live consumer from the stored branch to the derived branch is a behaviour
    change for such packs, not a no-op; reconcile the enumeration domains first.
    """
    if constituents is not None:
        return counts_by_kind(constituents)
    return {str(k): int(v) for k, v in (stored_counts or {}).items()}


# ---------------------------------------------------------------------------
# Fetched / assembled pack manifest writer (research A.3 #6)
# ---------------------------------------------------------------------------

#: Name of the generated manifest file at a pack (or snapshot) root.
_PACK_MANIFEST_FILENAME = "pack-manifest.yaml"

#: Recognised artifact subdirectories per the pack-layout contract: every kind
#: that resolves through a layered (built-in + org + project) repository plus the
#: ``drg`` fragment directory. Derived from the single :class:`ArtifactKind`
#: authority via
#: :attr:`~charter.offering.artifact_kinds.ArtifactKind.has_layered_repository`
#: rather than hand-listed, so it cannot drift from the enum; the ``"drg"`` leaf
#: is not a kind, so it is unioned in explicitly.
#:
#: Keyed on ``has_layered_repository`` (11 kinds: the 10 content-dir kinds plus
#: ``mission_step_contracts``), NOT ``has_built_in_content_dir``: an org or
#: fetched pack may ship ``mission_step_contracts/`` even though the built-in
#: pack has no such directory, and keying on the built-in axis made a
#: contracts-only snapshot unrecognised and dropped its count bucket.
RECOGNISED_ARTIFACT_DIRS: frozenset[str] = frozenset(k.plural for k in ArtifactKind if k.has_layered_repository) | {"drg"}


def write_pack_manifest(
    local_path: Path,
    *,
    pack_version: str | None,
    etag: str | None,
    source_url: str,
    source_type: str,
) -> None:
    """Write ``pack-manifest.yaml`` to ``local_path``.

    The manifest is read-only metadata for tooling and humans. Credentials,
    query parameters, and fragments in ``source_url`` are stripped before
    persistence. The writer takes primitives only, so the pack model never
    depends on the fetch adapters that produce them.
    """
    local_path = Path(local_path)
    safe_source_url = strip_source_credentials(source_url)
    manifest = finalize_pack_manifest(
        PackManifest(
            pack_version=pack_version,
            fetched_at=_iso_now(),
            source_type=source_type,
            source_url=safe_source_url,
            source_fingerprint=source_fingerprint(safe_source_url),
            source_uses_query=_source_uses_query(source_url),
            snapshot_sha256=snapshot_sha256(local_path),
            artifact_counts=resolve_counts(None, count_snapshot_artifacts(local_path)),
            etag=etag,
            presets=enumerate_presets(local_path) or None,
        )
    )
    (local_path / _PACK_MANIFEST_FILENAME).write_bytes(dump_pack_manifest_bytes(manifest))


def count_snapshot_artifacts(snapshot_dir: Path) -> dict[str, int]:
    """Per-bucket artifact counts of a fetched snapshot (the stored count view)."""
    counts: dict[str, int] = {}
    if not snapshot_dir.exists():
        return counts
    for entry in snapshot_dir.iterdir():
        if not entry.is_dir() or entry.name not in RECOGNISED_ARTIFACT_DIRS:
            continue
        bucket = entry.name if entry.name != "drg" else "drg_fragments"
        counts[bucket] = sum(1 for _ in entry.rglob("*.yaml"))
    # FR-014: the sharded built-in layout (mission #2680, WP05) ships DRG
    # fragments as top-level ``*.graph.yaml`` files rather than under a ``drg/``
    # directory. Fold them into the same ``drg_fragments`` bucket so a sharded
    # doctrine tree categorises identically to the monolith / ``drg/``-dir
    # layouts. Additive: no current snapshot ships top-level fragments.
    fragment_count = sum(1 for _ in snapshot_dir.glob("*.graph.yaml"))
    if fragment_count:
        counts["drg_fragments"] = counts.get("drg_fragments", 0) + fragment_count
    return counts


def strip_source_credentials(url: str) -> str:
    """Return a remote URL safe for durable metadata and comparisons."""
    if not url:
        return ""
    parsed = safe_urlsplit(url)
    if parsed is None:
        return ""
    if parsed.scheme not in {"http", "https"}:
        return url
    hostname = parsed.hostname or ""
    if ":" in hostname:
        hostname = f"[{hostname}]"
    try:
        port = parsed.port
    except ValueError:
        port = None
    netloc = f"{hostname}:{port}" if port is not None else hostname
    return urlunsplit((parsed.scheme, netloc, parsed.path, "", ""))


def safe_urlsplit(url: str) -> SplitResult | None:
    """Parse one URL without leaking malformed-authority exceptions."""
    try:
        return urlsplit(url)
    except ValueError:
        return None


def _source_uses_query(url: str) -> bool:
    """Return query presence without raising for malformed source URLs."""
    parsed = safe_urlsplit(url)
    return bool(parsed is not None and parsed.query)


def source_fingerprint(safe_url: str) -> str:
    """Return a stable non-secret identity for a sanitized source URL."""
    return hashlib.sha256(  # noqa: TID251 - URL identity fingerprint, not charter freshness
        safe_url.encode("utf-8")
    ).hexdigest()


def snapshot_sha256(snapshot_root: Path) -> str:
    """Hash installed snapshot files, excluding the manifest itself."""
    digest = hashlib.sha256()  # noqa: TID251 - local snapshot integrity checksum
    for path in sorted(
        snapshot_root.rglob("*"),
        key=lambda candidate: candidate.relative_to(snapshot_root).as_posix(),
    ):
        relative = path.relative_to(snapshot_root)
        if path.is_symlink():
            raise OSError(f"Snapshot contains unsupported symlink: {relative}")
        if relative == Path(_PACK_MANIFEST_FILENAME):
            continue
        if path.is_dir():
            continue
        if not path.is_file():
            raise OSError(f"Snapshot contains unsupported file type: {relative}")
        relative_bytes = relative.as_posix().encode("utf-8")
        digest.update(len(relative_bytes).to_bytes(8, "big"))
        digest.update(relative_bytes)
        size = path.stat().st_size
        digest.update(size.to_bytes(8, "big"))
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(64 * 1024), b""):
                digest.update(chunk)
    return digest.hexdigest()


def _iso_now() -> str:
    return now_utc_stamp()


__all__ = [
    "SCHEMA_VERSION",
    "HASH_EXCLUDED_FIELDS",
    "Constituent",
    "CharterProfile",
    "PackManifest",
    "sort_constituents",
    "compute_pack_manifest_hash",
    "finalize_pack_manifest",
    "dump_pack_manifest_bytes",
    "load_pack_manifest",
    "counts_by_kind",
    "RECOGNISED_ARTIFACT_DIRS",
    "write_pack_manifest",
    "count_snapshot_artifacts",
    "strip_source_credentials",
    "safe_urlsplit",
    "source_fingerprint",
    "snapshot_sha256",
]
