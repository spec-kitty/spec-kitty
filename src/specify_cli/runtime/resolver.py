"""6-tier asset resolution: override > legacy > org > global-mission > global > package default.

Resolution tiers (checked in order):
1. OVERRIDE        -- .kittify/overrides/{templates,command-templates}/
2. LEGACY          -- .kittify/{templates,command-templates}/ (deprecated; emits warning)
3. ORG             -- <org_root>/missions/{mission}/{templates,command-templates}/
                      for each root returned by the lazy
                      ``charter.drg.resolve_org_roots(project_dir)`` facade, in
                      declaration order (first match wins). A no-op when no
                      org packs are configured (NFR-005).
4. GLOBAL_MISSION  -- ~/.kittify/missions/{mission}/{templates,command-templates}/
5. GLOBAL          -- ~/.kittify/{templates,command-templates}/
6. PACKAGE         -- charter-resolved doctrine/missions/{mission}/{templates,command-templates}/

After ``spec-kitty migrate`` has been run (i.e. ``~/.kittify/`` is
populated), legacy-tier warnings are suppressed.  Pre-migration projects
receive a single "run ``spec-kitty migrate``" nudge per CLI invocation.
"""

from __future__ import annotations

import logging
import sys
import warnings
from pathlib import Path
from typing import TYPE_CHECKING

# Single source of truth for the resolution enum / result dataclass.
# Re-exported via the charter.resolution facade (which itself re-exports
# from charter.offering.resolver, preserving object identity) so every importer
# shares one class identity — otherwise `ResolutionTier.X == ResolutionTier.X`
# fails across modules and test suites that import from both paths flake on
# `is`/`==`. Historical note: prior to 2026-04-15 this module defined its
# own duplicate ResolutionTier/ResolutionResult, which caused ~30 CI failures
# on the release-readiness job where charter.offering.test_resolver and
# runtime.test_resolver_unit ran in the same session. The charter facade
# route was adopted in mission charter-mediated-doctrine-selection-01KRTZCA
# (WP07) to enforce the runtime → charter → doctrine boundary.
from charter.activation.mission_type_profiles import ResolvedMissionType
from charter.resolution import ResolutionResult, ResolutionTier
from specify_cli.core.paths import assert_safe_path_segment

if TYPE_CHECKING:
    from charter.missions import ExpectedArtifactManifest

__all__ = [
    "ResolutionResult",
    "ResolutionTier",
    "TemplateConfigurationError",
    "TemplateURNError",
    "required_artifacts_for",
    "resolve_command",
    "resolve_configured_artifact_name",
    "resolve_configured_template",
    "resolve_mission",
    "resolve_template",
    "resolve_template_by_urn",
]

from specify_cli.runtime.home import get_kittify_home, get_package_asset_root

logger = logging.getLogger(__name__)

_WINDOWS_RESERVED_TEMPLATE_BASENAMES = frozenset(
    {"CON", "PRN", "AUX", "NUL", "CLOCK$"}
    | {f"COM{index}" for index in range(1, 10)}
    | {f"LPT{index}" for index in range(1, 10)}
)


class TemplateConfigurationError(ValueError):
    """Raised when activated mission configuration cannot select a template.

    Attributes:
        mission_type: Activated mission-type ID, exact invalid candidate, or
            ``"<typeless>"`` for a neutral context.
        artifact_kind: Semantic template key requested by the caller.
        mapped_filename: Configured filename, when selection reached that far.
    """

    def __init__(
        self,
        *,
        mission_type: str | None,
        artifact_kind: str,
        reason: str,
        mapped_filename: str | None = None,
    ) -> None:
        self.mission_type = "<typeless>" if mission_type is None else mission_type
        self.artifact_kind = artifact_kind
        self.mapped_filename = mapped_filename
        super().__init__(
            f"Template configuration for mission type {self.mission_type!r} "
            f"and artifact kind {artifact_kind!r} {reason}."
        )


