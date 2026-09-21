"""Synthesis manifest writer — WP03 (T017).

Owns the ``SynthesisManifest`` and ``ManifestArtifactEntry`` Pydantic models
plus their IO helpers.

The manifest is written **last** in the promote pipeline (KD-2 authority
rule): a partial promote (e.g. crashed after some ``os.replace`` calls but
before the manifest write) leaves the live tree in an authors-but-no-manifest
state that readers treat as partial-and-rerunable.

Storage location: ``.kittify/charter/synthesis-manifest.yaml``

Data model reference: data-model.md §E-6 / §E-6a.
Schema reference: contracts/synthesis-manifest.schema.yaml.

All filesystem writes go through ``PathGuard`` (FR-016).
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr
from ruamel.yaml import YAML

from .errors import ManifestIntegrityError
from .synthesize_pipeline import canonical_yaml
from kernel.paths import to_posix

if TYPE_CHECKING:
    from .path_guard import PathGuard

# Canonical location of the synthesis manifest.
MANIFEST_PATH = Path(".kittify/charter/synthesis-manifest.yaml")
_ARTIFACT_PATH_PREFIX = Path(".kittify/doctrine")
_PROVENANCE_PATH_PREFIX = Path(".kittify/charter/provenance")


# ---------------------------------------------------------------------------
# Data models (data-model.md §E-6 / §E-6a)
# ---------------------------------------------------------------------------


class ManifestArtifactEntry(BaseModel):
    """One synthesized artifact listed in the synthesis manifest (data-model §E-6a)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    # Kept aligned with ``charter.offering.artifact_kinds.DIRECT_WRITE_KINDS`` by
    # test (``tests/charter/test_direct_write_kinds_parity.py``): a ``Literal``
    # cannot consume a runtime tuple, so alignment is by-test, not by-construction.
    kind: Literal["directive", "tactic", "styleguide", "procedure", "agent_profile"]
    slug: str
    path: str
    """Repo-relative path to the artifact YAML under ``.kittify/doctrine/``."""

    provenance_path: str
    """Repo-relative path to the provenance sidecar under ``.kittify/charter/``."""

    content_hash: str
    """SHA-256 hex digest of the artifact YAML bytes."""


