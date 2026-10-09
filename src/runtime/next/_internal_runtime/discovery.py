"""Mission pack discovery with deterministic precedence."""

# Internalized from spec-kitty-runtime 0.4.3 as part of
# `shared-package-boundary-cutover-01KQ22DS` (mission). See
# `runtime-standalone-package-retirement-01KQ20Z8` for the upstream
# public-API inventory.
from __future__ import annotations

import os
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field

from runtime.next._internal_runtime.schema import (
    DiscoveredMission,
    MissionPackManifest,
    MissionRuntimeError,
    MissionTemplate,
    load_mission_template_file,
)

_CONFIG_FILENAME = "config.yaml"
_KITTIFY_DIRNAME = ".kittify"
_MISSION_FILENAME = "mission.yaml"
_MISSIONS_DIRNAME = "missions"
_OVERRIDES_DIRNAME = "overrides"
_USER_GLOBAL_MISSIONS = "missions"


# ---------------------------------------------------------------------------
# Reserved built-in mission keys (R-002)
# ---------------------------------------------------------------------------

#: Mission keys reserved for the built-in tier. Custom missions discovered
#: from any non-builtin tier whose ``mission.key`` matches one of these are
#: rejected by ``mission_loader.validator.validate_custom_mission`` with
#: ``MISSION_KEY_RESERVED``. The built-in tier itself is exempt — built-ins
#: are allowed (and expected) to declare these keys.
RESERVED_BUILTIN_KEYS: frozenset[str] = frozenset(
    {
        "software-dev",
        "research",
        "documentation",
        "plan",
    }
)


def is_reserved_key(key: str) -> bool:
    """Return ``True`` iff ``key`` is a reserved built-in mission key."""
    return key in RESERVED_BUILTIN_KEYS


# ---------------------------------------------------------------------------
# Shadowing diagnostics models
# ---------------------------------------------------------------------------

class DiscoveryWarning(BaseModel):
    model_config = ConfigDict(frozen=True)

    path: str
    tier: str
    origin: str
    error: str


# ---------------------------------------------------------------------------
# Discovery context
# ---------------------------------------------------------------------------

