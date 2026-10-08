"""6-tier asset resolution: override > legacy > org > global-mission > global > package default.

Resolution tiers (checked in order):
1. OVERRIDE        -- .kittify/overrides/missions/{mission}/{templates,command-templates}/
                      (mission-scoped, checked first) falling back to the
                      global .kittify/overrides/{templates,command-templates}/
                      (no mission segment, kept for backward compatibility)
2. LEGACY          -- .kittify/{templates,command-templates}/ (deprecated; emits warning)
3. ORG             -- <org_root>/missions/{mission}/{templates,command-templates}/
                      for each root returned by
                      ``charter.offering.drg.org_pack_config.resolve_org_roots(project_dir)``,
                      in declaration order (first match wins). A no-op when
                      no org packs are configured (NFR-005).
4. GLOBAL_MISSION  -- ~/.kittify/missions/{mission}/{templates,command-templates}/
5. GLOBAL          -- ~/.kittify/{templates,command-templates}/
6. PACKAGE         -- packs/built-in/missions/{mission}/{templates,command-templates}/
                      (relocated there from the offering package by #3091/#3204;
                      resolved via ``MissionTemplateRepository.default()``)

After ``spec-kitty migrate`` has been run (i.e. ``~/.kittify/`` is
populated), legacy-tier warnings are suppressed.  Pre-migration projects
receive a single "run ``spec-kitty migrate``" nudge per CLI invocation.

This module lives in **charter.offering** so that the ``charter`` layer can
import the resolver without violating the 2.x dependency direction:

    kernel (root) <- charter.offering <- charter <- specify_cli

``specify_cli.runtime.resolver`` re-exports every public symbol for
backward compatibility.
"""

from __future__ import annotations

import logging
import sys
import warnings
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from kernel.paths import get_kittify_home, render_runtime_path

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public data types
# ---------------------------------------------------------------------------


class ResolutionTier(Enum):
    OVERRIDE = "override"
    LEGACY = "legacy"
    ORG = "org"
    GLOBAL_MISSION = "global_mission"
    GLOBAL = "global"
    PACKAGE_DEFAULT = "package_default"


@dataclass(frozen=True)
class ResolutionResult:
    path: Path
    tier: ResolutionTier
    mission: str | None = None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


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

    The runtime path is rendered via :func:`kernel.paths.render_runtime_path`
    so Windows users see the real ``%LOCALAPPDATA%\\spec-kitty\\`` path instead
    of a POSIX tilde literal (SC-002 of the Windows Compatibility Hardening
    mission).
    """
    global _migrate_nudge_shown  # noqa: PLW0603
    if _migrate_nudge_shown:
        return
    if _is_json_mode_invocation():
        return
    _migrate_nudge_shown = True
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

    Tier 3 (org) probes each configured org Charter Pack root, in
    declaration order, before falling through to the global-mission tier.

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

    # Tier 3 -- org (sourced from configured org Charter Packs). Same-layer
    # direct import (DEC-003: charter/offering/resolver.py needs no facade -- it is
    # already inside charter.offering). No try/except around
    # resolve_org_roots(): OrgPackSubdirEscapeError/OrgPackEnvVarUnsetError
    # are deliberately raised and must propagate (DEC-005, NFR-001). With no
    # org packs configured, resolve_org_roots() returns [] and this loop is a
    # no-op (NFR-005). ``quiet=True``: this is a resolution hot path that may
    # run many times per invocation -- an unparseable config.yaml with no
    # readable org intent must not spam a UserWarning per call (see
    # load_pack_registry's docstring). A genuinely declared-but-broken org
    # pack still raises a loud UserWarning regardless.
    from charter.offering.drg.org_pack_config import resolve_org_roots

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

    # Tier 6 -- package default (via MissionTemplateRepository)
    try:
        from charter.offering.missions import MissionTemplateRepository

        _repo = MissionTemplateRepository.default()
        if subdir == "command-templates":
            pkg_path = _repo._command_template_path(mission, name.removesuffix(".md"))
        elif subdir == "templates":
            pkg_path = _repo._content_template_path(mission, name)
        else:
            # Fallback for unknown subdirs
            pkg_path = _repo._missions_root / mission / subdir / name
            if not pkg_path.is_file():
                pkg_path = None
        if pkg_path:
            return ResolutionResult(
                path=pkg_path,
                tier=ResolutionTier.PACKAGE_DEFAULT,
                mission=mission,
            )
    except (FileNotFoundError, ImportError):
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
    1. .kittify/overrides/missions/{mission}/templates/{name}  (mission-scoped)
       .kittify/overrides/templates/{name}  (global fallback, backward-compat)
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


def resolve_command(
    name: str,
    project_dir: Path,
    mission: str = "software-dev",
) -> ResolutionResult:
    """Resolve a command template through the 6-tier precedence chain.

    Checks (in order):
    1. .kittify/overrides/missions/{mission}/command-templates/{name}  (mission-scoped)
       .kittify/overrides/command-templates/{name}  (global fallback, backward-compat)
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

    # Tier 3 -- org (sourced from configured org Charter Packs). Same-layer
    # direct import (DEC-003); no try/except around resolve_org_roots() --
    # see the identical rationale in _resolve_asset above (DEC-005, NFR-001).
    # ``quiet=True`` -- see the identical rationale in _resolve_asset above.
    from charter.offering.drg.org_pack_config import resolve_org_roots

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

    # Tier 5 -- package default (via MissionTemplateRepository)
    try:
        from charter.offering.missions import MissionTemplateRepository

        pkg_path = MissionTemplateRepository.default()._mission_config_path(name)
        if pkg_path:
            return ResolutionResult(path=pkg_path, tier=ResolutionTier.PACKAGE_DEFAULT, mission=name)
    except (FileNotFoundError, ImportError):
        pass

    raise FileNotFoundError(f"Mission '{name}' config not found in any resolution tier (project={project_dir})")