class ArtifactNameConfigurationError(ValueError):
    """Raised when a mission manifest cannot resolve an artifact filename."""

    def __init__(
        self,
        *,
        mission_type: str,
        artifact_key: str,
        reason: str,
        mapped_filename: str | None = None,
    ) -> None:
        self.mission_type = mission_type
        self.artifact_key = artifact_key
        self.mapped_filename = mapped_filename
        super().__init__(
            f"Artifact filename configuration for mission type {mission_type!r} "
            f"and artifact key {artifact_key!r} {reason}."
        )


class TemplateURNError(ValueError):
    """Raised when a mission-qualified template URN cannot be resolved.

    Covers both malformed URNs (absent, blank, missing the ``template:``
    prefix, or not of the ``<mission>/<name>`` shape after the prefix) and
    well-formed URNs that no tier resolves. Fail-closed per C-001: the
    mission segment is never inferred or defaulted when absent.

    Attributes:
        urn: The exact URN string that failed to resolve.
    """

    def __init__(self, *, urn: str, reason: str) -> None:
        self.urn = urn
        super().__init__(f"Template URN {urn!r} {reason}.")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _assert_portable_template_filename(filename: str) -> None:
    """Reject single-segment filenames that alias Windows device paths."""
    if filename.endswith((".", " ")):
        raise ValueError(
            f"Template filename {filename!r} is not portable to Windows: "
            "filenames must not end with a dot or space"
        )

    basename = filename.split(".", maxsplit=1)[0].upper()
    if basename in _WINDOWS_RESERVED_TEMPLATE_BASENAMES:
        raise ValueError(
            f"Template filename {filename!r} is not portable to Windows: "
            f"{basename!r} is a reserved device basename"
        )


def _is_global_runtime_configured() -> bool:
    """Return True if ``~/.kittify/`` has been populated by ``ensure_runtime``.

    The presence of ``cache/version.lock`` is the authoritative indicator
    that the global runtime has been bootstrapped at least once.  This
    avoids false positives from an empty ``~/.kittify/`` directory.
    """
    try:
        home = get_kittify_home()
        return (home / "cache" / "version.lock").is_file()
    except RuntimeError:
        return False


# Module-level flag: ensures the migrate nudge is emitted at most once per
# CLI invocation (not per resolution call).
_migrate_nudge_shown = False


def _is_json_mode_invocation() -> bool:
    """Return True when the active CLI invocation requested machine JSON."""
    return "--json" in sys.argv[1:]


def _warn_legacy_asset(path: Path) -> None:
    """Emit a deprecation warning for a legacy-tier asset hit.

    When the global runtime is already configured (``~/.kittify/`` has
    ``cache/version.lock``), the warning is suppressed because the user
    simply hasn't run ``spec-kitty migrate`` for this *project* yet.
    Instead, a one-time stderr nudge is printed.
    """
    if _is_global_runtime_configured():
        # Global runtime exists — suppress noisy DeprecationWarning, emit
        # a single one-time nudge to stderr instead.
        _emit_migrate_nudge()
        return

    msg = (
        f"Legacy asset resolved: {path} — run 'spec-kitty migrate' to clean up. "
        f"Legacy resolution will be removed in the next major version."
    )
    logger.warning(msg)
    warnings.warn(msg, DeprecationWarning, stacklevel=3)


def _emit_migrate_nudge() -> None:
    """Print a one-time "run ``spec-kitty migrate``" message to stderr.

    Uses a module-level flag so the nudge appears at most once per CLI
    invocation regardless of how many assets are resolved.  Output goes
    to stderr so it never interferes with ``--json`` output on stdout.

    The runtime path shown in the message is rendered via
    :func:`specify_cli.paths.render_runtime_path` so Windows users see the
    real ``%LOCALAPPDATA%\\spec-kitty\\`` path and not a POSIX tilde literal
    (SC-002 of the Windows Compatibility Hardening mission).
    """
    global _migrate_nudge_shown  # noqa: PLW0603
    if _migrate_nudge_shown:
        return
    if _is_json_mode_invocation():
        return
    _migrate_nudge_shown = True
    from specify_cli.paths import render_runtime_path  # noqa: PLC0415
    from specify_cli.runtime.home import get_kittify_home  # noqa: PLC0415
    runtime_display = render_runtime_path(get_kittify_home())
    print(
        "Note: Run `spec-kitty migrate` to clean up legacy project files and use the "
        f"global runtime ({runtime_display}).",
        file=sys.stderr,
    )


