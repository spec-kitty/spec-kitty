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
import logging
from collections.abc import Iterable, Mapping
from io import StringIO
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr
from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from . import provenance as _provenance
from .errors import ManifestIntegrityError, ProjectDirectiveScanError, SynthesisMembershipUnreadableError
from charter.offering.artifact_kinds import PROJECT_KIND_DIRS, ArtifactKind
from charter.offering.packs.hashing import hash_manifest_payload
from charter.offering.packs.pack_manifest import (
    CharterProfile,
    Constituent,
    PackManifest,
    finalize_pack_manifest,
)
from .synthesize_pipeline import canonical_yaml
from kernel.atomic import atomic_write
from kernel.charter_pack_paths import PROJECT_PACK_ROOT, project_pack_path
from kernel.paths import to_posix

if TYPE_CHECKING:
    from .path_guard import PathGuard

# Canonical location of the synthesis manifest.
MANIFEST_PATH = Path(".kittify/charter/synthesis-manifest.yaml")
_LOGGER = logging.getLogger(__name__)

#: Every reach-only artifact id synthesis has created, per kind; a listed id is never re-appended.
CREATED_ARTIFACTS_PATH = Path(".kittify/charter/synthesized-artifacts.yaml")
#: The unreleased tactic-only record: still read (unioned into ``tactic``), never written.
LEGACY_CREATED_ARTIFACTS_PATH = Path(".kittify/charter/synthesized-tactics.yaml")
_CREATED_ARTIFACTS_HEADER = (
    "# Artifact ids spec-kitty synthesis has created, per kind. Synthesis adds an\n"
    "# artifact to an explicit activated_<kind>s list only the first time it creates\n"
    "# it, so an artifact you remove stays removed. Written by spec-kitty; do not edit.\n"
)
#: Every entry lives under the project charter pack root (FR-016). A manifest
#: still listing the retired pre-cutover project prefix is rewritten by
#: ``spec-kitty upgrade`` and otherwise fails :func:`verify` (FR-011).
_ARTIFACT_PATH_PREFIX = PROJECT_PACK_ROOT
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
    """Repo-relative path to the artifact YAML under ``.kittify/charter-packs/``.

    A manifest written before the cutover migration carries the retired
    project prefix until ``spec-kitty upgrade`` rewrites it;
    :func:`verify` rejects that prefix (FR-011).
    """

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
    authoritative state and ignore any stale ``.kittify/charter-packs/graph.yaml``.

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


# ---------------------------------------------------------------------------
# The synthesis ownership record (#6510 / #4226, converged in #6767)
# ---------------------------------------------------------------------------
#
# One question -- "which artifacts of this kind did synthesis create?" -- has one reader
# (:func:`synthesized_urns`) over one record. The record is the synthesis manifest plus the
# provenance sidecar each listed entry names; the created-artifacts record
# (:data:`CREATED_ARTIFACTS_PATH`, with the legacy tactics record unioned in) is its one
# documented fallback. Every unreadable condition raises
# :class:`~charter.activation.synthesizer.errors.SynthesisMembershipUnreadableError`.


class UnreadableCreatedRecordError(ValueError):
    """A created-artifacts record exists but cannot be read as per-kind lists of ids.

    ``path`` is the repo-relative record that failed, so the caller can warn about it.
    """

    def __init__(self, path: str) -> None:
        super().__init__(path)
        self.path = path


def created_record_key(kind: str) -> str:
    """The created-artifacts record's key for *kind* (``created_tactics``, ...)."""
    return f"created_{ArtifactKind(kind).plural}"


def _record_kinds() -> frozenset[str]:
    """Kinds the created-artifacts record tracks.

    Deferred import: ``reconcile`` imports this module (the manifest writer), so the
    reach-only vocabulary cannot be imported at module scope here.
    """
    from .reconcile import REACH_ONLY_KINDS

    return frozenset(REACH_ONLY_KINDS)


def _load_record_file(path: Path) -> dict[str, Any]:
    """The mapping in one record file; empty when absent, raises when malformed."""
    if not path.exists():
        return {}
    try:
        data = YAML(typ="safe").load(path.read_text(encoding="utf-8"))
    except (OSError, YAMLError) as exc:
        raise UnreadableCreatedRecordError(path.as_posix()) from exc
    if not isinstance(data, dict):
        raise UnreadableCreatedRecordError(path.as_posix())
    return dict(data)