class DiscoveryContext(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    project_dir: Path | None = None
    explicit_paths: list[Path] = Field(default_factory=list)
    env_var_name: str = "SPEC_KITTY_MISSION_PATHS"
    user_home: Path = Field(default_factory=lambda: Path.home())
    builtin_roots: list[Path] = Field(default_factory=list)
    #: Org-pack doctrine roots (FR-007), one per configured
    #: ``charter_packs.org.packs[]`` entry. Populated by callers via the lazy
    #: ``charter.drg.resolve_org_roots(repo_root)`` facade -- this module
    #: never resolves org roots itself, matching DEC-004's discipline that
    #: ``src/runtime/next/**`` stays a pure consumer of the already-resolved
    #: list. Empty by default, so a project with no org packs configured
    #: sees no behavior change (NFR-005).
    org_roots: list[Path] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _split_env_paths(value: str) -> list[Path]:
    if not value.strip():
        return []
    return [Path(chunk) for chunk in value.split(os.pathsep) if chunk.strip()]


def _collect_from_manifest(pack_root: Path) -> list[Path]:
    """Collect mission paths from a mission-pack.yaml manifest.

    Validates against MissionPackManifest schema. Raises MissionRuntimeError
    on invalid manifests.
    """
    pack_file = pack_root / "mission-pack.yaml"
    if not pack_file.exists():
        return []
    with open(pack_file, encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}

    if not isinstance(raw, dict):
        raise MissionRuntimeError(f"Mission pack manifest must be a mapping: {pack_file}")

    # Validate against MissionPackManifest schema.
    if "pack" not in raw:
        raise MissionRuntimeError(
            f"Mission pack manifest missing required 'pack' section: {pack_file}"
        )

    manifest = MissionPackManifest.model_validate(raw)

    paths: list[Path] = []
    for entry in manifest.missions:
        paths.append(pack_root / entry.path)
    return paths


def _scan_root(root: Path) -> list[Path]:
    candidates: list[Path] = []

    if root.is_file() and root.name == _MISSION_FILENAME:
        return [root]

    if not root.exists() or not root.is_dir():
        return []

    # Explicit manifest entries first.
    candidates.extend(_collect_from_manifest(root))

    # Legacy/common mission-root layout: <root>/<mission_key>/mission.yaml
    for mission_file in sorted(root.glob(f"*/{_MISSION_FILENAME}")):
        candidates.append(mission_file)

    # Canonical pack layout.
    missions_dir = root / _MISSIONS_DIRNAME
    if missions_dir.is_dir():
        for mission_file in sorted(missions_dir.glob(f"*/{_MISSION_FILENAME}")):
            candidates.append(mission_file)

    # Direct mission root fallback.
    direct_mission = root / _MISSION_FILENAME
    if direct_mission.exists():
        candidates.append(direct_mission)

    # De-duplicate while preserving order.
    seen: set[Path] = set()
    unique: list[Path] = []
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        unique.append(candidate)
    return unique


def _project_config_pack_paths(project_dir: Path) -> list[Path]:
    config_file = project_dir / _KITTIFY_DIRNAME / _CONFIG_FILENAME
    if not config_file.exists():
        return []
    with open(config_file, encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}
    mission_packs = raw.get("mission_packs", [])
    if not isinstance(mission_packs, list):
        return []
    return [project_dir / pack for pack in mission_packs if isinstance(pack, str)]


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------

class DiscoveryResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    missions: list[DiscoveredMission] = Field(default_factory=list)
    warnings: list[DiscoveryWarning] = Field(default_factory=list)


def _build_tiers(context: DiscoveryContext) -> list[tuple[str, str, list[Path]]]:
    """Build the ordered list of discovery tiers from context."""
    tiers: list[tuple[str, str, list[Path]]] = []

    tiers.append(("explicit", "explicit_paths", context.explicit_paths))

    env_value = os.environ.get(context.env_var_name, "")
    tiers.append(("env", context.env_var_name, _split_env_paths(env_value)))

    project_dir = context.project_dir
    if project_dir:
        tiers.append(
            (
                "project_override",
                str(project_dir / _KITTIFY_DIRNAME / _OVERRIDES_DIRNAME / _MISSIONS_DIRNAME),
                [project_dir / _KITTIFY_DIRNAME / _OVERRIDES_DIRNAME / _MISSIONS_DIRNAME],
            )
        )
        tiers.append(
            (
                "project_legacy",
                str(project_dir / _KITTIFY_DIRNAME / _MISSIONS_DIRNAME),
                [project_dir / _KITTIFY_DIRNAME / _MISSIONS_DIRNAME],
            )
        )

    # Tier: org (FR-007). Sits immediately after project_legacy and before
    # user_global -- the same relative position WP03 gave the org tier in
    # both template resolvers (position parity, NFR-004/SC-008). Always
    # present (even with no project_dir) so the tier shape is uniform;
    # ``context.org_roots`` is empty by construction unless a caller
    # populated it, making this a no-op for the common case (NFR-005).
    tiers.append(("org", "org_roots", context.org_roots))

    tiers.append(
        (
            "user_global",
            str(context.user_home / _KITTIFY_DIRNAME / _USER_GLOBAL_MISSIONS),
            [context.user_home / _KITTIFY_DIRNAME / _USER_GLOBAL_MISSIONS],
        )
    )

    if project_dir:
        tiers.append(
            (
                "project_config",
                str(project_dir / _KITTIFY_DIRNAME / _CONFIG_FILENAME),
                _project_config_pack_paths(project_dir),
            )
        )

    tiers.append(("builtin", "builtin_roots", context.builtin_roots))
    return tiers


def discover_missions_with_warnings(context: DiscoveryContext) -> DiscoveryResult:
    """Discover missions by precedence, collecting warnings for load failures.

    Returns DiscoveryResult with both missions and warnings.
    """
    tiers = _build_tiers(context)

    discovered: list[DiscoveredMission] = []
    warnings: list[DiscoveryWarning] = []
    selected_by_key: set[str] = set()

    for tier, origin, roots in tiers:
        for root in roots:
            for mission_yaml in _scan_root(root):
                try:
                    template = load_mission_template_file(mission_yaml)
                except Exception as exc:
                    warnings.append(
                        DiscoveryWarning(
                            path=str(mission_yaml),
                            tier=tier,
                            origin=origin,
                            error=str(exc),
                        )
                    )
                    continue
                key = template.mission.key
                selected = key not in selected_by_key
                if selected:
                    selected_by_key.add(key)
                discovered.append(
                    DiscoveredMission(
                        key=key,
                        path=str(mission_yaml.resolve()),
                        origin=origin,
                        precedence_tier=tier,
                        selected=selected,
                    )
                )

    return DiscoveryResult(missions=discovered, warnings=warnings)


def discover_missions(context: DiscoveryContext) -> list[DiscoveredMission]:
    """Discover missions by precedence.

    Includes shadowed missions with `selected=False` so callers can surface
    collisions with origin metadata.

    For load-failure warnings, use discover_missions_with_warnings() instead.
    """
    return discover_missions_with_warnings(context).missions


def load_mission_template(path_or_key: str, context: DiscoveryContext | None = None) -> MissionTemplate:
    """Load mission template by explicit path or discovered mission key."""
    candidate_path = Path(path_or_key)

    if candidate_path.exists():
        if candidate_path.is_dir():
            candidate_path = candidate_path / "mission.yaml"
        return load_mission_template_file(candidate_path)

    if context is None:
        context = DiscoveryContext()

    discovered = discover_missions(context)
    for item in discovered:
        if item.key == path_or_key and item.selected:
            return load_mission_template_file(Path(item.path))

    raise MissionRuntimeError(
        f"Mission '{path_or_key}' not found. Checked discovery tiers via context={context.model_dump()}"
    )
