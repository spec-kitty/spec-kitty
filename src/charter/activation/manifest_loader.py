"""Canonical cached loader authority for ``expected-artifacts.yaml`` (#3770).

**Relocation (mission expected-artifacts-loader-unification-01M1C9VQ, WP01):**
this module IS the single org-first / built-in-fallback / ``model_validate`` /
wrap-``ValidationError``-into-:class:`ManifestSchemaError` authority, moved
here from ``specify_cli.dossier.manifest.ManifestRegistry.load_manifest``
(the logic below is a faithful transcription of that method, not a
re-derivation). It lives in ``charter.activation`` — not
``charter.offering.missions`` — because it needs
:func:`charter.activation.org_expected_artifacts.resolve_org_expected_artifacts`
and :func:`charter.offering.drg.org_pack_config.resolve_existing_org_roots`;
activation may import offering, but offering must not import activation
(D1, ``research.md``), so the loader cannot live in offering without an
inverted dependency.

``specify_cli.dossier.manifest.ManifestRegistry.load_manifest`` is now a
thin delegate to :func:`load_manifest` below (FR-003); ``ManifestRegistry``
keeps its sibling completeness methods (``get_required_artifacts`` etc.),
which are genuinely ``specify_cli``-owned and do NOT move (D3). The old
import path re-exports ``load_manifest``, :class:`ManifestSchemaError`, and
:class:`~charter.offering.missions.repository.MalformedManifestError` so no
existing consumer's import breaks (FR-002, C-001).

**Sibling-error model (D2).** Present-but-unparseable manifests (YAML-syntax,
non-mapping, or present-but-unreadable) raise
:class:`~charter.offering.missions.repository.MalformedManifestError`
(already charter-resident) on BOTH tiers. Built-in-tier YAML-syntax
fail-loud shipped in ``1763bf2ae3``, via
:meth:`~charter.offering.missions.repository.MissionTemplateRepository.get_expected_artifacts`,
which this module does not catch, so that error propagates unchanged.
FR-007/FR-012 (#3412, mission ``expected-artifacts-loader-unification-01M1C9VQ``
WP03) widened both tiers symmetrically: the org tier's own read
(:func:`charter.activation.org_expected_artifacts.resolve_org_expected_artifacts`)
now also raises ``MalformedManifestError`` for a present-but-broken org
file instead of swallowing it to "no org contribution", and the built-in
tier's ``get_expected_artifacts`` now raises on present-but-unreadable
(``OSError``/``UnicodeDecodeError``) too, not only ``YAMLError``.
Present-but-schema-invalid manifests (valid YAML, ``extra="forbid"``
violation) raise :class:`ManifestSchemaError` on EITHER tier — a sibling of
``MalformedManifestError``, not a synonym: both are distinct from ``None``
(genuine absence).

Key concepts:
- :func:`load_manifest`: the cached authority function this module exists for.
- :class:`ManifestSchemaError`: fail-loud channel for schema/``extra="forbid"``
  violations (moved here from ``specify_cli.dossier.manifest``).
- Module-level ``_cache``: keyed ``(mission_type, org_roots)`` — see
  :func:`load_manifest`'s docstring for the non-shadowing/declaration-order
  guarantees this key shape preserves (NFR-002).

See: kitty-specs/expected-artifacts-loader-unification-01M1C9VQ/data-model.md
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import cast

from pydantic import ValidationError

from charter.offering.missions.expected_artifact_manifest import ExpectedArtifactManifest
from charter.offering.missions.repository import MissionTemplateRepository

# NOTE: `charter.offering.missions.repository.MalformedManifestError` is this
# module's sibling error (see the "Sibling-error model" docstring section
# above) -- it is raised by `MissionTemplateRepository.get_expected_artifacts`
# and propagates through `load_manifest` unchanged below, so it is
# deliberately NOT imported here (nothing in this module constructs or
# catches it). `specify_cli.dossier.manifest` re-exports it directly from
# `charter.offering.missions.repository`, not through this module.

__all__ = [
    "ManifestSchemaError",
    "clear_cache",
    "load_manifest",
]

logger = logging.getLogger(__name__)


class ManifestSchemaError(Exception):
    """Raised when a *found* ``expected-artifacts.yaml`` fails schema
    validation, as distinct from a manifest that is absent entirely or one
    that fails at the YAML-syntax level (that case raises the sibling
    :class:`~charter.offering.missions.repository.MalformedManifestError`
    instead -- see the module docstring's "Sibling-error model" section).

    Deliberately NOT a :class:`pydantic.ValidationError` subclass:
    ``ValidationError`` is a Rust-backed pydantic-core type not designed for
    subclassing, and the model-level tests in ``tests/dossier/test_manifest.py``
    construct :class:`~charter.offering.missions.expected_artifact_manifest.ExpectedArtifactSpec`/
    :class:`~charter.offering.missions.expected_artifact_manifest.ExpectedArtifactManifest`
    directly and assert the raw ``pydantic.ValidationError`` from *that*
    construction -- unaffected by this type, which only wraps failures at the
    :func:`load_manifest` boundary.

    This is the fix for a MAJOR adversarial-review finding: catching
    ``except pydantic.ValidationError`` around the whole
    ``Indexer.index_feature(...)`` call (in
    ``specify_cli.sync.dossier_pipeline.sync_feature_dossier``) misattributes
    ANY ``ValidationError`` raised while indexing -- including a genuine
    ``ArtifactRef``/``MissionDossier`` model-validator bug, raised well
    *after* the manifest has already loaded successfully -- to "your
    ``expected-artifacts.yaml`` is broken". Catching this domain-specific
    type instead of the raw pydantic type lets a real indexer bug fall
    through to the generic ``except Exception`` branch (ERROR + stack
    trace) where it belongs.

    Args:
        mission_type: The mission type the manifest was resolved for.
        origin: A human-legible label for the manifest's source -- a file
            path for the built-in/project tiers (``ConfigResult.origin``);
            a descriptive org-tier label when no single file path is
            available (see the org-tier branch of :func:`load_manifest`).

    The underlying :class:`pydantic.ValidationError` is chained via
    ``raise ... from exc``, so it is always available as ``__cause__`` --
    :meth:`__str__` reads it from there rather than storing a redundant
    third field.
    """

    def __init__(self, mission_type: str, origin: str) -> None:
        self.mission_type = mission_type
        self.origin = origin
        super().__init__(mission_type, origin)

    def __str__(self) -> str:
        underlying = self.__cause__
        detail = str(underlying) if underlying is not None else "unknown validation failure"
        return f"expected-artifacts.yaml schema-invalid for mission type {self.mission_type!r} ({self.origin}): {detail}"


#: Cache key is ``(mission_type, org_roots_fingerprint)``, NOT bare
#: ``mission_type`` (FR-008 / WP05 cache-key fix, preserved verbatim by this
#: relocation). ``org_roots_fingerprint`` is a **declaration-ordered** tuple
#: of existing org-root path strings -- NOT sorted. Per NFR-003 / C-4
#: ("last-EXISTING-match wins"), two ``repo_root``s that declare the SAME
#: set of org roots in a DIFFERENT order can resolve to different
#: manifests; sorting the key would collide those two cases onto one cache
#: entry and silently hand the second ``repo_root`` the first's
#: (order-wrong) manifest. The tuple is empty when ``repo_root`` is ``None``
#: (today's default call shape, unchanged) or when no configured org pack
#: resolves to an existing path for that ``repo_root``. Without
#: order-preservation, the cache -- process-global and previously keyed on
#: ``mission_type`` alone -- would let the FIRST resolution of a given
#: mission type in a long-lived process (a daemon, or a test session
#: touching two projects with different org overrides) permanently shadow
#: every later ``repo_root``'s result for that same mission type: project
#: B's request would silently get project A's org override (or lack
#: thereof). Errors are NOT cached -- only successful loads and genuine
#: ``None`` are (NFR-002). See
#: ``tests/dossier/test_manifest.py::TestManifestRegistryOrgTier``.
_cache: dict[tuple[str, tuple[str, ...]], ExpectedArtifactManifest | None] = {}


def _offering_template_repository() -> MissionTemplateRepository:
    """Return the offering's mission template repository bound to the built-in tree.

    Lazy-friendly seam (mirrors the pre-relocation discipline in
    ``specify_cli.dossier.manifest``): the single authority for reading
    ``<type>/expected-artifacts.yaml`` from the canonical built-in mission
    tree. Tests monkeypatch this function (not ``MissionTemplateRepository``
    itself) to inject fixture content through the real ``load_manifest``
    call path -- see ``tests/dossier/test_manifest.py``'s
    ``TestSchemaHardeningAndLoudFailure`` fake-repository seam.
    """
    return MissionTemplateRepository.default()


def _resolve_existing_org_roots(repo_root: Path) -> list[Path]:
    """Return configured org Charter Pack roots that exist on disk for *repo_root*.

    Delegates to the shared
    :func:`charter.offering.drg.org_pack_config.resolve_existing_org_roots`
    primitive (#3525 Fold A) rather than re-implementing the filter
    comprehension -- the same primitive every other "does this org root
    exist" consumer routes onto: a stale/never-fetched ``local_path`` config
    entry degrades to "no org contribution" for this call rather than
    raising.
    """
    from charter.offering.drg.org_pack_config import resolve_existing_org_roots  # noqa: PLC0415

    # `cast`, not a suppression: this module is checked under
    # `[[tool.mypy.overrides]] module = ["charter.*"] follow_imports = "skip"`
    # (pyproject.toml), so the lazily-imported `resolve_existing_org_roots`
    # resolves to `Any` regardless of its real (already `list[Path]`)
    # signature -- the same pre-existing gap affects the identical pattern in
    # `charter.activation.active_charter_service_builder._self_resolve_existing_org_roots`.
    return cast("list[Path]", resolve_existing_org_roots(repo_root))


def load_manifest(mission_type: str, repo_root: Path | None = None) -> ExpectedArtifactManifest | None:
    """Load manifest for mission type from the canonical built-in tree.

    Reads ``<type>/expected-artifacts.yaml`` from the built-in mission tree
    via :meth:`~charter.offering.missions.repository.MissionTemplateRepository.get_expected_artifacts`
    and adapts the returned ``ConfigResult`` into an
    :class:`~charter.offering.missions.expected_artifact_manifest.ExpectedArtifactManifest`.
    The adapted model -- not the raw ``ConfigResult`` -- is cached (NFR-002).

    Returns ``None`` if the manifest is genuinely absent (degraded mode for
    custom/unknown missions on the given tier). A *found*, syntactically
    -valid manifest that fails **schema** validation (e.g. a typo'd/extra
    key, rejected by ``extra="forbid"``) raises :class:`ManifestSchemaError`
    instead of being silently swallowed; a *found* manifest that is not even
    valid YAML, is unreadable, or is not a mapping raises the sibling
    :class:`~charter.offering.missions.repository.MalformedManifestError` on
    EITHER tier (built-in: shipped, ``1763bf2ae3``, widened to
    present-but-unreadable by FR-012; org: FR-007/FR-012, #3412) -- see the
    module docstring's "Sibling-error model" section.

    When *repo_root* is given and resolves to 1+ existing configured org
    roots, an org-pack ``<org_root>/missions/<mission_type>/expected-artifacts.yaml``
    (see :func:`charter.activation.org_expected_artifacts.resolve_org_expected_artifacts`,
    contract C-4) takes precedence over the built-in file, whole-file --
    never field-merged with it. *repo_root* is optional and defaults to
    ``None`` (built-in-tree-only resolution) so the sole
    ``repo_root``-agnostic production caller (``specify_cli.sync.namespace.resolve_manifest_version``)
    is unaffected by this signature.

    Args:
        mission_type: Mission type (e.g., 'software-dev', 'research')
        repo_root: Project root to resolve org-pack overrides for, or
            ``None`` (default) for built-in-tree-only resolution.

    Returns:
        ExpectedArtifactManifest if found and valid, None if genuinely
        absent on every consulted tier.

    Raises:
        ManifestSchemaError: If the manifest file is found, parses as
            valid YAML, but fails *schema* validation (e.g. an
            unrecognized/typo'd key, given
            ``model_config = ConfigDict(extra="forbid")`` on both models).
            Carries typed ``mission_type`` and ``origin`` fields naming the
            resolved manifest's source (e.g.
            ``"doctrine/software-dev/expected-artifacts.yaml"`` for the
            built-in/project tiers; a descriptive org-tier label when no
            single file path is available), and chains the underlying
            ``pydantic.ValidationError`` via ``__cause__`` -- so
            ``str(exc)`` is always operator-actionable (names both the
            file and the bad key) for any consumer, not only one that
            knows to read an exception note.
        MalformedManifestError: On either tier, if the manifest file is
            present but fails to parse as YAML, is unreadable, or is not a
            mapping -- propagated unchanged from
            :meth:`~charter.offering.missions.repository.MissionTemplateRepository.get_expected_artifacts`
            (built-in tier) or
            :func:`~charter.activation.org_expected_artifacts.resolve_org_expected_artifacts`
            (org tier, FR-007/FR-012).
    """
    org_roots = _resolve_existing_org_roots(repo_root) if repo_root is not None else []
    cache_key = (mission_type, tuple(str(root) for root in org_roots))
    if cache_key in _cache:
        return _cache[cache_key]

    org_parsed: object | None = None
    if org_roots:
        from charter.activation.org_expected_artifacts import (  # noqa: PLC0415
            resolve_org_expected_artifacts,
        )

        org_parsed = resolve_org_expected_artifacts(org_roots, mission_type)

    if org_parsed is not None:
        return _validate_and_cache_org_manifest(mission_type, org_roots, org_parsed, cache_key)

    config = _offering_template_repository().get_expected_artifacts(mission_type)

    if config is None:
        logger.debug(f"Manifest not found for mission type: {mission_type}")
        _cache[cache_key] = None
        return None

    try:
        manifest = ExpectedArtifactManifest.model_validate(config.parsed)
    except ValidationError as exc:
        # Domain `ManifestSchemaError` (typed `mission_type`/`origin` fields,
        # chaining the raw ValidationError via `__cause__`) instead of
        # letting the raw `pydantic.ValidationError` cross this module's
        # boundary -- a bare `except pydantic.ValidationError` at any
        # consumer is a proxy for "manifest schema failure" that misfires on
        # ANY ValidationError raised later in the same call stack.
        raise ManifestSchemaError(mission_type, config.origin) from exc
    _cache[cache_key] = manifest
    logger.info(f"Loaded manifest for {mission_type}: {len(manifest.get_step_ids())} steps")
    return manifest


def _validate_and_cache_org_manifest(
    mission_type: str,
    org_roots: list[Path],
    org_parsed: object,
    cache_key: tuple[str, tuple[str, ...]],
) -> ExpectedArtifactManifest:
    """Schema-validate an org-tier parsed mapping and cache it on success.

    Split out of :func:`load_manifest` to keep that function's cyclomatic
    complexity within the project ceiling (NFR-003). No legacy
    ``except Exception -> None`` swallow here (removed by this WP): an
    operator authored this org override and expects it to take effect, so a
    schema-invalid org manifest fails exactly as loudly as a schema-invalid
    built-in one.
    """
    try:
        manifest = ExpectedArtifactManifest.model_validate(org_parsed)
    except ValidationError as exc:
        # `resolve_org_expected_artifacts` returns only the parsed mapping,
        # not which org_root/file matched (last-EXISTING-match-wins means it
        # isn't necessarily the last root in the list either -- only the
        # last root with a *matching file*), so no single precise path is
        # available here. `origin` is therefore a descriptive label naming
        # the org tier + mission_type + the full set of roots that were
        # checked, rather than a fabricated/guessed file path.
        origin = (
            f"org-tier expected-artifacts.yaml for mission type {mission_type!r} "
            f"(no single source file path available; checked org roots: "
            f"{', '.join(str(root) for root in org_roots)})"
        )
        raise ManifestSchemaError(mission_type, origin) from exc
    _cache[cache_key] = manifest
    logger.info(f"Loaded org-tier manifest for {mission_type}: {len(manifest.get_step_ids())} steps")
    return manifest


def clear_cache() -> None:
    """Clear the module-level manifest cache in place (useful for testing).

    Mutates the existing ``_cache`` dict object (``.clear()``) rather than
    rebinding the module global to a new dict -- ``specify_cli.dossier.manifest.ManifestRegistry._cache``
    is an alias to this same dict object (see that module), so callers that
    hold a reference to either name observe the same, single cache.
    """
    _cache.clear()