def _ids_under(data: Mapping[str, Any], key: str, path: Path) -> set[str]:
    ids = data.get(key, [])
    if not isinstance(ids, list) or not all(isinstance(item, str) for item in ids):
        raise UnreadableCreatedRecordError(path.as_posix())
    return set(ids)


def read_created_record(repo_root: Path) -> tuple[dict[str, set[str]], dict[str, Any]]:
    """Per-kind recorded ids (the legacy tactics record unioned in) and the keys this module does not own."""
    path = repo_root / CREATED_ARTIFACTS_PATH
    data = _load_record_file(path)
    legacy_path = repo_root / LEGACY_CREATED_ARTIFACTS_PATH
    legacy = _load_record_file(legacy_path)
    kinds = _record_kinds()
    recorded = {kind: _ids_under(data, created_record_key(kind), path) for kind in kinds}
    recorded["tactic"] |= _ids_under(legacy, created_record_key("tactic"), legacy_path)
    foreign = {key: value for key, value in data.items() if key not in {created_record_key(kind) for kind in kinds}}
    return recorded, foreign


def write_created_record(repo_root: Path, recorded: Mapping[str, set[str]], foreign: Mapping[str, Any]) -> None:
    """Write the created-artifacts record, preserving keys this module does not own (format unchanged)."""
    kinds = _record_kinds()
    body = {**{created_record_key(kind): sorted(recorded[kind]) for kind in kinds}, **foreign}
    stream = StringIO()
    YAML().dump(body, stream)
    atomic_write(repo_root / CREATED_ARTIFACTS_PATH, f"{_CREATED_ARTIFACTS_HEADER}{stream.getvalue()}", mkdir=True)


def sidecar_artifact_urn(repo_root: Path, entry: ManifestArtifactEntry, *, owned_only: bool = True) -> str | None:
    """Return the ``artifact_urn`` *entry*'s provenance sidecar records, or raise.

    The one parser of the sidecar shape; nothing else under ``src/`` may parse it.

    With ``owned_only`` (the default, the ownership contract) a
    ``project-direct-write`` sidecar yields ``None``: project registration
    (``charter activate``) records hand-authored files, and re-records synthesized
    ones, in the same manifest; that record is not synthesis ownership (the same
    split ``project_drg._registered_project_artifacts`` and
    ``project_registration._sidecar_recorded_urn`` draw).

    ``owned_only=False`` returns the recorded URN regardless of who wrote it. The
    ``charter synthesize --json`` envelope uses that: it reports what the manifest
    committed and the artifact's id, not the ownership verdict, so a registration
    keeps its ``artifact_id`` exactly as before.

    A sidecar that is missing, unreadable, outside ``.kittify/charter/provenance/``
    (or escaping the repository), invalid, or records a URN of another kind or
    with an empty id raises
    :class:`~charter.activation.synthesizer.errors.SynthesisMembershipUnreadableError`
    naming ``entry.provenance_path``.
    """
    try:
        rel = _validate_manifest_path(
            entry.provenance_path,
            field_name="manifest provenance path",
            required_prefix=_PROVENANCE_PATH_PREFIX,
        )
        sidecar = _provenance.load_yaml(_resolve_under_repo(repo_root, rel, field_name="manifest provenance path"))
    except (OSError, ValueError, YAMLError) as exc:
        raise _ownership_unreadable(entry.provenance_path, exc, kind=entry.kind) from exc
    urn_kind, _, urn_id = sidecar.artifact_urn.partition(":")
    if urn_kind != entry.kind or not urn_id:
        raise _ownership_unreadable(
            entry.provenance_path,
            ValueError(f"artifact_urn {sidecar.artifact_urn!r} is not a {entry.kind} URN"),
            kind=entry.kind,
        )
    if owned_only and sidecar.adapter_id == "project-direct-write":
        return None
    return str(sidecar.artifact_urn)


