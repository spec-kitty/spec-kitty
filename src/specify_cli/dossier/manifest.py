"""Expected artifact manifest system for mission completeness validation.

This module defines the registry for declaring which artifacts are
required/optional at each mission step. Manifests are YAML-based and
step-aware, reading from mission.yaml state machines.

**C-001 relocation (mission rc3-charter-gate-predicate-inversion-01M0GGT1,
WP04 / #3599):** the manifest *schema* -- ``ArtifactClassEnum`` /
``ExpectedArtifactSpec`` / ``ExpectedArtifactManifest`` -- moved to
:mod:`charter.offering.missions.expected_artifact_manifest`; this module keeps only
the registry (``ManifestRegistry``), which is genuinely ``specify_cli``-owned
(dossier caching/org-tier policy). The three relocated names are still
importable from here -- ``ExpectedArtifactManifest.model_validate`` is called
at RUNTIME below, not just referenced in type hints, so a
``TYPE_CHECKING``-only import would ``NameError``; instead the runtime call
site uses a lazy, function-local import, and the module-level
``__getattr__`` below (PEP 562) keeps
``from specify_cli.dossier.manifest import ExpectedArtifactManifest`` (and
its two siblings) resolving for existing importers -- see
``tests/charter_offering/missions/test_expected_artifact_manifest_relocation.py``.

**Loader-authority relocation (mission
expected-artifacts-loader-unification-01M1C9VQ, WP01 / #3770):** the
org-first / built-in-fallback / ``model_validate`` / error-wrapping *logic*
of ``ManifestRegistry.load_manifest`` moved to
:func:`charter.activation.manifest_loader.load_manifest` (the single cached
authority both runtime and charter-tier callers reach); ``ManifestSchemaError``
moved alongside it into that module. ``ManifestRegistry.load_manifest`` below
is now a thin delegate to that authority -- ``ManifestRegistry`` itself stays
here because it is a stateful class with sibling completeness methods
(``get_required_artifacts``, ``get_blocking_artifacts``, ``get_optional_artifacts``,
``validate_manifest``, ``clear_cache``) that are genuinely ``specify_cli``-owned
and do not move. This module re-exports ``load_manifest``, ``ManifestSchemaError``,
and ``MalformedManifestError`` at module level (object identity preserved --
see ``tests/dossier/test_manifest.py``'s shim-reexport-surface tests) so no
existing importer of any of the four names
(``ManifestRegistry``/``load_manifest``/``ManifestSchemaError``/``MalformedManifestError``)
from this path breaks.

Key concepts:
- ArtifactClassEnum: 6 artifact classes (input, workflow, output, evidence, policy, runtime)
- ExpectedArtifactSpec: Single expected artifact definition
- ExpectedArtifactManifest: Complete manifest for a mission (required_always, required_by_step, optional_always)
- ManifestRegistry: Step-aware querying of manifests, delegating loading/caching to the charter authority

See: kitty-specs/042-local-mission-dossier-authority-parity-export/data-model.md
See: kitty-specs/expected-artifacts-loader-unification-01M1C9VQ/data-model.md
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from charter.activation.manifest_loader import (
    ManifestSchemaError,
    _cache as _charter_manifest_cache,
    clear_cache as _clear_charter_manifest_cache,
    load_manifest as load_manifest,  # explicit re-export (compat), see __all__ note
)

# `MalformedManifestError` is defined in `charter.offering.missions.repository`
# (offering layer, owned by WP03), but runtime must reach doctrine/offering
# content only through a charter facade -- never a direct
# `charter.offering.*` import (test_runtime_charter_doctrine_boundary.py) --
# so this goes through the already-established `charter.missions` door
# (object identity preserved; see
# tests/architectural/test_charter_facades_reexport_offering.py).
from charter.missions import MalformedManifestError as MalformedManifestError

if TYPE_CHECKING:
    from charter.offering.missions import ExpectedArtifactManifest, ExpectedArtifactSpec

#: WP01 (#3770) shim re-exports (FR-002). All four relocated names remain
#: importable from this module with object identity preserved (real module
#: attributes, imported above via explicit ``as`` re-export idiom -- unlike
#: the three ``_RELOCATED_NAMES`` below, which resolve dynamically via
#: ``__getattr__`` (PEP 562)).
#:
#: ``__all__`` lists only the two names that internal ``src/`` callers still
#: import *from this shim path* -- ``ManifestRegistry`` (the delegate class,
#: imported by sync/indexer/reconcile/rebaseline) and ``ManifestSchemaError``
#: (caught by sync/namespace + sync/dossier_pipeline). ``load_manifest`` and
#: ``MalformedManifestError`` are deliberately NOT listed: internal callers
#: reach them at their canonical charter origins (``charter.activation.
#: manifest_loader`` / the ``charter.missions`` facade), so listing them in
#: ``__all__`` here would trip the symbol-level dead-code gate
#: (``tests/architectural/test_no_dead_symbols.py`` -- an ``__all__`` entry
#: with no internal-from-this-module consumer). They stay importable for
#: external/backward-compat callers; do NOT re-add them to ``__all__``.
__all__ = [
    "ManifestRegistry",
    "ManifestSchemaError",
]

#: Names relocated to :mod:`charter.offering.missions.expected_artifact_manifest`
#: (C-001) that this module still lazily re-exports for backward
#: compatibility -- see the module docstring and ``__getattr__`` below.
_RELOCATED_NAMES = frozenset({"ArtifactClassEnum", "ExpectedArtifactManifest", "ExpectedArtifactSpec"})


def __getattr__(name: str) -> Any:
    """PEP 562 lazy re-export for the classes relocated to ``charter.offering.missions``.

    Only fires for attribute access this module doesn't otherwise define
    (regular imports/definitions above always win first) -- so
    ``from specify_cli.dossier.manifest import ExpectedArtifactManifest``
    (and ``ExpectedArtifactSpec`` / ``ArtifactClassEnum``) keeps resolving at
    runtime for every existing importer, without this module carrying an
    import-time dependency on ``doctrine`` (the lazy import below only runs
    when one of the three names is actually requested).
    """
    if name in _RELOCATED_NAMES:
        from charter import missions as _cm  # noqa: PLC0415 — through-charter re-export (runtime→charter→doctrine boundary)

        return getattr(_cm, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


class ManifestRegistry:
    """Registry for loading and querying expected artifact manifests.

    Singleton-like pattern with in-memory caching.
    Provides step-aware querying of artifact requirements.

    Example:
        >>> manifest = ManifestRegistry.load_manifest("software-dev")
        >>> if manifest:
        ...     specs = ManifestRegistry.get_required_artifacts(manifest, "specify")
        ...     print(f"Specify step requires {len(specs)} artifacts")
    """

    #: Cache key is ``(mission_type, org_roots_fingerprint)``, NOT bare
    #: ``mission_type`` (FR-008 / WP05 cache-key fix). ``org_roots_fingerprint``
    #: is a **declaration-ordered** tuple of existing org-root path strings —
    #: NOT sorted. Per NFR-003 / C-4 ("last-EXISTING-match wins"), two
    #: `repo_root`s that declare the SAME set of org roots in a DIFFERENT
    #: order can resolve to different manifests; sorting the key would
    #: collide those two cases onto one cache entry and silently hand the
    #: second `repo_root` the first's (order-wrong) manifest. The tuple is
    #: empty when ``repo_root`` is ``None`` (today's call shape, unchanged)
    #: or when no configured org pack resolves to an existing path for that
    #: ``repo_root``. Without order-preservation, the cache — process-global
    #: and previously keyed on ``mission_type`` alone — would let the FIRST
    #: resolution of a given mission type in a long-lived process (a daemon,
    #: or a test session touching two projects with different org overrides)
    #: permanently shadow every later ``repo_root``'s result for that same
    #: mission type: project B's request would silently get project A's org
    #: override (or lack thereof). See
    #: ``tests/dossier/test_manifest.py::TestManifestRegistryOrgTier::test_cache_key_does_not_shadow_across_different_repo_roots``
    #: and ``::test_cache_key_preserves_declaration_order_for_same_root_set``.
    #:
    #: **Relocation (WP01 / #3770):** this is the SAME dict object as
    #: :data:`charter.activation.manifest_loader._cache` (aliased at class
    #: -body evaluation time below, not copied) -- the actual load+cache
    #: logic now lives entirely in that module; ``ManifestRegistry`` never
    #: writes to this dict directly any more. The alias exists so
    #: introspection against ``ManifestRegistry._cache`` (cache-key shape,
    #: membership, length) keeps working unchanged for every pre-existing
    #: test that reads it.
    _cache = _charter_manifest_cache

    @staticmethod
    def load_manifest(mission_type: str, repo_root: Path | None = None) -> ExpectedArtifactManifest | None:
        """Load manifest for mission type from the canonical doctrine tree.

        **Thin delegate (WP01 / #3770):** all resolution, precedence, and
        caching logic lives in
        :func:`charter.activation.manifest_loader.load_manifest` -- the one
        cached authority reachable from both runtime and charter-tier
        callers. This method exists only so existing callers of
        ``ManifestRegistry.load_manifest(...)`` (the stateful-class call
        shape, alongside the sibling completeness methods below) keep
        working unchanged; see that function's docstring for the full
        org/built-in precedence, cache-key, and error-taxonomy contract.

        Args:
            mission_type: Mission type (e.g., 'software-dev', 'research')
            repo_root: Project root to resolve org-pack overrides for, or
                ``None`` (default) for built-in-tree-only resolution.

        Returns:
            ExpectedArtifactManifest if found and valid, None if genuinely
            absent on every consulted tier.

        Raises:
            ManifestSchemaError: See
                :func:`charter.activation.manifest_loader.load_manifest`.
            MalformedManifestError: See
                :func:`charter.activation.manifest_loader.load_manifest`
                (built-in tier only, as of this WP).
        """
        return load_manifest(mission_type, repo_root=repo_root)

    @staticmethod
    def get_required_artifacts(
        manifest: ExpectedArtifactManifest,
        step_id: str,
    ) -> list[ExpectedArtifactSpec]:
        """Get required artifact specs for a mission step.

        Combines required_always with required_by_step[step_id].
        Returns empty list if step_id not in manifest (graceful degradation).

        Args:
            manifest: ExpectedArtifactManifest to query
            step_id: Mission step ID (e.g., 'specify', 'planning')

        Returns:
            List of ExpectedArtifactSpec required at this step
        """
        base = manifest.required_always
        step_specific = manifest.required_by_step.get(step_id, [])
        return base + step_specific

    @staticmethod
    def get_blocking_artifacts(
        specs: list[ExpectedArtifactSpec],
    ) -> list[ExpectedArtifactSpec]:
        """Filter artifact specs to only blocking ones.

        Args:
            specs: List of ExpectedArtifactSpec

        Returns:
            List of specs where blocking=True
        """
        return [s for s in specs if s.blocking]

    @staticmethod
    def get_optional_artifacts(manifest: ExpectedArtifactManifest) -> list[ExpectedArtifactSpec]:
        """Get optional artifact specs for a mission.

        Args:
            manifest: ExpectedArtifactManifest to query

        Returns:
            List of optional artifact specs
        """
        return manifest.optional_always

    @staticmethod
    def validate_manifest(
        manifest: ExpectedArtifactManifest,
        mission_dir: Path,  # noqa: ARG004
    ) -> tuple[bool, list[str]]:
        """Validate manifest against mission structure.

        Checks:
        - Step IDs in required_by_step exist in mission.yaml states
        - Path patterns are relative (no leading /)
        - Path patterns don't reference parent (..)

        Args:
            manifest: Manifest to validate
            mission_dir: Path to mission directory

        Returns:
            Tuple of (is_valid, list of error messages)
        """
        errors = []

        # Check path patterns
        for specs_list in [
            manifest.required_always,
            manifest.optional_always,
            *manifest.required_by_step.values(),
        ]:
            for spec in specs_list:
                if spec.path_pattern.startswith("/"):
                    errors.append(f"Path pattern must be relative: '{spec.path_pattern}' (artifact_key={spec.artifact_key})")
                if ".." in spec.path_pattern:
                    errors.append(f"Path pattern cannot reference parent directory: '{spec.path_pattern}' (artifact_key={spec.artifact_key})")

        return len(errors) == 0, errors

    @staticmethod
    def clear_cache() -> None:
        """Clear manifest cache (useful for testing).

        Delegates to :func:`charter.activation.manifest_loader.clear_cache`,
        which mutates (``.clear()``) the same dict object aliased at
        :data:`ManifestRegistry._cache` above -- so this empties both names
        at once (WP01 / #3770).
        """
        _clear_charter_manifest_cache()