def _reset_migrate_nudge() -> None:
    """Reset the one-time nudge flag (for testing only)."""
    global _migrate_nudge_shown  # noqa: PLW0603
    _migrate_nudge_shown = False


def _package_default_path(
    *,
    pkg_missions: Path,
    mission: str,
    subdir: str,
    name: str,
) -> Path | None:
    """Resolve package defaults (tier 6) through charter's sole doctrine door.

    FR-003 / T019 — **construction-contract mapping, recorded here as the
    call site the WP asked to document.**

    Before this change this helper went through a since-deleted charter-layer
    template-resolver delegate, obtained from an
    ``lru_cache``d ``_charter_template_resolver_for(missions_root)`` factory
    keyed on a ``missions_root`` *string*, while the canonical charter factory
    (``charter.activation.resolver.ActiveCharterService``) is built from a ``repo_root`` by the
    unified builder. Those two construction contracts do not compose, and the
    mapping is resolved as follows:

    **There is no missions_root → repo_root mapping, by design.** The factory's
    tier-axis methods are ``@staticmethod``s that take ``missions_root`` (and,
    for the full chain, ``project_dir``) as arguments, because the 6-tier axis
    is ungated by design and reads no instance state — so no instance, and
    therefore no ``repo_root``, is needed here at all.

    The rejected alternative was T019 option (a): resolve ``repo_root`` from
    the ``project_dir`` already threaded through :func:`_resolve_asset` and
    build the activation-aware factory with it. It is available — but it would
    couple this pure-filesystem tier-6 lookup to charter governance-config
    loading (``PackContext.from_config`` + ``resolve_org_roots`` +
    ``infer_repo_languages``) whose result the called methods provably never
    read, and would newly make template resolution fail-closed on a malformed
    ``.kittify/config.yaml`` — a project could then no longer resolve the
    templates its repair commands need. The ``lru_cache`` that used to live
    here has moved into ``charter.activation.resolver._mission_template_repository``,
    alongside the resolution entry point, so repeated tier-6 lookups still
    reuse one repository.

    Note this module keeps its own tiers 1-5 (a second, parallel filesystem
    implementation with known semantic drift from ``doctrine/resolver.py``);
    that is named, pre-existing deferred debt and explicitly out of FR-003's
    scope. Only the tier-6 hop is charter-mediated, which is why the factory
    exposes a tier-6-only entry point at all.
    """
    from charter.activation.resolver import ActiveCharterService  # noqa: PLC0415 — lazy: keeps the charter import off module load

    return ActiveCharterService.resolve_package_default_asset_path(
        missions_root=pkg_missions,
        mission=mission,
        subdir=subdir,
        name=name,
    )