def _ownership_unreadable(offending: str, exc: Exception, *, kind: str | None = None) -> SynthesisMembershipUnreadableError:
    """The one coded refusal for a provenance sidecar that cannot be read."""
    reason = f"{type(exc).__name__}: {exc}".strip()
    body = (
        f"{MANIFEST_PATH.as_posix()} lists {offending}, which cannot be read as a provenance record "
        f"({reason}), so spec-kitty cannot tell which {kind or 'artifact'} was synthesized. "
        "Restore or repair that file from version control (for example "
        f"`git checkout -- {offending}`), then retry."
    )
    return SynthesisMembershipUnreadableError(
        body,
        record_path=MANIFEST_PATH.as_posix(),
        offending_artifact=offending,
        reason=reason,
        kind=kind,
    )


def _membership_error(kind: str, cause: Exception, record_state: str) -> SynthesisMembershipUnreadableError:
    """The one coded refusal for an ownership record that cannot answer."""
    if isinstance(cause, SynthesisMembershipUnreadableError):
        lead = f"{cause.offending_artifact or MANIFEST_PATH.as_posix()} cannot be read ({cause.reason})"
        offending = cause.offending_artifact
    else:
        reason = f"{type(cause).__name__}: {cause}".strip()
        lead = f"{MANIFEST_PATH.as_posix()} cannot be read ({reason})"
        offending = MANIFEST_PATH.as_posix()
    body = (
        f"{lead} and the created-artifacts record ({CREATED_ARTIFACTS_PATH.as_posix()}) is {record_state}, "
        f"so spec-kitty cannot tell which {kind}s synthesis created. Refusing to deliver governance: every "
        f"synthesized {kind} would otherwise reach agents even while its directive is inactive.\n"
        f"Remediation: restore {MANIFEST_PATH.as_posix()} (and its provenance sidecars) from version control "
        f"(for example `git checkout -- {MANIFEST_PATH.as_posix()}`), or fix their YAML by hand. Do not delete "
        f"{CREATED_ARTIFACTS_PATH.as_posix()}: synthesis would forget which artifacts it created and add back "
        "ones you removed."
    )
    return SynthesisMembershipUnreadableError(
        body,
        record_path=MANIFEST_PATH.as_posix(),
        offending_artifact=offending,
        reason=f"{type(cause).__name__}: {cause}".strip(),
        kind=kind,
    )


def _recorded_urns(repo_root: Path, kind: str, cause: Exception) -> frozenset[str]:
    """The created-artifacts record's ids of *kind*, standing in for an unreadable manifest or sidecar.

    The record lists every id synthesis has ever created, so it never under-counts.
    When it is absent, unreadable or lists no id of *kind* -- or the record does not
    track the kind at all -- the one coded error is raised: an empty set would re-root
    every synthesized artifact.
    """
    if kind not in _record_kinds():
        raise _membership_error(kind, cause, f"not tracked by the record for {kind}s")
    try:
        recorded, _ = read_created_record(repo_root)
    except UnreadableCreatedRecordError:
        record_state = "unreadable"
    else:
        if recorded[kind]:
            _LOGGER.warning(
                "%s cannot be read; using %s for the synthesized %ss.",
                MANIFEST_PATH.as_posix(),
                CREATED_ARTIFACTS_PATH.as_posix(),
                kind,
            )
            return frozenset(f"{kind}:{artifact_id}" for artifact_id in recorded[kind])
        # An absent record, or one listing no id of this kind, says nothing about what was synthesized.
        record_state = f"absent or lists no {kind}"
    raise _membership_error(kind, cause, record_state)


#: Kinds whose node identity is the artifact id rather than the manifest slug. Only the
#: provenance sidecar records a directive's ``PROJECT_*`` id; every other kind's node is
#: ``<kind>:<slug>`` (see :func:`charter.activation.synthesizer.reconcile.synthesized_node_urns`),
#: so for those the manifest entry alone already names what synthesis created.
_ID_KEYED_KINDS: frozenset[str] = frozenset({ArtifactKind.DIRECTIVE.value})


