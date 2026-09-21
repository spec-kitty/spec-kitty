"""Unified charter bundle manifest (v1.0.0).

Declares the files ``src/charter/activation/sync.py :: sync()`` materializes as the
project's governance bundle. v1.0.0 scope is limited to the three
sync-produced derivatives. See
``docs/architecture/06_unified_charter_bundle.md`` for the full contract and
``kitty-specs/unified-charter-bundle-chokepoint-01KP5Q2G/contracts/bundle-manifest.schema.yaml``
for the JSON Schema.

Out of v1.0.0 scope (per C-012):

* ``references.yaml`` — produced by ``src/charter/activation/compiler.py``.
* ``context-state.json`` — runtime state written by
  ``src/charter/activation/context.py :: build_charter_context``.

Expanding the manifest requires a schema bump and a new migration; the
project ``.gitignore`` MAY carry additional entries for those files.

Extended in WP03 (FR-015): ``validate_synthesis_state`` cross-checks the
synthesis state added by the charter synthesizer (provenance sidecars,
synthesis manifest).  This extension is **additive only** — no schema version
bump, legacy bundles without synthesis state pass exactly as they did under
v1.0.0 (C-012 backward-compat guarantee, see ``BundleValidationResult``).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .hasher import hash_content
from .offering.artifact_kinds import DIRECT_WRITE_KINDS, ArtifactKind

if TYPE_CHECKING:
    from .activation.synthesizer.manifest import ManifestArtifactEntry

SCHEMA_VERSION: str = "2.0.0"
CHARTER_MD = Path(".kittify/charter/charter.md")
GOVERNANCE_YAML = Path(".kittify/charter/governance.yaml")
DIRECTIVES_YAML = Path(".kittify/charter/directives.yaml")
METADATA_YAML = Path(".kittify/charter/metadata.yaml")

#: consolidate-charter-bundle (WP01 / T004): the ONE shared ``charter.yaml``
#: filename constant. ``charter.yaml`` is the git-tracked, authorable
#: structured charter introduced by manifest v2.0.0 (data-model.md, contracts/
#: charter-yaml-schema.md). Import THIS constant rather than re-declaring the
#: literal path — the existing duplicated filename sets (this module's
#: Path-form constants + ``sync.py``'s str-form ``_*_FILENAME`` constants) are
#: reconciled onto this single source as their owning WPs land (S1192
#: pre-emption; do NOT re-scatter a second copy of the ``charter.yaml`` name).
CHARTER_YAML = Path(".kittify/charter/charter.yaml")

# Content-identity input set for the charter bundle's freshness hash
# (synthesized-drg-stale-refresh mission originally; re-scoped by
# consolidate-charter-bundle WP01 manifest v2). Post-inversion the ONLY
# content-hash input is ``charter.yaml`` itself — the four legacy derived
# files (governance/directives/references/metadata) it replaces are retired
# (data-model.md Landmine 1/contracts/manifest-v2.md M1). Do NOT import this
# constant from the ``specify_cli`` reader — that would invert the dependency
# direction (mirrors ``specify_cli.charter_runtime.freshness.computer::
# _BUNDLE_FILES``, which independently owns its own copy).
BUNDLE_CONTENT_HASH_FILES: tuple[str, ...] = ("charter.yaml",)

# Synthesis state paths (all relative to repo root)
SYNTHESIS_MANIFEST_PATH = Path(".kittify/charter/synthesis-manifest.yaml")
PROVENANCE_DIR = Path(".kittify/charter/provenance")
DOCTRINE_DIR = Path(".kittify/doctrine")
STAGING_DIR = Path(".kittify/charter/.staging")

# Artifact file-extension suffixes for each kind, derived from the single
# registration-writing kind authority (WP01 / NFR-002): every kind that
# ``project_registration.py`` / the DRG project scanner / the synthesis
# manifest's ``ManifestArtifactEntry.kind`` Literal register is covered here
# (#4833 -- `agent_profile`/`procedure` no longer trip "unknown kind"). Do
# NOT hand-maintain a second copy of this mapping -- import
# ``DIRECT_WRITE_KINDS`` and derive.
_KIND_SUFFIX: dict[str, str] = {
    kind: ArtifactKind(kind).glob_pattern.removeprefix("*") for kind in DIRECT_WRITE_KINDS
}
_ALL_ARTIFACT_PATTERNS = list(_KIND_SUFFIX.values())


class CharterBundleManifest(BaseModel):
    """Typed declaration of the unified charter bundle contract."""

    schema_version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    tracked_files: list[Path] = Field(min_length=1)
    derived_files: list[Path]
    derivation_sources: dict[Path, Path]
    content_hash_files: list[Path] = Field(default_factory=list)
    """The content-hash input set (v2.0.0 / M1) — a field DISTINCT from
    ``derived_files``. Sourced from :data:`BUNDLE_CONTENT_HASH_FILES`. This
    field is deliberately NOT included in the ``tracked ∩ derived = ∅``
    disjointness check below: it was always a separate concern (the historic
    4-vs-3 file-count mismatch between the old ``BUNDLE_CONTENT_HASH_FILES``
    tuple and ``derived_files`` is exactly that distinction, made explicit).
    Landmine 1 (data-model.md): do NOT fold this into ``derived_files`` —
    ``charter.yaml`` is tracked/authored, not derived."""
    gitignore_required_entries: list[str]

    model_config = ConfigDict(frozen=True)

    @model_validator(mode="after")
    def _validate(self) -> CharterBundleManifest:
        # No path may appear in both tracked and derived. UNTOUCHED by the
        # v2.0.0 manifest bump (Landmine 1 / M2) — charter.yaml lives only in
        # tracked_files, never derived_files, so this invariant continues to
        # hold without modification.
        tracked = set(self.tracked_files)
        derived = set(self.derived_files)
        overlap = tracked & derived
        if overlap:
            raise ValueError(
                f"Paths appear in both tracked and derived: {sorted(str(p) for p in overlap)}"
            )
        # Every key in derivation_sources must appear in derived_files.
        missing_keys = set(self.derivation_sources.keys()) - derived
        if missing_keys:
            raise ValueError(
                "derivation_sources keys not in derived_files: "
                f"{sorted(str(p) for p in missing_keys)}"
            )
        # Every value in derivation_sources must appear in tracked_files.
        missing_values = set(self.derivation_sources.values()) - tracked
        if missing_values:
            raise ValueError(
                "derivation_sources values not in tracked_files: "
                f"{sorted(str(p) for p in missing_values)}"
            )
        return self


CANONICAL_MANIFEST: CharterBundleManifest = CharterBundleManifest(
    schema_version=SCHEMA_VERSION,
    tracked_files=[CHARTER_MD, CHARTER_YAML],
    derived_files=[],
    derivation_sources={},
    content_hash_files=[CHARTER_YAML],
    gitignore_required_entries=[],
)


# ---------------------------------------------------------------------------
# synthesized-drg-stale-refresh: content-identity freshness helper
# ---------------------------------------------------------------------------


def compute_bundle_content_hash(repo_root: Path) -> str | None:
    """Compute the content-identity digest of the synced bundle files.

    Hashes each file in :data:`BUNDLE_CONTENT_HASH_FILES` (declared order)
    INDEPENDENTLY via :func:`charter.hasher.hash_content` (per-file BOM-strip
    + CRLF-normalize), then combines the per-file ``"sha256:..."`` digests
    deterministically by hashing their newline-joined concatenation. Per-file
    hashing (not concat-then-hash-once) is required: ``canonical_yaml`` only
    strips a *leading* BOM of a whole payload, so a BOM on a non-first file
    would otherwise survive undetected (data-model.md fact #14).

    consolidate-charter-bundle (#2773): the input set is now the single
    authoritative ``charter.yaml`` (the four legacy files were folded into it),
    so the recipe hashes one file today; the per-file loop is retained so the
    contract stays correct if the input set ever grows again.

    This is the single canonical write-side hashing recipe (C-005): the writers
    and the freshness reader both route through it so there is exactly one
    recipe.

    Parameters
    ----------
    repo_root:
        Absolute project root.

    Returns
    -------
    str | None
        ``"sha256:<hex>"``, deterministic for fixed file content
        (mtime-agnostic). ``None`` — fail-safe, never raises — when
        ``.kittify/charter/`` is missing OR any hashed file is
        individually missing or unreadable (``OSError``,
        ``UnicodeDecodeError`` — a non-UTF-8 file raises the latter, which is
        NOT an ``OSError`` subclass and must be caught explicitly). The
        freshness reader maps ``None`` to ``stale``, never a crash (spec
        fail-posture).
    """
    charter_dir = repo_root / ".kittify" / "charter"
    digests: list[str] = []
    for name in BUNDLE_CONTENT_HASH_FILES:
        path = charter_dir / name
        if not path.exists():
            return None
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return None
        # Explicit annotation: the ``charter.*`` mypy override (pyproject.toml
        # [[tool.mypy.overrides]]) sets follow_imports="skip" for intra-package
        # imports, which erases hash_content's declared "-> str" return type
        # to Any at this call site. Annotating recovers the real type without
        # a suppression comment.
        digest: str = hash_content(text)
        digests.append(digest)
    combined: str = hash_content("\n".join(digests))
    return combined


def first_missing_bundle_file(repo_root: Path) -> str | None:
    """Return the name of the first missing content-hash bundle file, if any.

    Pure existence check over :data:`BUNDLE_CONTENT_HASH_FILES` (declared
    order) under ``.kittify/charter/`` — it does not read file content or
    compute any hash, and its own contract is independent of
    :func:`compute_bundle_content_hash` (whose fail-safe ``None``-on-missing
    behaviour is unchanged by this helper).

    Callers that need to know *which* file is missing before doing work that
    assumes a complete bundle (issue #2758) use this instead of interpreting
    a bare ``None`` from :func:`compute_bundle_content_hash`. consolidate-charter-bundle
    (#2773): the input set is now the single authoritative ``charter.yaml``, so
    this returns that path when the bundle has not been generated yet — the
    fail-loud chokepoints raise an actionable "run the migration / charter
    generate" error instead of silently persisting an un-healable ``None``
    bundle-content hash that the freshness reader
    (``specify_cli.charter_runtime.freshness.computer``) would report as
    permanently ``stale``.

    Parameters
    ----------
    repo_root:
        Absolute project root.

    Returns
    -------
    str | None
        The filename (e.g. ``"references.yaml"``) of the first missing file
        in :data:`BUNDLE_CONTENT_HASH_FILES` order, or ``None`` when every
        file is present under ``.kittify/charter/``.
    """
    charter_dir = repo_root / ".kittify" / "charter"
    for name in BUNDLE_CONTENT_HASH_FILES:
        if not (charter_dir / name).exists():
            return name
    return None


# ---------------------------------------------------------------------------
# WP03 (FR-015): Synthesis state validation extension
# ---------------------------------------------------------------------------


@dataclass
class BundleValidationResult:
    """Result of ``validate_synthesis_state()``.

    Backward-compat guarantee (C-012):
    - ``errors`` is always an empty list when no synthesis state exists.
    - ``warnings`` may mention stale ``.failed/`` staging dirs.
    - ``synthesis_state_present`` is ``False`` for legacy bundles.
    """

    synthesis_state_present: bool = False
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        """True when there are no errors (warnings are non-blocking)."""
        return len(self.errors) == 0


def validate_synthesis_state(repo_root: Path) -> BundleValidationResult:
    """Validate the synthesis state of a project bundle.

    Checks (additive — legacy bundles without synthesis state pass unchanged):

    1. Every artifact file under ``.kittify/doctrine/`` has a provenance sidecar.
       For an artifact *registered* in the synthesis manifest, the expected
       sidecar is resolved from the manifest entry's own ``provenance_path``
       field; for an unregistered (orphan/legacy) artifact, the expected
       sidecar path is derived from the filename
       (``.kittify/charter/provenance/<kind>-<slug>.yaml``) — hybrid
       resolution, #4832 / Decision 4.
    2. Every provenance sidecar references an existing artifact file, resolved
       the same hybrid way (manifest entry's ``path`` field when registered,
       filename stem-parse + filesystem walk otherwise).
    3. If ``.kittify/charter/synthesis-manifest.yaml`` is present, verify all
       listed ``content_hash`` values against on-disk bytes.
    4. Stale ``.kittify/charter/.staging/<runid>.failed/`` directories produce
       a warning (not an error) — R-7 accumulation signal (quickstart §8).
    5. No doubled-leaf artifact directories exist (``provenance/provenance/``,
       ``doctrine/styleguide/styleguide/``, …) — #3819. Checks 1/2 above are
       blind to this corruption: they key off ``Path.name`` after an
       ``rglob`` walk, so a doubled copy with the same basename as its
       correctly-placed sibling never trips a missing/orphaned-sidecar
       error. See :func:`_check_no_doubled_leaf_paths`.

    Parameters
    ----------
    repo_root:
        Absolute path to the repository root.

    Returns
    -------
    BundleValidationResult
        Structured result containing errors, warnings, and a flag indicating
        whether any synthesis state was found at all.
    """
    result = BundleValidationResult()
    _check_stale_failed_dirs(repo_root, result)

    doctrine_root = repo_root / DOCTRINE_DIR
    provenance_root = repo_root / PROVENANCE_DIR
    manifest_path = repo_root / SYNTHESIS_MANIFEST_PATH

    _check_no_doubled_leaf_paths(repo_root, provenance_root, doctrine_root, result)

    artifact_files = _collect_artifact_files(doctrine_root) if doctrine_root.exists() else []
    provenance_files = sorted(provenance_root.glob("*.yaml")) if provenance_root.exists() else []
    if not artifact_files and not provenance_files and not manifest_path.exists():
        return result

    # Fresh-seed early-exit (belt-and-suspenders): when the manifest declares
    # built_in_only=True with an empty artifact list, no user synthesis has
    # occurred.  Any residual sidecar files are stale fixtures — do not
    # validate against them.  The condition requires BOTH built_in_only AND
    # artifacts == [] so a manifest with real artifacts still gets validated.
    if manifest_path.exists() and _manifest_is_fresh_seed(manifest_path):
        result.synthesis_state_present = True
        return result

    result.synthesis_state_present = True

    by_artifact_path, by_provenance_path = _manifest_entry_indices(manifest_path)
    _check_artifacts_have_provenance(
        repo_root, artifact_files, provenance_root, by_artifact_path, result
    )
    _check_provenance_have_artifacts(
        repo_root, doctrine_root, provenance_root, by_provenance_path, result
    )
    _check_manifest_integrity(repo_root, result)
    return result


def _manifest_is_fresh_seed(manifest_path: Path) -> bool:
    """Return True when the manifest declares built_in_only=True with no artifacts.

    Called as a guard before provenance cross-checking so that a seeded
    synthesis-manifest.yaml (``built_in_only: true``, ``artifacts: []``)
    produced at project initialisation does not trigger spurious errors when
    stale fixture sidecar files are present.

    The condition is intentionally strict: BOTH ``built_in_only`` and an empty
    ``artifacts`` list are required.  A manifest with ``built_in_only: true``
    but a non-empty artifact list is an inconsistent state that warrants full
    validation.
    """
    try:
        from .activation.synthesizer.manifest import load_yaml as load_manifest  # noqa: PLC0415

        manifest = load_manifest(manifest_path)
    except Exception:  # noqa: BLE001
        # If the manifest cannot be parsed we fall through to full validation,
        # which will surface the load error via _check_manifest_integrity().
        return False
    return bool(manifest.built_in_only) and not manifest.artifacts


def _check_stale_failed_dirs(repo_root: Path, result: BundleValidationResult) -> None:
    """Warn on stale .failed/ staging directories (R-7)."""
    staging_root = repo_root / STAGING_DIR
    if not staging_root.exists():
        return
    for d in sorted(staging_root.iterdir()):
        if d.name.endswith(".failed") and d.is_dir():
            result.warnings.append(
                f"Stale failed staging directory found: {d.relative_to(repo_root)} "
                "(inspect cause.yaml, then remove to suppress this warning)"
            )


#: Directory leaves a synthesis writer can double-append onto a base that
#: already ends in that same leaf (#3819): ``provenance_root`` (the
#: provenance sidecar tree) and each per-kind doctrine subdirectory.
_DOUBLED_LEAF_BASES: tuple[str, ...] = ("directive", "tactic", "styleguide")


def _check_no_doubled_leaf_paths(
    repo_root: Path,
    provenance_root: Path,
    doctrine_root: Path,
    result: BundleValidationResult,
) -> None:
    """Flag a doubled-leaf synthesis-writer defect (#3819).

    A path-join defect can append a directory leaf onto a base that already
    ends in that same leaf, producing byte-identical duplicates nested one
    level too deep: ``.kittify/charter/provenance/provenance/<file>`` or
    ``.kittify/doctrine/styleguide/styleguide/<file>``.
    :func:`_check_artifacts_have_provenance` / :func:`_check_provenance_have_artifacts`
    cannot catch this class of corruption — they key off ``Path.name`` after
    an ``rglob`` walk, so a doubled copy sharing its correctly-placed
    sibling's basename never trips a missing/orphaned-sidecar error. This
    check inspects the directory structure directly instead.
    """
    candidates = [(provenance_root, "provenance")]
    candidates.extend((doctrine_root / kind, kind) for kind in _DOUBLED_LEAF_BASES)

    for base, leaf in candidates:
        doubled_dir = base / leaf
        if not doubled_dir.is_dir():
            continue
        for offender in sorted(p for p in doubled_dir.rglob("*") if p.is_file()):
            result.errors.append(
                "Doubled-leaf synthesis artifact detected: "
                f"'{offender.relative_to(repo_root)}' — a path-join wrote into "
                f"'{leaf}/{leaf}/' instead of the canonical '{leaf}/' (#3819)."
            )


def _collect_artifact_files(doctrine_root: Path) -> list[Path]:
    """Collect all synthesized artifact files under the doctrine root."""
    files: list[Path] = []
    for suffix in _ALL_ARTIFACT_PATTERNS:
        files.extend(doctrine_root.rglob(f"*{suffix}"))
    return files


def _load_manifest_entries(manifest_path: Path) -> list[ManifestArtifactEntry]:
    """Load synthesis-manifest artifact entries for hybrid resolution (#4832).

    Returns ``[]`` on any missing/unreadable/malformed manifest -- load and
    integrity errors for a present-but-corrupt manifest are surfaced once, by
    :func:`_check_manifest_integrity`. This helper must not duplicate that
    reporting; a silent empty index simply falls the forward/reverse checks
    back to the filesystem walk for every artifact/sidecar (equivalent to no
    manifest being registered yet).
    """
    if not manifest_path.exists():
        return []
    try:
        from .activation.synthesizer.manifest import load_yaml as load_manifest  # noqa: PLC0415

        manifest = load_manifest(manifest_path)
    except Exception:  # noqa: BLE001
        return []
    return list(manifest.artifacts)


def _manifest_entry_indices(
    manifest_path: Path,
) -> tuple[dict[str, ManifestArtifactEntry], dict[str, ManifestArtifactEntry]]:
    """Build (by artifact path, by provenance path) indices over manifest entries.

    Both dicts are keyed by the entry's own repo-relative path string (exactly
    as recorded at registration time, ``manifest.py:47-61``) -- not a
    re-derived filename parse. This is what lets a *registered* artifact
    resolve without re-parsing its on-disk stem (#4832).
    """
    entries = _load_manifest_entries(manifest_path)
    by_artifact_path = {entry.path: entry for entry in entries}
    by_provenance_path = {entry.provenance_path: entry for entry in entries}
    return by_artifact_path, by_provenance_path


def _check_artifacts_have_provenance(
    repo_root: Path,
    artifact_files: list[Path],
    provenance_root: Path,
    manifest_by_path: dict[str, ManifestArtifactEntry],
    result: BundleValidationResult,
) -> None:
    """Step 1: every artifact file must have a provenance sidecar.

    Hybrid resolution (#4832 / Decision 4): an artifact *registered* in the
    synthesis manifest resolves its expected sidecar from the manifest
    entry's own ``provenance_path`` field -- not by re-parsing the on-disk
    filename. This is what lets a registered SCREAMING-cased directive
    validate clean without a rename (FR-006). An artifact absent from the
    manifest (orphan/legacy) falls back to the filesystem filename-parse walk
    so the orphan-artifact direction of NFR-001 is preserved.
    """
    for artifact_path in sorted(artifact_files):
        rel_path = artifact_path.relative_to(repo_root)
        entry = manifest_by_path.get(rel_path.as_posix())
        if entry is not None:
            expected_prov = repo_root / entry.provenance_path
            if not expected_prov.exists():
                result.errors.append(
                    f"Artifact '{rel_path}' has no provenance sidecar "
                    f"(expected: {entry.provenance_path})"
                )
            continue
        kind, slug = _kind_and_slug_from_artifact(artifact_path)
        if kind is None or slug is None:
            continue
        expected_prov = provenance_root / f"{kind}-{slug}.yaml"
        if not expected_prov.exists():
            result.errors.append(
                f"Artifact '{rel_path}' has no provenance sidecar "
                f"(expected: {expected_prov.relative_to(repo_root)})"
            )


def _check_provenance_have_artifacts(
    repo_root: Path,
    doctrine_root: Path,
    provenance_root: Path,
    manifest_by_provenance_path: dict[str, ManifestArtifactEntry],
    result: BundleValidationResult,
) -> None:
    """Step 2: every provenance sidecar must reference an existing artifact.

    Hybrid resolution (#4832 / Decision 4): a sidecar *registered* in the
    synthesis manifest resolves its expected artifact from the manifest
    entry's own ``path`` field -- not by re-parsing ``kind``/``slug`` from
    the sidecar's ``<kind>-<slug>.yaml`` stem. A sidecar absent from the
    manifest (orphan/legacy) falls back to the stem-parse + filesystem walk
    so the orphan-sidecar direction of NFR-001 is preserved.
    """
    if not provenance_root.exists():
        return
    for prov_file in sorted(provenance_root.glob("*.yaml")):
        rel_path = prov_file.relative_to(repo_root)
        entry = manifest_by_provenance_path.get(rel_path.as_posix())
        if entry is not None:
            if not (repo_root / entry.path).exists():
                result.errors.append(
                    f"Provenance sidecar '{rel_path}' references "
                    f"non-existent artifact (kind={entry.kind}, slug={entry.slug})"
                )
            continue
        stem = prov_file.stem  # e.g. "directive-my-slug"
        parts = stem.split("-", 1)
        if len(parts) != 2:
            result.errors.append(f"Provenance file has unexpected name format: {rel_path}")
            continue
        kind, slug = parts[0], parts[1]
        if kind not in _KIND_SUFFIX:
            result.errors.append(f"Provenance file has unknown kind '{kind}': {rel_path}")
            continue
        if _find_artifact(doctrine_root, kind, slug) is None:
            result.errors.append(
                f"Provenance sidecar '{rel_path}' references "
                f"non-existent artifact (kind={kind}, slug={slug})"
            )


def _check_manifest_integrity(repo_root: Path, result: BundleValidationResult) -> None:
    """Step 3: verify synthesis manifest content hashes and self-hash if present."""
    manifest_path = repo_root / SYNTHESIS_MANIFEST_PATH
    if not manifest_path.exists():
        return
    try:
        from .activation.synthesizer.manifest import (  # noqa: PLC0415
            load_yaml as load_manifest,
            verify as verify_manifest,
            verify_manifest_hash,
        )
        manifest = load_manifest(manifest_path)
    except Exception as exc:
        result.errors.append(f"Could not load synthesis manifest: {exc}")
        return
    try:
        verify_manifest(manifest, repo_root)
    except Exception as exc:
        result.errors.append(f"Synthesis manifest integrity check failed: {exc}")
    try:
        verify_manifest_hash(manifest)
    except Exception as exc:
        result.errors.append(f"Synthesis manifest self-hash mismatch: {exc}")


def _kind_and_slug_from_artifact(path: Path) -> tuple[str | None, str | None]:
    """Extract (kind, slug) from an artifact filename.

    Returns ``(None, None)`` if the file does not match any known pattern.
    """
    name = path.name
    for kind, suffix in _KIND_SUFFIX.items():
        if name.endswith(suffix):
            base = name[: -len(suffix)]
            # For directives: "<NNN>-<slug>" → slug is everything after the first dash+digits
            if kind == "directive":
                # Strip leading "<NNN>-" prefix if present
                parts = base.split("-", 1)
                slug = parts[1] if len(parts) == 2 and parts[0].isdigit() else base
            else:
                slug = base
            return kind, slug
    return None, None


def _find_artifact(doctrine_root: Path, kind: str, slug: str) -> Path | None:
    """Find the artifact file for a given (kind, slug) under doctrine_root."""
    suffix = _KIND_SUFFIX.get(kind)
    if suffix is None:
        return None
    for candidate in doctrine_root.rglob(f"*{suffix}"):
        cand_kind, cand_slug = _kind_and_slug_from_artifact(candidate)
        if cand_kind == kind and cand_slug == slug:
            return candidate
    return None


__all__ = [
    "CANONICAL_MANIFEST",
    "CHARTER_YAML",
    "CharterBundleManifest",
    "SCHEMA_VERSION",
    # synthesized-drg-stale-refresh (BUNDLE_CONTENT_HASH_FILES is intentionally
    # module-internal — the reader consumes the compute_bundle_content_hash
    # helper, never the file-list constant — so it stays out of __all__)
    "compute_bundle_content_hash",
    # #2758: fail-closed preflight helper (WP02)
    "first_missing_bundle_file",
    # WP03 extension (FR-015)
    "BundleValidationResult",
    "validate_synthesis_state",
]