class SynthesisManifest(BaseModel):
    """Top-of-bundle manifest — the authoritative commit marker (data-model §E-6).

    Written last by ``write_pipeline.promote`` so that readers can detect
    partial-promote states: manifest absent → partial; manifest present but
    hash mismatch → corrupt; manifest present + all hashes pass → live tree
    is authoritative.

    Schema version 2 (Phase 7): added synthesizer_version and manifest_hash.
    ``manifest_hash`` is the SHA-256 hex digest of ``canonical_yaml(all fields
    except manifest_hash)`` — allows readers to verify manifest self-integrity.

    Schema version 3 (synthesized-drg-stale-refresh): added
    ``bundle_content_hash``, the content-identity digest of the four synced
    bundle files (see ``charter.bundle.compute_bundle_content_hash``) used by
    the synthesized-DRG freshness comparison. The literal is widened to
    ``Literal["2", "3"]`` so pre-fix ``"2"`` manifests keep validating. The
    model default is ``"3"``: the real writers omit ``schema_version`` and rely
    on this default to stamp new manifests, so they carry ``bundle_content_hash``.
    The fresh-seed writer (``_fresh_seed_manifest_text``) deliberately overrides
    to ``"2"`` (a built-in-only seed carries no content hash; see its rationale).
    Do NOT revert the default to ``"2"`` — new writes must be ``"3"``.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")
    _raw_field_names: frozenset[str] | None = PrivateAttr(default=None)

    schema_version: Literal["2", "3"] = "3"
    mission_id: str | None = None
    created_at: str
    """ISO 8601 UTC timestamp."""

    run_id: str
    """ULID matching the staging directory that produced this manifest."""

    adapter_id: str
    """Primary adapter id.  Empty string for mixed-identity runs."""

    adapter_version: str
    """Primary adapter version.  Empty string for mixed-identity runs."""

    synthesizer_version: str = Field(..., min_length=1)
    """Version of the spec-kitty-cli package that produced this manifest."""

    manifest_hash: str = Field(..., min_length=64, max_length=64)
    """SHA-256 hex digest of canonical_yaml(all manifest fields except manifest_hash)."""

    artifacts: list[ManifestArtifactEntry] = Field(default_factory=list)
    """One entry per committed artifact, in deterministic order."""

    built_in_only: bool = False
    """When True the synthesizer legitimately produced no project DRG
    (FR-009 / data-model §6).  Downstream readers MUST treat this as the
    authoritative state and ignore any stale ``.kittify/doctrine/graph.yaml``.

    Default ``False`` preserves backward compatibility — manifests written by
    pre-WP02 synthesizers parse unchanged.
    """

    bundle_content_hash: str | None = None
    """``"sha256:..."`` content-identity digest of the four synced bundle
    files, produced by ``charter.bundle.compute_bundle_content_hash``.

    **Substantive (non-volatile).** This field participates in no-op-stable
    write comparisons and MUST NOT be added to
    ``write_pipeline._VOLATILE_MANIFEST_FIELDS`` — unlike ``created_at`` or
    ``run_id``, a changed value here means the synced bundle content genuinely
    changed and the manifest write is not a no-op.

    ``None`` on built-in-only seeds and post-condition flips (the freshness
    reader short-circuits on ``built_in_only`` before comparing hashes) and on
    any pre-fix ``schema_version: "2"`` manifest that predates this field.
    """


# ---------------------------------------------------------------------------
# IO helpers
# ---------------------------------------------------------------------------


def _yaml_instance() -> YAML:
    y = YAML()
    y.default_flow_style = False
    y.explicit_start = False
    return y


def dump_yaml(manifest: SynthesisManifest, path: Path, guard: PathGuard) -> None:
    """Serialize ``manifest`` to ``path`` via ``PathGuard.write_text``.

    Uses ``canonical_yaml`` for stable serialization so that the file bytes
    are deterministic under identical inputs (NFR-006).

    Parameters
    ----------
    manifest:
        Fully-assembled ``SynthesisManifest``.
    path:
        Target path.  Must be within the PathGuard allowlist.
    guard:
        PathGuard instance used for all writes.
    """
    data = manifest.model_dump(mode="python")
    # Serialize the top-level manifest using canonical_yaml for key ordering.
    yaml_bytes = canonical_yaml(data)
    guard.write_text(
        path,
        yaml_bytes.decode("utf-8"),
        encoding="utf-8",
        caller="manifest.dump_yaml",
    )


def load_yaml(path: Path) -> SynthesisManifest:
    """Deserialize the manifest from ``path`` and validate with Pydantic.

    Parameters
    ----------
    path:
        Absolute or repo-relative path to the synthesis manifest YAML.

    Returns
    -------
    SynthesisManifest
        Validated manifest.

    Raises
    ------
    pydantic.ValidationError
        If the YAML content does not match the SynthesisManifest schema.
    FileNotFoundError
        If ``path`` does not exist.
    """
    y = _yaml_instance()
    raw = y.load(path.read_text(encoding="utf-8"))
    manifest = SynthesisManifest.model_validate(raw)
    if isinstance(raw, Mapping):
        manifest._raw_field_names = frozenset(str(key) for key in raw)
    return manifest


def hash_manifest_payload(
    data: Mapping[str, Any], *, exclude_keys: frozenset[str]
) -> str:
    """Single canonical manifest hasher — SHA-256 of ``canonical_yaml(payload)``.

    The **one** manifest-hashing primitive, shared by both the charter
    ``SynthesisManifest`` (via :func:`compute_manifest_hash`) and the unified
    ``PackManifest`` (``specify_cli.doctrine.pack_manifest``). Keeping the SHA
    here — the module's existing designated raw-SHA owner — means no second
    hasher is ever introduced (RR-SF2 / T005).

    Every key in ``exclude_keys`` is dropped before serialization so callers
    can omit self / provenance fields (``manifest_hash``, and the volatile
    ``generated_at`` / ``generated_by`` for the pack manifest) from the digest.
    """
    filtered = {k: v for k, v in data.items() if k not in exclude_keys}
    return hashlib.sha256(canonical_yaml(filtered)).hexdigest()  # noqa: TID251 - production raw SHA-256 owner


def hash_content_bytes(raw: bytes) -> str:
    """SHA-256 hex digest of raw artifact bytes (single sanctioned hasher).

    Callers are responsible for any normalization (e.g. LF line-ending
    normalization for cross-platform-stable ``content_hash`` values) before
    passing bytes here, so this stays a thin, auditable owner of the raw SHA.
    """
    return hashlib.sha256(raw).hexdigest()  # noqa: TID251 - production raw SHA-256 owner


def compute_manifest_hash(manifest_or_data: SynthesisManifest | Mapping[str, Any]) -> str:
    """Compute the canonical manifest self-hash.

    The contract is intentionally identical to ``verify_manifest_hash``:
    SHA-256 of ``canonical_yaml(all manifest fields except manifest_hash)``.
    Mapping inputs are validated through ``SynthesisManifest`` first so model
    defaults, including future fields, participate in the hash consistently.
    """
    if isinstance(manifest_or_data, SynthesisManifest):
        data = manifest_or_data.model_dump(mode="python")
    else:
        data = SynthesisManifest.model_validate(
            {**manifest_or_data, "manifest_hash": "0" * 64}
        ).model_dump(mode="python")

    return hash_manifest_payload(data, exclude_keys=frozenset({"manifest_hash"}))


def finalize_manifest(manifest: SynthesisManifest) -> SynthesisManifest:
    """Recompute ``manifest_hash`` from the full instance and return a copy.

    The single canonical finalizer (data-model.md "Contract: finalize_
    manifest") every manifest-persisting site routes through immediately
    before writing. Because the hash is always derived from the FULL
    instance (via :func:`compute_manifest_hash`, which model-normalizes
    every field including future additions), no field can be silently
    omitted from the hashed payload the way a hand-synced raw dict could
    drop one.

    Behavior-preserving: for content identical to today, this produces the
    same ``manifest_hash`` the existing inline ``compute_manifest_hash``
    call sites produce.
    """
    zeroed = manifest.model_copy(update={"manifest_hash": "0" * 64})
    return manifest.model_copy(update={"manifest_hash": compute_manifest_hash(zeroed)})


def verify_manifest_hash(manifest: SynthesisManifest) -> None:
    """Verify the manifest self-hash field.

    Recomputes SHA-256 of the canonical YAML serialization of all manifest
    fields except ``manifest_hash`` itself and compares to the stored value.

    Legacy fallback: if the primary (model-normalized) comparison fails, and
    the manifest was loaded from disk (``_raw_field_names`` populated),
    recompute a **raw** hash over exactly the on-disk field subset (the keys
    the file actually carried, per-field gated by ``_raw_field_names`` —
    NOT a fixed pop-list). This lets a manifest written before a schema
    field existed (e.g. a pre-fix ``schema_version: "2"`` file lacking
    ``bundle_content_hash``) keep verifying, while a manifest that DOES
    carry a field but with a tampered value still fails: the field is in
    ``_raw_field_names`` so it is included in the subset and the tampered
    value flows into the recomputed digest.

    Raises
    ------
    ValueError
        If the computed hash does not match ``manifest.manifest_hash``.
    """
    computed = compute_manifest_hash(manifest)
    if computed != manifest.manifest_hash:
        raw_field_names = manifest._raw_field_names
        if raw_field_names is not None:
            subset = {
                k: v
                for k, v in manifest.model_dump(mode="python").items()
                if k in raw_field_names and k != "manifest_hash"
            }
            legacy_computed = hashlib.sha256(  # noqa: TID251 - production raw SHA-256 owner
                canonical_yaml(subset)
            ).hexdigest()
            if legacy_computed == manifest.manifest_hash:
                return

        raise ValueError(
            f"manifest_hash mismatch (stored {manifest.manifest_hash[:12]}..., "
            f"computed {computed[:12]}...)"
        )


def _validate_manifest_path(raw_path: str, *, field_name: str, required_prefix: Path) -> Path:
    """Return a safe repo-relative manifest path under ``required_prefix``."""
    path = Path(to_posix(raw_path))
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(
            f"{field_name} must be repo-relative and stay under "
            f"{required_prefix.as_posix()}: {raw_path}"
        )
    try:
        path.relative_to(required_prefix)
    except ValueError as exc:
        raise ValueError(
            f"{field_name} must be under {required_prefix.as_posix()}: {raw_path}"
        ) from exc
    return path


def _resolve_under_repo(repo_root: Path, rel_path: Path, *, field_name: str) -> Path:
    """Resolve ``rel_path`` and fail if symlinks escape ``repo_root``."""
    repo_resolved = repo_root.resolve(strict=False)
    resolved = (repo_root / rel_path).resolve(strict=False)
    try:
        resolved.relative_to(repo_resolved)
    except ValueError as exc:
        raise ValueError(
            f"{field_name} resolves outside repository root: {rel_path.as_posix()}"
        ) from exc
    return resolved


def verify(manifest: SynthesisManifest, repo_root: Path) -> None:
    """Verify that every artifact listed in the manifest exists with matching hash.

    Implements the **authority rule** from KD-2: live tree is authoritative IFF
    manifest is present AND all ``content_hash`` checks pass.

    Parameters
    ----------
    manifest:
        The manifest to verify.
    repo_root:
        Repository root used to resolve relative artifact paths.

    Raises
    ------
    ManifestIntegrityError
        When any artifact file is missing or its on-disk hash does not match
        the ``content_hash`` stored in the manifest entry.
    """
    manifest_path = str(MANIFEST_PATH)
    for entry in manifest.artifacts:
        artifact_rel = _validate_manifest_path(
            entry.path,
            field_name="manifest artifact path",
            required_prefix=_ARTIFACT_PATH_PREFIX,
        )
        _validate_manifest_path(
            entry.provenance_path,
            field_name="manifest provenance path",
            required_prefix=_PROVENANCE_PATH_PREFIX,
        )
        artifact_path = _resolve_under_repo(
            repo_root,
            artifact_rel,
            field_name="manifest artifact path",
        )
        if not artifact_path.exists():
            raise ManifestIntegrityError(
                manifest_path=manifest_path,
                offending_artifact=entry.path,
            )
        on_disk_bytes = artifact_path.read_bytes()
        on_disk_hash = hashlib.sha256(on_disk_bytes).hexdigest()  # noqa: TID251 - production raw SHA-256 owner
        if on_disk_hash != entry.content_hash:
            raise ManifestIntegrityError(
                manifest_path=manifest_path,
                offending_artifact=entry.path,
            )


__all__ = [
    "ManifestArtifactEntry",
    "SynthesisManifest",
    "MANIFEST_PATH",
    "dump_yaml",
    "load_yaml",
    "finalize_manifest",
    "compute_manifest_hash",
    "hash_manifest_payload",
    "hash_content_bytes",
    "verify",
    "verify_manifest_hash",
]