def synthesized_urns(repo_root: Path, kind: str) -> frozenset[str]:
    """URNs of the *kind* artifacts synthesis created: the one ownership reader (#6767).

    Ownership comes from the existing record only (no id-prefix heuristic): the
    manifest lists each synthesized artifact, and its provenance sidecar records
    the URN (``artifact_urn``, e.g. ``directive:PROJECT_001``). A URN is
    synthesis-owned when at least one entry recording it has a sidecar whose
    ``adapter_id`` is not ``project-direct-write``: a direct-write registration
    alone (a hand-authored file ``charter activate`` registered) is not ownership,
    and a synthesized artifact re-registered as direct-write stays owned.

    Absent manifest (not even a dangling symlink): empty set (nothing synthesized).
    An unreadable or invalid manifest falls back to the created-artifacts record
    (:func:`_recorded_urns`); when that record cannot answer either,
    :class:`~charter.activation.synthesizer.errors.SynthesisMembershipUnreadableError`
    is raised -- fail closed, never "nothing owned".

    An entry whose sidecar cannot be read is answered two ways, by node identity
    (:data:`_ID_KEYED_KINDS`). For a directive only the sidecar records the id, so
    the same record fallback applies; for every other kind the entry's own
    ``<kind>:<slug>`` is that artifact's identity, so the manifest answers (the
    manifest is the creation record, and treating it as owned is the fail-closed
    direction for delivery gating).

    :func:`specify_cli.cli.commands.charter._synthesis._artifact_id_from_sidecar` is the
    lenient display reader: it wraps :func:`sidecar_artifact_urn` and catches that error.
    """
    manifest_file = repo_root / MANIFEST_PATH
    try:
        # A dangling symlink is unreadable, not absent; exists() itself can raise (EACCES).
        if not (manifest_file.exists() or manifest_file.is_symlink()):
            return frozenset()
        manifest = load_yaml(manifest_file)
    except (OSError, ValueError, YAMLError) as exc:
        return _recorded_urns(repo_root, kind, exc)
    owned: set[str] = set()
    for entry in manifest.artifacts:
        if entry.kind != kind:
            continue
        try:
            urn = sidecar_artifact_urn(repo_root, entry)
        except SynthesisMembershipUnreadableError as exc:
            if kind in _ID_KEYED_KINDS:
                return _recorded_urns(repo_root, kind, exc)
            owned.add(f"{kind}:{entry.slug}")
            continue
        if urn is not None:
            owned.add(urn)
    return frozenset(owned)


def synthesized_slugs(repo_root: Path, kind: str) -> frozenset[str]:
    """The id segment of :func:`synthesized_urns` for *kind* (e.g. ``how-we-apply-directive-024``)."""
    prefix = f"{kind}:"
    return frozenset(urn[len(prefix) :] for urn in synthesized_urns(repo_root, kind))


def manifest_slugs(repo_root: Path, kind: str) -> frozenset[str]:
    """Bare slugs of *kind* the synthesis manifest lists; empty when absent or unreadable.

    The write-side diff helper (``reach_only._first_time_slugs``) asks "what did the
    manifest say before this run", which must stay answerable on a partially-written
    tree, so this stays lenient. It is **not** an ownership answer: use
    :func:`synthesized_urns` for that.
    """
    from .reconcile import synthesized_node_urns

    try:
        manifest = load_yaml(repo_root / MANIFEST_PATH)
    except (OSError, ValueError, YAMLError):
        return frozenset()
    prefix = f"{kind}:"
    return frozenset(urn[len(prefix) :] for urn in synthesized_node_urns(manifest) if urn.startswith(prefix))


def project_directive_ids(repo_root: Path) -> frozenset[str]:
    """Ids the project pack's directive files declare (#6510): the one project-directive scan.

    An absent directive directory, or one holding no directive file, yields an
    empty set. A directory that cannot be listed, or a malformed directive
    file, raises :class:`ProjectDirectiveScanError` (never a guess).
    """
    from charter.offering.drg.project_scan import scan_project_artifacts

    directive = ArtifactKind.DIRECTIVE
    folder = project_pack_path(repo_root, PROJECT_KIND_DIRS[directive])
    try:
        paths = frozenset(folder.rglob(directive.glob_pattern)) if folder.is_dir() else frozenset()
        artifacts = scan_project_artifacts(repo_root, paths=paths) if paths else ()
    except (OSError, ValueError) as exc:
        directory = f"{PROJECT_PACK_ROOT.as_posix()}/{PROJECT_KIND_DIRS[directive]}/"
        raise ProjectDirectiveScanError(directory=directory, reason=str(exc)) from exc
    return frozenset(artifact.node.urn.partition(":")[2] for artifact in artifacts)