def _resolve_asset(
    name: str,
    subdir: str,
    project_dir: Path,
    mission: str = "software-dev",
) -> ResolutionResult:
    """Core 6-tier resolution logic shared by public helpers.

    Tier 1 (override) checks two shapes, mission-scoped first:
    1a. ``.kittify/overrides/missions/{mission}/{subdir}/{name}`` (mission-scoped)
    1b. ``.kittify/overrides/{subdir}/{name}`` (global, backward-compatible fallback)

    Tier 3 (org) probes each configured org charter pack root, in
    declaration order, before falling through to the global-mission tier.
    Sourced via the lazy ``charter.drg.resolve_org_roots`` facade (DEC-003) --
    never a direct ``doctrine.*`` import from this module.

    Args:
        name: Filename to resolve (e.g. ``"plan.md"``).
        subdir: Subdirectory within each tier (``"templates"`` or
                ``"command-templates"``).
        project_dir: Root of the user project that contains ``.kittify/``.
        mission: Mission key used for tier 1 (both shapes) and tiers 3-5.

    Returns:
        ResolutionResult with the winning path, tier and mission.

    Raises:
        FileNotFoundError: If no tier provides the requested asset.
    """
    kittify = project_dir / ".kittify"

    # Tier 1 -- override. Mission-scoped overrides
    # (.kittify/overrides/missions/{mission}/{subdir}/{name}) are more
    # specific and win over the global, non-mission-scoped override
    # (.kittify/overrides/{subdir}/{name}), which is kept as a
    # backward-compatible fallback.
    mission_scoped_override = kittify / "overrides" / "missions" / mission / subdir / name
    if mission_scoped_override.is_file():
        return ResolutionResult(path=mission_scoped_override, tier=ResolutionTier.OVERRIDE, mission=mission)

    override = kittify / "overrides" / subdir / name
    if override.is_file():
        return ResolutionResult(path=override, tier=ResolutionTier.OVERRIDE, mission=mission)

    # Tier 2 -- legacy
    legacy = kittify / subdir / name
    if legacy.is_file():
        _warn_legacy_asset(legacy)
        return ResolutionResult(path=legacy, tier=ResolutionTier.LEGACY, mission=mission)

    # Tier 3 -- org (sourced from configured org charter packs). Lazy import
    # mirrors the five existing specify_cli/** call sites that route org-root
    # resolution through this facade (DEC-003) -- never a direct
    # ``doctrine.*`` import from runtime. No try/except around
    # resolve_org_roots(): OrgPackSubdirEscapeError/OrgPackEnvVarUnsetError
    # are deliberately raised and must propagate (DEC-005, NFR-001). With no
    # org packs configured, resolve_org_roots() returns [] and this loop is a
    # no-op (NFR-005). ``quiet=True``: this is a resolution hot path that may
    # run many times per invocation -- an unparseable config.yaml with no
    # readable org intent must not spam a UserWarning per call (see
    # load_pack_registry's docstring). A genuinely declared-but-broken org
    # pack still raises a loud UserWarning regardless.
    from charter.drg import resolve_org_roots  # noqa: PLC0415 — lazy, mirrors existing pattern

    for org_root in resolve_org_roots(project_dir, quiet=True):
        org_path = org_root / "missions" / mission / subdir / name
        if org_path.is_file():
            return ResolutionResult(path=org_path, tier=ResolutionTier.ORG, mission=mission)

    # Tier 4 -- global mission-specific (~/.kittify/missions/{mission}/...)
    try:
        global_home = get_kittify_home()

        global_mission_path = global_home / "missions" / mission / subdir / name
        if global_mission_path.is_file():
            return ResolutionResult(
                path=global_mission_path,
                tier=ResolutionTier.GLOBAL_MISSION,
                mission=mission,
            )

        # Tier 5 -- global non-mission (~/.kittify/{subdir}/{name})
        global_path = global_home / subdir / name
        if global_path.is_file():
            return ResolutionResult(path=global_path, tier=ResolutionTier.GLOBAL, mission=mission)
    except RuntimeError:
        # Cannot determine home directory -- skip tiers 4 and 5
        pass

    # Tier 6 -- package default via charter. Keep this call routed through
    # charter so runtime never binds directly to doctrine's repository shape.
    try:
        pkg_missions = get_package_asset_root()
        pkg_path = _package_default_path(
            pkg_missions=pkg_missions,
            mission=mission,
            subdir=subdir,
            name=name,
        )
        if pkg_path is not None and pkg_path.is_file():
            return ResolutionResult(
                path=pkg_path,
                tier=ResolutionTier.PACKAGE_DEFAULT,
                mission=mission,
            )
    except FileNotFoundError:
        pass

    raise FileNotFoundError(
        f"Asset '{name}' not found in any resolution tier "
        f"(subdir={subdir!r}, mission={mission!r}, project={project_dir})"
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def resolve_template(
    name: str,
    project_dir: Path,
    mission: str = "software-dev",
) -> ResolutionResult:
    """Resolve a template file through the 6-tier precedence chain.

    Checks (in order):
    1. .kittify/overrides/templates/{name}
    2. .kittify/templates/{name}  (legacy -- emits warning/nudge)
    3. <org_root>/missions/{mission}/templates/{name}  (per configured org pack)
    4. ~/.kittify/missions/{mission}/templates/{name}
    5. ~/.kittify/templates/{name}
    6. <package>/missions/{mission}/templates/{name}

    Args:
        name: Template filename (e.g. ``"spec-template.md"``).
        project_dir: Project root containing ``.kittify/``.
        mission: Mission key (default ``"software-dev"``).

    Returns:
        ResolutionResult with the resolved path, tier, and mission.

    Raises:
        FileNotFoundError: If the template is not found at any tier.
    """
    return _resolve_asset(name, "templates", project_dir, mission)


def resolve_configured_template(
    artifact_kind: str,
    project_dir: Path,
    resolved_mission_type: ResolvedMissionType,
) -> ResolutionResult:
    """Resolve a content template selected by activated mission configuration.

    This first-stage mapping seam reads ``artifact_kind`` from an explicit
    activated mission context, then delegates the configured filename to
    :func:`resolve_template`. The existing six-tier filesystem precedence
    remains wholly owned by that second-stage resolver.

    This seam has no repository or activation-registry input, so it cannot
    revalidate whether a syntactically safe mission type was activated. That
    authenticity remains the producing charter resolver's responsibility. It
    does validate the ID as a safe path segment before reading the lazy mapping,
    preventing a forged context from escaping mission-scoped resolution roots.

    Args:
        artifact_kind: Semantic mapping key, such as ``"spec"`` or ``"plan"``.
        project_dir: Project root containing ``.kittify/``.
        resolved_mission_type: Explicit activated mission context. A neutral
            context is rejected rather than inferred as software development.

    Returns:
        ResolutionResult from the unchanged six-tier resolver.

    Raises:
        TemplateConfigurationError: If the context is typeless, its mapping is
            null, the key is absent or blank, or the configured file cannot be
            resolved at any permitted tier.
    """
    mission_type = resolved_mission_type.mission_type
    if mission_type is None:
        raise TemplateConfigurationError(
            mission_type=None,
            artifact_kind=artifact_kind,
            reason="requires an activated, non-typeless mission context",
        )

    try:
        assert_safe_path_segment(mission_type)
    except ValueError as exc:
        raise TemplateConfigurationError(
            mission_type=mission_type,
            artifact_kind=artifact_kind,
            reason=f"has unsafe mission type {mission_type!r} ({exc})",
        ) from exc

    template_set = resolved_mission_type.template_set
    if template_set is None:
        raise TemplateConfigurationError(
            mission_type=mission_type,
            artifact_kind=artifact_kind,
            reason="has no configured template mapping",
        )

    mapped_filename = template_set.get(artifact_kind)
    if mapped_filename is None:
        raise TemplateConfigurationError(
            mission_type=mission_type,
            artifact_kind=artifact_kind,
            reason="is missing the requested mapping key",
        )
    if not mapped_filename.strip():
        raise TemplateConfigurationError(
            mission_type=mission_type,
            artifact_kind=artifact_kind,
            mapped_filename=mapped_filename,
            reason="maps to a blank filename",
        )

    try:
        assert_safe_path_segment(mapped_filename)
        _assert_portable_template_filename(mapped_filename)
    except ValueError as exc:
        raise TemplateConfigurationError(
            mission_type=mission_type,
            artifact_kind=artifact_kind,
            mapped_filename=mapped_filename,
            reason=f"maps to unsafe filename {mapped_filename!r} ({exc})",
        ) from exc

    try:
        return resolve_template(mapped_filename, project_dir, mission=mission_type)
    except FileNotFoundError as exc:
        raise TemplateConfigurationError(
            mission_type=mission_type,
            artifact_kind=artifact_kind,
            mapped_filename=mapped_filename,
            reason=f"maps to unresolved filename {mapped_filename!r}",
        ) from exc


def _load_expected_artifact_manifest(
    mission_type: str, repo_root: Path | None = None
) -> ExpectedArtifactManifest | None:
    """Load and validate *mission_type*'s expected-artifacts manifest (read-only).

    **Retired mirror (WP02, #3770, FR-004):** this function used to duplicate
    the org->built-in precedence + ``model_validate`` logic locally. It now
    delegates to :func:`charter.activation.manifest_loader.load_manifest` --
    the single relocated, cached authority (WP01) -- instead of maintaining a
    second copy. Returns ``None`` when neither tier has a manifest for
    *mission_type* (unregistered/custom type -- degrades gracefully).

    FR-008: when *repo_root* is given and resolves to 1+ existing configured
    org roots, an org-pack ``<org_root>/missions/<mission_type>/expected-artifacts.yaml``
    takes precedence over the built-in file, whole-file -- never field-merged
    with it -- exactly as the authority implements (contract C-4). *repo_root*
    is optional and defaults to ``None`` (today's exact behavior: no org
    lookup, built-in tree only), so every existing caller with no root in
    scope is unaffected by this signature.

    Raises:
        ManifestSchemaError: A *found*, syntactically-valid manifest that
            fails schema validation (``extra="forbid"``) -- propagated
            unchanged from the authority, for BOTH tiers. Not caught here
            (WP03/#3412 is a separate, not-yet-landed work package): this
            delegate must not re-swallow it.
        MalformedManifestError: A *found* manifest that fails to parse as
            YAML at all -- propagated unchanged from the authority
            (built-in tier only, today).
    """
    from charter.activation.manifest_loader import load_manifest  # noqa: PLC0415

    return load_manifest(mission_type, repo_root=repo_root)


def resolve_configured_artifact_name(
    artifact_key: str,
    mission_type: str = "software-dev",
) -> str:
    """Resolve the canonical filename for *artifact_key* under *mission_type* (FR-009).

    Twins :func:`resolve_configured_template`'s per-type filename seam
    without adding a second filename authority (squad §S2): the mapping is
    projected from ``expected-artifacts.yaml``'s ``path_pattern`` (via
    :func:`charter.offering.missions.project_artifact_name_set`),
    never from :attr:`~charter.offering.missions.models.MissionStepTemplateRef.template_file`.

    Args:
        artifact_key: Stable manifest key, e.g. ``"input.spec.main"``.
        mission_type: Mission-type id (default ``"software-dev"``).

    Returns:
        The configured ``path_pattern`` filename.

    Raises:
        ArtifactNameConfigurationError: If *mission_type* is an unsafe path
            segment, has no expected-artifacts manifest, or has no mapping
            for *artifact_key*.
        ManifestSchemaError: If *mission_type* has an expected-artifacts
            manifest but it fails schema validation -- see
            :func:`_load_expected_artifact_manifest`.
    """
    try:
        assert_safe_path_segment(mission_type)
    except ValueError as exc:
        raise ArtifactNameConfigurationError(
            mission_type=mission_type,
            artifact_key=artifact_key,
            reason=f"has unsafe mission type {mission_type!r} ({exc})",
        ) from exc

    manifest = _load_expected_artifact_manifest(mission_type)
    if manifest is None:
        raise ArtifactNameConfigurationError(
            mission_type=mission_type,
            artifact_key=artifact_key,
            reason="has no expected-artifacts manifest",
        )

    from charter.missions import project_artifact_name_set  # noqa: PLC0415

    name_set = project_artifact_name_set(manifest) or {}
    mapped_filename = name_set.get(artifact_key)
    if mapped_filename is None:
        raise ArtifactNameConfigurationError(
            mission_type=mission_type,
            artifact_key=artifact_key,
            reason="is missing the requested mapping key",
        )
    return mapped_filename


def required_artifacts_for(
    step: str, mission_type: str = "software-dev", repo_root: Path | None = None
) -> list[str]:
    """Return the blocking artifact filenames required at *step* (FR-009).

    Combines ``required_always`` with ``required_by_step[step]`` (mirroring
    :meth:`~specify_cli.dossier.manifest.ManifestRegistry.get_required_artifacts`
    /  ``get_blocking_artifacts``) and returns only the ``blocking`` specs'
    filenames -- the live per-type presence-gate consumer shape (WP04b).

    Args:
        step: Mission step id (e.g. ``"specify"``, ``"plan"``).
        mission_type: Mission-type id (default ``"software-dev"``).
        repo_root: Project root to resolve org-pack overrides for (FR-008),
            or ``None`` (default) for built-in-tree-only resolution --
            forwarded to :func:`_load_expected_artifact_manifest` unchanged.

    Returns:
        Blocking filenames for *step*, or an empty list when *mission_type*
        has no expected-artifacts manifest (unregistered/custom type).

    Raises:
        ManifestSchemaError: If *mission_type* has an expected-artifacts
            manifest but it fails schema validation -- see
            :func:`_load_expected_artifact_manifest`.
    """
    manifest = _load_expected_artifact_manifest(mission_type, repo_root=repo_root)
    if manifest is None:
        return []
    specs = [*manifest.required_always, *manifest.required_by_step.get(step, [])]
    return [spec.path_pattern for spec in specs if spec.blocking]


#: URN prefix identifying a template node's DRG identity, mirroring
#: ``charter.offering.drg.models.NodeKind.TEMPLATE.value`` (``"template"``).
_TEMPLATE_URN_PREFIX = "template:"

#: ``resolve_template_by_id`` only consults ``TierRoot.project_dir`` for the
#: override/legacy tiers (verified against ``charter.offering.template_catalog``);
#: ``missions_root`` matters solely to the discovery surface
#: (``discover_templates``), which this URN lane never calls. A fixed,
#: non-existent sentinel keeps that fact explicit instead of silently
#: reusing an unrelated path.
_URN_LANE_MISSIONS_ROOT_SENTINEL = Path("/nonexistent-template-urn-missions-root")


def resolve_template_by_urn(
    urn: str,
    project_dir: Path,
) -> ResolutionResult:
    """Resolve a mission-qualified ``template:<mission>/<name>`` URN.

    This is Lane 2 of the name↔URN resolution contract (C-004,
    ``contracts/name-urn-resolution.md``): a graph-addressed resolution path
    added *alongside* :func:`resolve_configured_template` (Lane 1, the
    name-based creation path). Neither lane re-wires the other --
    :func:`resolve_configured_template`'s signature is unchanged.

    The URN is split into its mission-qualified ``<mission>/<name>`` template
    ID and handed to
    :func:`charter.template_catalog.resolve_template_by_id`, which performs
    that split itself and delegates to the same Stage-2 six-tier precedence
    (override > legacy > org > global-mission > global > package) that
    :func:`resolve_template` implements -- so an override at
    ``.kittify/overrides/templates/<file>`` wins on this lane exactly as it
    does on the name-based lane (US3.3).

    Args:
        urn: Mission-qualified template URN, e.g.
            ``"template:software-dev/spec-template.md"``.
        project_dir: Project root containing ``.kittify/`` (participates in
            the override/legacy tiers).

    Returns:
        ResolutionResult from the unchanged six-tier resolver.

    Raises:
        TemplateURNError: If the URN is absent/blank, missing the
            ``"template:"`` prefix, malformed (not ``"<mission>/<name>"``
            after the prefix), or unresolvable at any tier. The mission
            segment is never inferred or defaulted (C-001, no #2660
            inference reintroduction) -- an unqualified URN fails closed
            rather than defaulting to ``"software-dev"``.
    """
    if not urn or not urn.strip():
        raise TemplateURNError(urn=urn, reason="is absent or blank")

    if not urn.startswith(_TEMPLATE_URN_PREFIX):
        raise TemplateURNError(
            urn=urn,
            reason=f"does not start with the required {_TEMPLATE_URN_PREFIX!r} prefix",
        )

    template_id = urn[len(_TEMPLATE_URN_PREFIX) :]

    from charter.template_catalog import TierRoot, resolve_template_by_id  # noqa: PLC0415

    tier_roots = [
        TierRoot(
            tier=ResolutionTier.PACKAGE_DEFAULT,
            missions_root=_URN_LANE_MISSIONS_ROOT_SENTINEL,
            project_dir=project_dir,
        )
    ]

    try:
        return resolve_template_by_id(template_id, tier_roots=tier_roots)
    except ValueError as exc:
        raise TemplateURNError(urn=urn, reason=f"is malformed ({exc})") from exc
    except FileNotFoundError as exc:
        raise TemplateURNError(
            urn=urn,
            reason=f"could not be resolved at any tier ({exc})",
        ) from exc


def resolve_command(
    name: str,
    project_dir: Path,
    mission: str = "software-dev",
) -> ResolutionResult:
    """Resolve a command template through the 6-tier precedence chain.

    Checks (in order):
    1. .kittify/overrides/command-templates/{name}
    2. .kittify/command-templates/{name}  (legacy -- emits warning/nudge)
    3. <org_root>/missions/{mission}/command-templates/{name}  (per configured org pack)
    4. ~/.kittify/missions/{mission}/command-templates/{name}
    5. ~/.kittify/command-templates/{name}
    6. <package>/missions/{mission}/command-templates/{name}

    Args:
        name: Command template filename (e.g. ``"plan.md"``).
        project_dir: Project root containing ``.kittify/``.
        mission: Mission key (default ``"software-dev"``).

    Returns:
        ResolutionResult with the resolved path, tier, and mission.

    Raises:
        FileNotFoundError: If the command template is not found at any tier.
    """
    return _resolve_asset(name, "command-templates", project_dir, mission)


def resolve_mission(
    name: str,
    project_dir: Path,
) -> ResolutionResult:
    """Resolve a mission.yaml through the precedence chain.

    Checks (in order):
    1. .kittify/overrides/missions/{name}/mission.yaml
    2. .kittify/missions/{name}/mission.yaml  (legacy -- emits warning/nudge)
    3. <org_root>/missions/{name}/mission.yaml  (per configured org pack)
    4. ~/.kittify/missions/{name}/mission.yaml
    5. <package>/missions/{name}/mission.yaml

    Note: missions are inherently mission-scoped, so there is no separate
    "global non-mission" tier for mission configs.

    Args:
        name: Mission key (e.g. ``"software-dev"``).
        project_dir: Project root containing ``.kittify/``.

    Returns:
        ResolutionResult with the resolved path, tier, and mission.

    Raises:
        FileNotFoundError: If the mission config is not found at any tier.
    """
    kittify = project_dir / ".kittify"
    filename = "mission.yaml"

    # Tier 1 -- override
    override = kittify / "overrides" / "missions" / name / filename
    if override.is_file():
        return ResolutionResult(path=override, tier=ResolutionTier.OVERRIDE, mission=name)

    # Tier 2 -- legacy
    legacy = kittify / "missions" / name / filename
    if legacy.is_file():
        _warn_legacy_asset(legacy)
        return ResolutionResult(path=legacy, tier=ResolutionTier.LEGACY, mission=name)

    # Tier 3 -- org (sourced from configured org charter packs). Lazy import
    # mirrors _resolve_asset's org-tier import above (DEC-003); no
    # try/except around resolve_org_roots() -- see the identical rationale
    # in _resolve_asset above (DEC-005, NFR-001). ``quiet=True`` -- see the
    # identical rationale in _resolve_asset above.
    from charter.drg import resolve_org_roots  # noqa: PLC0415 — lazy, mirrors existing pattern

    for org_root in resolve_org_roots(project_dir, quiet=True):
        org_path = org_root / "missions" / name / filename
        if org_path.is_file():
            return ResolutionResult(path=org_path, tier=ResolutionTier.ORG, mission=name)

    # Tier 4 -- global (missions are inherently mission-scoped)
    try:
        global_home = get_kittify_home()
        global_path = global_home / "missions" / name / filename
        if global_path.is_file():
            return ResolutionResult(path=global_path, tier=ResolutionTier.GLOBAL_MISSION, mission=name)
    except RuntimeError:
        pass

    # Tier 5 -- package default via charter. FR-003: routed through the
    # canonical charter factory; see _package_default_path's docstring for the
    # construction-contract mapping this call site shares.
    try:
        from charter.activation.resolver import ActiveCharterService  # noqa: PLC0415 — lazy, mirrors _package_default_path

        pkg_missions = get_package_asset_root()
        pkg_path = ActiveCharterService.resolve_package_default_mission_config_path(
            missions_root=pkg_missions,
            mission=name,
        )
        if pkg_path is not None and pkg_path.is_file():
            return ResolutionResult(path=pkg_path, tier=ResolutionTier.PACKAGE_DEFAULT, mission=name)
    except FileNotFoundError:
        pass

    raise FileNotFoundError(f"Mission '{name}' config not found in any resolution tier (project={project_dir})")
