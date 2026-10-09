"""Stage-and-promote write pipeline — WP03 (T018).

Public entry point: ``promote(request, staging_dir, results, validation_callback)``

This module implements KD-2 (atomicity model):

    stage → validate → ordered-os.replace → manifest-last → wipe

Authority rule (KD-2): the live tree is authoritative IFF the synthesis
manifest (``.kittify/charter/synthesis-manifest.yaml``) is present AND all
listed ``content_hash`` values match on-disk artifact bytes.  A partial
promote (crash between promote start and manifest write) leaves the live tree
in an authored-but-no-manifest state → readers treat it as partial-and-
rerunable.

Step ordering (enforced by this module):
    1. Write every (body, provenance) pair into the staged subtrees.
    2. Call ``validation_callback(staging_dir)`` — raises → abort to .failed/.
    3. Ordered ``os.replace`` (via PathGuard) into final live trees.
    4. Write manifest last (the sole mutation after content os.replace calls).
    5. ``staging_dir.wipe()``.
    6. Return the manifest.

On any exception between step 3 and step 4 the staging dir is NOT wiped —
the ``StagingDir`` context manager in the caller routes it to ``.failed/``.

All filesystem writes go through ``PathGuard`` (FR-016).
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from kernel.atomic import substantively_equal as _substantively_equal_core
from kernel.clock import now_utc_iso
from kernel.charter_pack_paths import (
    KITTIFY_DIRNAME,
    PROJECT_GRAPH_FILENAME,
    PROJECT_PACK_DIRNAME,
    project_pack_path,
)

from charter.bundle import compute_bundle_content_hash
from charter.activation.synthesizer._constants import GRAPH_FILENAME as _GRAPH_FILENAME

from .artifact_naming import artifact_filename, pack_kind_subdir
from .errors import NeutralityGateViolation, StagingPromoteError
from .evidence import EvidenceBundle
from .manifest import (
    MANIFEST_PATH,
    ManifestArtifactEntry,
    SynthesisManifest,
    dump_yaml as dump_manifest,
    finalize_manifest,
)
from .manifest import load_yaml as load_manifest
from .path_guard import PathGuard
from .provenance import dump_yaml as dump_provenance, provenance_path_for
from .request import SynthesisRequest
from .staging import StagingDir
from .synthesize_pipeline import ProvenanceEntry, _get_synthesizer_version, canonical_yaml

#: Live-tree writes land in the project charter pack root
#: (``kernel.charter_pack_paths``, FR-016); provenance sidecars stay under
#: ``.kittify/charter/provenance/``.
_KITTIFY_DIRNAME = KITTIFY_DIRNAME
_CHARTER_DIRNAME = "charter"
_PROVENANCE_DIRNAME = "provenance"


# ---------------------------------------------------------------------------
# Typed staged-artifact entry (WP02 — Charter Contract Cleanup Tranche 1)
# ---------------------------------------------------------------------------
#
# ``StagedArtifact`` is the typed entry returned by ``compute_written_artifacts``
# below. It is the single source of truth for the ``written_artifacts`` array
# emitted by ``charter synthesize --json`` (FR-003), and powers the byte-equal
# dry-run / non-dry-run path-parity guarantee (FR-004).
#
# Shape mirrors the ``WrittenArtifact`` contract from
# ``contracts/synthesis-envelope.schema.json``:
#
#   * ``path``        — repo-relative POSIX path that the live tree will (or
#                       did) carry. Computed from the same helpers
#                       ``promote()`` uses below — see ``_artifact_filename``
#                       and ``_pack_kind_subdir`` — so dry-run and
#                       non-dry-run agree byte-for-byte.
#   * ``kind``        — doctrine kind (``directive`` / ``tactic`` / ``styleguide``)
#                       lifted directly from ``ProvenanceEntry.artifact_kind``.
#   * ``slug``        — slug component lifted from ``ProvenanceEntry.artifact_slug``.
#   * ``artifact_id`` — concrete artifact identifier extracted from
#                       ``ProvenanceEntry.artifact_urn``. ``None`` for kinds
#                       that do not carry a URN-encoded id (tactic, styleguide).
#                       The CLI surface MUST NOT expose the placeholder
#                       ``PROJECT_000``; it is rejected here as well so a
#                       missing-provenance regression cannot silently leak.
#
# The dataclass is frozen so callers cannot mutate provenance after the fact.
# Adding fields here is safe (additive); removing/renaming would break the
# CLI envelope shape and is out of scope.


@dataclass(frozen=True)
class StagedArtifact:
    """Typed provenance entry for a single staged-or-promoted doctrine artifact.

    Sourced from ``(body, ProvenanceEntry)`` results returned by
    ``synthesize_pipeline.run_all``; never reconstructed from ``kind:slug``
    selectors. Used by both dry-run and non-dry-run code paths so that
    ``written_artifacts[*].path`` is byte-equal across the two modes
    (FR-004).
    """

    path: str
    """Repo-relative POSIX path (e.g. ``.kittify/charter-packs/directive/001-foo.directive.yaml``)."""

    kind: str
    """Doctrine kind: ``directive`` | ``tactic`` | ``styleguide``."""

    slug: str
    """Slug component used in the artifact filename."""

    artifact_id: str | None
    """Concrete artifact identifier (e.g. ``PROJECT_001``) or ``None``."""


def _artifact_id_from_provenance(prov: ProvenanceEntry) -> str | None:
    """Lift the concrete artifact_id from a ``ProvenanceEntry``.

    ``stage_and_validate``, ``promote``, and dry-run envelope projection all
    call this helper so malformed directive provenance cannot silently fall
    back to a ``000`` path. Returns ``None`` for kinds that do not carry a
    URN-encoded id (tactic, styleguide).
    """
    if prov.artifact_kind != "directive":
        return None
    prefix, separator, artifact_id = prov.artifact_urn.partition(":")
    if prefix != "directive" or separator != ":" or not artifact_id:
        raise ValueError(
            "Directive provenance must carry artifact_urn='directive:<artifact_id>'"
        )
    if artifact_id == "PROJECT_000":
        raise ValueError("Directive provenance must not surface PROJECT_000")
    # cast: charter.* follow_imports=skip collapses prov.artifact_urn to Any,
    # making partition() return Any; str is guaranteed by the guard above.
    return cast("str | None", artifact_id)


def compute_written_artifacts(
    results: list[tuple[Mapping[str, Any], ProvenanceEntry]],
    repo_root: Path,
) -> list[StagedArtifact]:
    """Project ``(body, ProvenanceEntry)`` results into typed staged-artifact entries.

    Pure function (no I/O). Uses the same path computation as ``promote()`` so
    a dry-run and a real-run produce byte-equal ``path`` values (FR-004).

    Parameters
    ----------
    results:
        The output of ``synthesize_pipeline.run_all``.
    repo_root:
        Project root used to resolve repo-relative paths (POSIX style).

    Returns
    -------
    list[StagedArtifact]
        One entry per result, in the order ``run_all`` produced them. Empty
        list when there are no results.
    """
    entries: list[StagedArtifact] = []
    for _body, prov in results:
        kind = prov.artifact_kind
        slug = prov.artifact_slug
        artifact_id = _artifact_id_from_provenance(prov)
        filename = artifact_filename(kind, slug, artifact_id)
        live_path = project_pack_path(repo_root, pack_kind_subdir(kind), filename)
        rel_path = live_path.relative_to(repo_root).as_posix()
        entries.append(
            StagedArtifact(
                path=rel_path,
                kind=kind,
                slug=slug,
                artifact_id=artifact_id,
            )
        )
    return entries


# ---------------------------------------------------------------------------
# Filename helpers (data-model §E-2 "Filename rule")
# ---------------------------------------------------------------------------


def _artifact_filename(kind: str, slug: str, artifact_id: str | None = None) -> str:
    """Return the repository-glob-matching filename for an artifact.

    - directive: ``<NNN>-<slug>.directive.yaml``
      where ``<NNN>`` is the numeric segment of ``artifact_id``
      (e.g. ``PROJECT_001`` → ``001``).
    - tactic:    ``<slug>.tactic.yaml``
    - styleguide: ``<slug>.styleguide.yaml``
    """
    return artifact_filename(kind, slug, artifact_id)


def _pack_kind_subdir(kind: str) -> str:
    """Return the doctrine subdirectory name for a given artifact kind."""
    return pack_kind_subdir(kind)


def _compute_content_hash(yaml_bytes: bytes) -> str:
    """SHA-256 hex digest of artifact YAML bytes (matches synthesize_pipeline)."""
    return hashlib.sha256(yaml_bytes).hexdigest()  # noqa: TID251 - production raw SHA-256 owner


# ---------------------------------------------------------------------------
# No-op-stable promotion helpers (#1912)
# ---------------------------------------------------------------------------
#
# Every governed run re-synthesizes the charter pack with a fresh ``run_id``,
# ``produced_at`` timestamp, and current ``synthesizer_version``. Writing those
# volatile fields unconditionally dirtied the tracked provenance/manifest files
# on every op even when no substantive content changed. The helpers below let
# ``promote()`` skip the live-tree write when the regenerated payload is
# byte-identical *modulo* those volatile provenance fields, so a no-op run
# leaves the committed bytes (and their prior timestamps/version) untouched.

# Provenance sidecar fields that change on every run regardless of content.
_VOLATILE_PROVENANCE_FIELDS: frozenset[str] = frozenset(
    {"produced_at", "synthesizer_version", "synthesis_run_id", "generated_at"}
)

# Synthesis manifest fields that change on every run regardless of content.
# ``manifest_hash`` is derived from the others, so it is volatile too.
_VOLATILE_MANIFEST_FIELDS: frozenset[str] = frozenset(
    {"created_at", "run_id", "adapter_version", "synthesizer_version", "manifest_hash"}
)

# Project graph overlay fields that change when the graph is regenerated even
# if the project-layer nodes/edges did not.
_VOLATILE_GRAPH_FIELDS: frozenset[str] = frozenset({"generated_at", "generated_by"})


def _strip_volatile(text: str, volatile_keys: frozenset[str]) -> str:
    """Drop top-level ``key: value`` lines for volatile fields from canonical YAML.

    The synthesizer serializes provenance and manifests via ``canonical_yaml``,
    which emits one top-level mapping with alphabetically sorted keys in block
    style. Each volatile field is therefore a single ``"<key>: ..."`` line at
    column zero. Removing those lines yields a stable "substantive content"
    projection that two runs with identical inputs produce identically — the
    basis for the no-op skip. This is a textual comparison, never written back
    to disk, so it cannot corrupt the on-disk YAML.

    This is charter's YAML-canonical-line projection — the *reference* ``strip``
    handed to the shared, format-agnostic no-op-stability core
    (:func:`kernel.atomic.substantively_equal`). The core itself bakes in no
    YAML assumptions; charter supplies this projection.
    """
    prefixes = tuple(f"{key}:" for key in volatile_keys)
    kept = [
        line
        for line in text.splitlines()
        if not (line[:1] not in (" ", "\t", "-") and line.startswith(prefixes))
    ]
    return "\n".join(kept)


def _substantively_equal(
    new_bytes: bytes,
    existing_path: Path,
    volatile_keys: frozenset[str],
) -> bool:
    """Return True if ``new_bytes`` equals ``existing_path`` modulo volatile fields.

    Reads the existing file and delegates the pure, I/O-free comparison to the
    shared no-op-stability core (:func:`kernel.atomic.substantively_equal`),
    passing charter's YAML-canonical-line :func:`_strip_volatile` as the
    ``strip`` projection. Returns False when the existing file is absent or
    unreadable so a genuine write still happens. Only the volatile
    provenance/manifest fields are excluded from the comparison; any substantive
    change (body, hashes, adapter identity, artifact set) still triggers a
    rewrite.
    """
    try:
        existing_text = existing_path.read_text(encoding="utf-8")
    except OSError:
        return False
    return _substantively_equal_core(
        existing_text,
        new_bytes,
        volatile_keys=volatile_keys,
        strip=_strip_volatile,
    )


# ---------------------------------------------------------------------------
# Neutrality gate helpers
# ---------------------------------------------------------------------------


def _is_generic_scoped(
    _target_kind: str,
    target_slug: str,
    evidence: EvidenceBundle | None,
) -> bool:
    """Return True if this artifact slot should be checked for language-specific bias.

    An artifact is generic-scoped when there is no code-signals scope_tag
    or when the artifact slug does not contain the scope_tag as a component.
    Conservative default: if evidence is absent, all artifacts are generic-scoped.

    Scope determination rules:
    - No evidence / no code_signals → generic (lint it)
    - scope_tag == "unknown" → generic (lint it)
    - scope_tag IS a substring of slug → language-scoped (skip lint)
    - scope_tag NOT in slug → generic (lint it)

    Example: scope_tag="python", slug="python-style-guide" → language-scoped (False)
    Example: scope_tag="python", slug="testing-philosophy" → generic (True)
    """
    if evidence is None or evidence.code_signals is None:
        return True  # no scope info → assume generic, apply lint

    scope_tag = evidence.code_signals.scope_tag
    if scope_tag == "unknown":
        return True

    # A language-scoped artifact slug typically contains the scope_tag as a component.
    # e.g. "python-style-guide" contains "python"; "testing-philosophy" does not.
    return scope_tag not in target_slug


def _run_neutrality_gate(
    staging_dir: StagingDir,
    results: list[tuple[Any, ProvenanceEntry]],
    evidence: EvidenceBundle | None,
) -> None:
    """Scan generic-scoped staged artifacts for language bias.

    Iterates over all (body, provenance) results. For each artifact that is
    generic-scoped (per ``_is_generic_scoped``), runs ``run_neutrality_lint``
    on the staged content file. If any banned term is found, raises
    ``NeutralityGateViolation`` immediately without promoting.

    The staging directory is NOT wiped on gate failure — the caller's context
    manager routes it to ``.failed/`` for operator inspection (KD-2, FR-011).

    Parameters
    ----------
    staging_dir:
        The active staging directory (pre-promote state).
    results:
        All ``(body, ProvenanceEntry)`` pairs from ``run_all()``.
    evidence:
        EvidenceBundle from the synthesis request, used to determine scope_tag.
    """
    from charter.activation.neutrality.lint import run_neutrality_lint

    for _body, prov in results:
        kind = prov.artifact_kind
        slug = prov.artifact_slug

        if not _is_generic_scoped(kind, slug, evidence):
            # Language-scoped artifact — language-specific terms are expected here.
            continue

        # Determine the staged content path for this specific artifact.
        # The artifact_id is embedded in the URN for directives.
        artifact_id = _artifact_id_from_provenance(prov)
        filename = _artifact_filename(kind, slug, artifact_id)
        staged_path = staging_dir.path_for_content(kind, filename)

        if not staged_path.exists():
            # Staged file missing — skip (shouldn't happen in normal flow).
            continue

        # Scan only this specific staged file, treating the staging root as repo_root
        # so that _repo_relative_string produces stable paths.
        lint_result = run_neutrality_lint(
            repo_root=staging_dir.root,
            scan_roots=[staged_path],
        )

        # Gate only on actual banned-term hits — not on stale allowlist entries.
        # Stale entries are expected when scanning staged files against the default
        # allowlist (which references repo-relative paths that don't exist in staging).
        if lint_result.hits:
            # Collect up to 5 hit matches for the error message.
            terms = tuple(hit.match for hit in lint_result.hits[:5])
            raise NeutralityGateViolation(
                artifact_urn=prov.artifact_urn,
                detected_terms=terms,
                staging_dir=staging_dir.root,
            )


def stage_and_validate(
    request: SynthesisRequest,
    staging_dir: StagingDir,
    results: list[tuple[Mapping[str, Any], ProvenanceEntry]],
    validation_callback: Callable[[StagingDir], None],
) -> list[str]:
    """Write staged files and run the full pre-promote validation stack.

    This is the truthful implementation for CLI ``--dry-run``: all artifact
    bodies and provenance sidecars are materialized in the staging tree, the
    project DRG overlay is emitted via ``validation_callback``, and the
    neutrality gate scans the exact staged bytes that a real promote would use.

    No live-tree ``os.replace`` calls occur here.

    Returns
    -------
    list[str]
        Stable ``kind:slug`` selectors for the staged artifact set.
    """
    staged_artifacts: list[str] = []

    for body, prov in results:
        kind = prov.artifact_kind
        slug = prov.artifact_slug
        artifact_id = _artifact_id_from_provenance(prov)

        filename = _artifact_filename(kind, slug, artifact_id)
        yaml_bytes = canonical_yaml(body)

        staged_content_path = staging_dir.path_for_content(kind, filename)
        staging_dir.guard.write_bytes(
            staged_content_path,
            yaml_bytes,
            caller="write_pipeline.stage_and_validate[content]",
        )

        staged_prov_path = staging_dir.path_for_provenance(kind, slug)
        dump_provenance(prov, staged_prov_path, staging_dir.guard)
        staged_artifacts.append(f"{kind}:{slug}")

    validation_callback(staging_dir)
    _run_neutrality_gate(staging_dir, results, request.evidence)
    return staged_artifacts


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def _stage_artifacts(
    guard: PathGuard,
    staging_dir: StagingDir,
    results: list[tuple[Mapping[str, Any], ProvenanceEntry]],
) -> list[tuple[str, str, str, str, bytes]]:
    """Write every (body, provenance) pair into the staged subtrees (step 1).

    Returns the staged item tuples ``(kind, slug, filename, artifact_id,
    yaml_bytes)`` — extracted from :func:`promote` (S3776) as its own
    testable unit.
    """
    staged_items: list[tuple[str, str, str, str, bytes]] = []

    for body, prov in results:
        kind = prov.artifact_kind
        slug = prov.artifact_slug

        # Infer artifact_id from the provenance URN for directive filename
        artifact_id = _artifact_id_from_provenance(prov)

        filename = _artifact_filename(kind, slug, artifact_id)
        yaml_bytes = canonical_yaml(body)

        # Write content into staged doctrine tree
        staged_content_path = staging_dir.path_for_content(kind, filename)
        guard.write_bytes(staged_content_path, yaml_bytes, caller="write_pipeline.promote[content]")

        # Write provenance sidecar into staged charter tree
        staged_prov_path = staging_dir.path_for_provenance(kind, slug)
        dump_provenance(prov, staged_prov_path, guard)

        staged_items.append((kind, slug, filename, artifact_id or slug, yaml_bytes))

    return staged_items


def _validate_or_fail(
    staging_dir: StagingDir,
    validation_callback: Callable[[StagingDir], None],
) -> None:
    """Run the validation callback; route a failure to ``.failed/`` (step 2).

    WP04 wires its DRG + schema validation gate in via ``validation_callback``.
    A raised exception aborts and routes to ``staging_dir.commit_to_failed()``.
    """
    try:
        validation_callback(staging_dir)
    except Exception as exc:
        staging_dir.commit_to_failed(f"Validation failed: {exc}")
        raise


def _ensure_live_dirs(guard: PathGuard, repo_root: Path) -> None:
    """Create destination directories for every doctrine kind + provenance.

    Uses ``pack_kind_subdir()`` so the names match the .gitignore
    whitelist (step 3 prep).
    """
    for kind in ("directive", "tactic", "styleguide"):
        guard.mkdir(
            project_pack_path(repo_root, _pack_kind_subdir(kind)),
            caller="write_pipeline.promote[mkdir-doctrine]",
        )

    guard.mkdir(
        repo_root / _KITTIFY_DIRNAME / _CHARTER_DIRNAME / _PROVENANCE_DIRNAME,
        caller="write_pipeline.promote[mkdir-provenance]",
    )


def _replace_one_artifact(
    guard: PathGuard,
    staging_dir: StagingDir,
    repo_root: Path,
    body: Mapping[str, Any],
    prov: ProvenanceEntry,
) -> ManifestArtifactEntry:
    """Promote one staged (body, provenance) pair into the live tree.

    No-op-stable (#1912): skips the ``os.replace`` for content/provenance
    when the staged bytes are unchanged modulo their respective volatile
    fields, so an unchanged file's mtime is left alone. Returns the
    resulting manifest entry.
    """
    kind = prov.artifact_kind
    slug = prov.artifact_slug

    artifact_id_ = _artifact_id_from_provenance(prov)

    filename = _artifact_filename(kind, slug, artifact_id_)
    yaml_bytes = canonical_yaml(body)
    content_hash = _compute_content_hash(yaml_bytes)

    # Content: staging → .kittify/charter-packs/<kind-subdir>/<filename>
    #
    # The doctrine body YAML carries no volatile fields, so a no-op run
    # produces byte-identical content. Skip the replace when unchanged
    # so the tracked file (and its mtime) is left alone (#1912).
    staged_content = staging_dir.path_for_content(kind, filename)
    live_content = project_pack_path(repo_root, _pack_kind_subdir(kind), filename)
    if not _substantively_equal(yaml_bytes, live_content, frozenset()):
        guard.replace(staged_content, live_content, caller="write_pipeline.promote[content-replace]")
    # else: unchanged — staged copy is discarded by staging_dir.wipe().

    # Provenance: staging → .kittify/charter/provenance/<kind>-<slug>.yaml
    #
    # Provenance sidecars stamp volatile fields (produced_at,
    # synthesizer_version, synthesis_run_id, generated_at) every run.
    # Skip the replace when the sidecar is unchanged modulo those
    # fields so the prior committed timestamp/version survives (#1912).
    staged_prov = staging_dir.path_for_provenance(kind, slug)
    live_prov = (
        repo_root / _KITTIFY_DIRNAME / _CHARTER_DIRNAME / _PROVENANCE_DIRNAME / f"{kind}-{slug}.yaml"
    )
    staged_prov_bytes = staged_prov.read_bytes()
    if not _substantively_equal(staged_prov_bytes, live_prov, _VOLATILE_PROVENANCE_FIELDS):
        guard.replace(staged_prov, live_prov, caller="write_pipeline.promote[prov-replace]")
    # else: unchanged — staged copy is discarded by staging_dir.wipe().

    rel_content = str(live_content.relative_to(repo_root))
    rel_prov = provenance_path_for(kind, slug)

    return ManifestArtifactEntry(
        kind=kind,
        slug=slug,
        path=rel_content,
        provenance_path=rel_prov,
        content_hash=content_hash,
    )


def _promote_graph_overlay(guard: PathGuard, staging_dir: StagingDir, repo_root: Path) -> None:
    """Promote the staged DRG overlay graph, if any (no-op-stable).

    The graph overlay stamps generated_at/generated_by on regeneration, so
    skip the replace when only those volatile fields changed (#1912 — avoid
    graph.yaml churn).
    """
    staged_graph = staging_dir.root / PROJECT_PACK_DIRNAME / _GRAPH_FILENAME
    if not staged_graph.exists():
        return

    live_graph = project_pack_path(repo_root, PROJECT_GRAPH_FILENAME)
    if not _substantively_equal(staged_graph.read_bytes(), live_graph, _VOLATILE_GRAPH_FIELDS):
        guard.replace(staged_graph, live_graph, caller="write_pipeline.promote[graph-replace]")


def _promote_artifacts(
    guard: PathGuard,
    staging_dir: StagingDir,
    repo_root: Path,
    results: list[tuple[Mapping[str, Any], ProvenanceEntry]],
) -> list[ManifestArtifactEntry]:
    """Ordered ``os.replace`` of every artifact + the graph overlay (step 3).

    Extracted from :func:`promote` (S3776) as the caller's single try/except
    boundary around all live-tree replaces.
    """
    manifest_entries = [
        _replace_one_artifact(guard, staging_dir, repo_root, body, prov) for body, prov in results
    ]
    _promote_graph_overlay(guard, staging_dir, repo_root)
    return manifest_entries


def _build_manifest(
    mission_id: str | None,
    run_id: str,
    results: list[tuple[Mapping[str, Any], ProvenanceEntry]],
    manifest_entries: list[ManifestArtifactEntry],
    repo_root: Path,
) -> SynthesisManifest:
    """Assemble + finalize a fresh ``SynthesisManifest`` (step 4, no override).

    Builds a ``SynthesisManifest`` instance and routes it through the single
    canonical finalizer (data-model.md "Contract: finalize_manifest") instead
    of hand-syncing a raw dict — the hash is always derived from the FULL
    instance, so no field (incl. bundle_content_hash) can be silently
    omitted (closes BLOCKER-2).
    """
    # Determine primary adapter id/version (aggregate from provenance).
    adapter_ids = {prov.adapter_id for _, prov in results}
    adapter_versions = {prov.adapter_version for _, prov in results}
    primary_adapter_id = adapter_ids.pop() if len(adapter_ids) == 1 else ""
    primary_adapter_version = adapter_versions.pop() if len(adapter_versions) == 1 else ""

    synthesizer_ver = _get_synthesizer_version()
    sorted_artifacts = sorted(manifest_entries, key=lambda e: (e.kind, e.slug))

    manifest = SynthesisManifest(
        mission_id=mission_id,
        created_at=now_utc_iso(),
        run_id=run_id,
        adapter_id=primary_adapter_id,
        adapter_version=primary_adapter_version,
        synthesizer_version=synthesizer_ver,
        manifest_hash="0" * 64,
        artifacts=sorted_artifacts,
        bundle_content_hash=compute_bundle_content_hash(repo_root),
    )
    return finalize_manifest(manifest)


def _write_manifest_file(
    guard: PathGuard,
    repo_root: Path,
    manifest: SynthesisManifest,
) -> SynthesisManifest:
    """Write the manifest-last commit marker, no-op-stably (step 4 write).

    The manifest stamps volatile fields (created_at, run_id, adapter_version,
    synthesizer_version, manifest_hash) on every run. Skip the rewrite when
    the manifest is unchanged modulo those fields. A substantive change
    (artifact set, hashes, adapter identity) still alters the comparison and
    triggers a rewrite, so the on-disk manifest can never go stale relative
    to the artifacts, and records the versions that actually ran.

    Returns the manifest callers should observe: the freshly written one, or
    — when the write was skipped — the prior on-disk manifest (preserving its
    timestamps) so callers see the persisted state rather than the discarded
    fresh one.
    """
    manifest_path = repo_root / MANIFEST_PATH
    guard.mkdir(manifest_path.parent, caller="write_pipeline.promote[mkdir-manifest]")
    new_manifest_bytes = canonical_yaml(manifest.model_dump(mode="python"))
    if _substantively_equal(new_manifest_bytes, manifest_path, _VOLATILE_MANIFEST_FIELDS):
        return load_manifest(manifest_path)

    dump_manifest(manifest, manifest_path, guard)
    return manifest


def promote(
    request: SynthesisRequest,
    staging_dir: StagingDir,
    results: list[tuple[Mapping[str, Any], ProvenanceEntry]],
    validation_callback: Callable[[StagingDir], None],
    repo_root: Path | None = None,
    mission_id: str | None = None,
    manifest_override: SynthesisManifest | None = None,
) -> SynthesisManifest:
    """Execute the full stage-and-promote pipeline for a synthesis run.

    Parameters
    ----------
    request:
        The ``SynthesisRequest`` envelope (for ``run_id`` and adapter info).
    staging_dir:
        Pre-created staging directory (see ``StagingDir.create``).
    results:
        List of ``(body, ProvenanceEntry)`` tuples from ``run_all()``.
    validation_callback:
        Callable invoked with the staged tree *before* promote.  WP04 wires
        its DRG + schema validation gate here.  A raised exception aborts and
        routes to ``staging_dir.commit_to_failed()``.
    repo_root:
        Repository root path.  Defaults to the grandparent of the staging
        dir's root (inferred from ``staging_dir.root``).
    mission_id:
        Optional ULID to record in the manifest for audit purposes.
    manifest_override:
        Optional authoritative manifest to write last instead of building one
        from ``results``. Bounded resynthesis uses this to preserve untouched
        manifest entries while still letting ``promote()`` own manifest-last
        atomicity.

    Returns
    -------
    SynthesisManifest
        The written manifest (manifest-last commit marker).

    Raises
    ------
    StagingPromoteError
        If any ``os.replace`` call or the manifest write fails.
    """
    if repo_root is None:
        # staging_dir.root == .kittify/charter/.staging/<run_id>
        # → repo_root == staging_dir.root.parent.parent.parent.parent
        repo_root = staging_dir.root.parent.parent.parent.parent

    guard = staging_dir.guard
    run_id = staging_dir.run_id

    # Step 1: write every (body, provenance) pair into the staged subtrees.
    _stage_artifacts(guard, staging_dir, results)

    # Step 2: validation callback (WP04 wires DRG + schema validation here).
    _validate_or_fail(staging_dir, validation_callback)

    # ------------------------------------------------------------------
    # Step 2b: neutrality lint gate (FR-011, FR-012)
    #
    # Runs AFTER validation and BEFORE the first os.replace call.
    # Scans generic-scoped staged artifacts for language-specific bias.
    # On NeutralityGateViolation the staging dir is NOT wiped — the
    # StagingDir context manager in the caller routes it to .failed/.
    # ------------------------------------------------------------------
    _run_neutrality_gate(staging_dir, results, request.evidence)

    # Step 3: ordered os.replace into final live trees.
    _ensure_live_dirs(guard, repo_root)
    try:
        manifest_entries = _promote_artifacts(guard, staging_dir, repo_root, results)
    except Exception as exc:
        # Do NOT wipe staging — let the caller (StagingDir context manager) route
        # to .failed/.  Manifest has NOT been written → partial-and-rerunable state.
        raise StagingPromoteError(
            run_id=run_id,
            staging_dir=str(staging_dir.root),
            cause=str(exc),
        ) from exc

    # Step 4: manifest last — the authoritative commit marker (KD-2).
    manifest = (
        _build_manifest(mission_id, run_id, results, manifest_entries, repo_root)
        if manifest_override is None
        else manifest_override
    )

    try:
        written_manifest = _write_manifest_file(guard, repo_root, manifest)
    except Exception as exc:
        # Manifest write failed — staging NOT wiped; partial state preserved.
        raise StagingPromoteError(
            run_id=run_id,
            staging_dir=str(staging_dir.root),
            cause=f"manifest write failed: {exc}",
        ) from exc

    # Step 5: wipe staging dir (only on full success).
    staging_dir.wipe()

    # Step 6: return manifest.
    return written_manifest


__all__ = [
    "promote",
    "stage_and_validate",
    "compute_written_artifacts",
    "StagedArtifact",
]