def synthesis_owned_directive_ids(
    repo_root: Path,
    directive_ids: Iterable[str],
    *,
    project_ids: frozenset[str] | None = None,
) -> frozenset[str]:
    """The ids among *directive_ids* that name a directive synthesis created (#6510 / #4226).

    Synthesis only ever creates project-layer directives, so the ownership
    record (:func:`synthesized_urns`, the one reader) is read only when at least
    one of *directive_ids* is declared by a file under the project pack's
    directive directory. A list of built-in or org directives returns an empty
    set with no manifest I/O, so a lost provenance sidecar cannot refuse a run
    that never needs it. When the project directive files cannot be read, every
    id is a candidate and the record is read (never a guess). An unreadable
    record raises
    :class:`~charter.activation.synthesizer.errors.SynthesisMembershipUnreadableError`
    (fail closed, never "nothing owned").

    *project_ids* is a result of :func:`project_directive_ids` the caller already
    holds; when given, the project pack is not scanned again.
    """
    requested = frozenset(directive_ids)
    if not requested:
        return frozenset()
    if project_ids is None:
        try:
            project_ids = project_directive_ids(repo_root)
        except ProjectDirectiveScanError:
            project_ids = requested
    candidates = requested & project_ids
    if not candidates:
        return frozenset()
    owned_urns = synthesized_urns(repo_root, ArtifactKind.DIRECTIVE.value)
    return frozenset(directive_id for directive_id in candidates if f"{ArtifactKind.DIRECTIVE.value}:{directive_id}" in owned_urns)


# ---------------------------------------------------------------------------
# Charter absorption into the unified pack manifest (IC-01 / T002)
# ---------------------------------------------------------------------------


def absorb_synthesis_manifest(manifest: SynthesisManifest) -> PackManifest:
    """Absorb a charter ``SynthesisManifest`` into the unified schema (PP-M2).

    The charter bundle's ``artifacts[]`` become canonical ``constituents[]``
    (each preserving its ``provenance_path``), and the **entire** charter-only
    field-set is carried onto a :class:`CharterProfile` so nothing is dropped:
    ``mission_id``, ``bundle_content_hash``, ``synthesizer_version``,
    ``run_id``, ``adapter_id``, ``adapter_version``, ``created_at``,
    ``schema_version`` and the load-bearing ``built_in_only``.

    This is a lossless in-memory bridge. It does **not** change the on-disk
    ``synthesis-manifest.yaml`` format, so every existing charter-manifest
    reader (freshness / preflight / lint / bundle / versioning / the rc35
    migrations) keeps reading the unchanged bytes (T003).
    """
    constituents = [
        Constituent(
            kind=ArtifactKind(entry.kind),
            id=entry.slug,
            path=entry.path,
            content_hash=entry.content_hash,
            provenance_path=entry.provenance_path,
        )
        for entry in manifest.artifacts
    ]
    profile = CharterProfile(
        mission_id=manifest.mission_id,
        bundle_content_hash=manifest.bundle_content_hash,
        synthesizer_version=manifest.synthesizer_version,
        run_id=manifest.run_id,
        adapter_id=manifest.adapter_id,
        adapter_version=manifest.adapter_version,
        created_at=manifest.created_at,
        schema_version=manifest.schema_version,
        built_in_only=manifest.built_in_only,
    )
    return finalize_pack_manifest(
        PackManifest(constituents=constituents, charter=profile)
    )


__all__ = [
    "ManifestArtifactEntry",
    "SynthesisManifest",
    "MANIFEST_PATH",
    "CREATED_ARTIFACTS_PATH",
    "LEGACY_CREATED_ARTIFACTS_PATH",
    "UnreadableCreatedRecordError",
    "created_record_key",
    "read_created_record",
    "write_created_record",
    "dump_yaml",
    "load_yaml",
    "finalize_manifest",
    "compute_manifest_hash",
    "verify",
    "verify_manifest_hash",
    "absorb_synthesis_manifest",
    "project_directive_ids",
    "sidecar_artifact_urn",
    "synthesized_urns",
    "synthesized_slugs",
    "manifest_slugs",
    "synthesis_owned_directive_ids",
]
