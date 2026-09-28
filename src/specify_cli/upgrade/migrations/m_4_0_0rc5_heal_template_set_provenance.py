"""Heal legacy absolute paths for built-in template-set catalog references.

The 3.2.7 provenance migration intentionally excluded ``template_set`` rows.
That migration is already applied by some version-window projects, so this
forward migration owns only that previously excluded catalog field. A stale
absolute path from another checkout is recognized by its mission-specific
``built-in/missions/<mission>/mission.yaml`` suffix beneath the canonical
``packs/built-in`` tree shape and rewritten to the canonical token. This also
repairs a path that still exists in another checkout. An existing path outside
the current root and that canonical tree shape is preserved: it may be mutable
external authority and cannot be safely inferred to be a built-in source.
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

from charter.bundle import CHARTER_YAML
from charter.offering.missions import MissionTemplateRepository
from charter.offering.missions.repository import MissionsRootNotFound
from charter.offering.pack_paths import PackRootNotFound
from charter.offering.provenance import is_built_in_pack_path, to_portable_source_path
from kernel.paths import BUILT_IN_PACK_SIBLING_PATTERN
from kernel.sibling_paths import SiblingPathNotFound

from ..registry import MigrationRegistry
from .base import BaseMigration, MigrationResult

MIGRATION_ID = "4_0_0rc5_heal_template_set_provenance"
TARGET_VERSION = "4.0.0rc5"

_CATALOG_KIND = "template_set"
_MISSION_CONFIG_FILENAME = "mission.yaml"
_BUILT_IN_ROOT_PARTS = BUILT_IN_PACK_SIBLING_PATTERN.parts


def _charter_path(project_path: Path) -> Path:
    charter_path: Path = project_path / CHARTER_YAML
    return charter_path


def _is_absolute_path(value: str) -> bool:
    return Path(value).is_absolute() or PureWindowsPath(value).is_absolute()


def _portable_builtin_suffix(token: str) -> str | None:
    if not token.startswith("${"):
        return None
    suffix = token.partition("}/")[2]
    builtin_segment = f"{_BUILT_IN_ROOT_PARTS[-1]}/"
    return suffix if suffix.startswith(builtin_segment) else None


def _mission_token(mission: Any) -> str | None:
    if not isinstance(mission, str) or not mission or "/" in mission or "\\" in mission:
        return None
    if mission in {".", ".."}:
        return None

    try:
        repo = MissionTemplateRepository.default()
    except (MissionsRootNotFound, PackRootNotFound, SiblingPathNotFound, OSError, ValueError):
        return None

    source = repo._mission_config_path(mission) or (repo._missions_root / mission / _MISSION_CONFIG_FILENAME)
    token = to_portable_source_path(source, project_root=None)
    return token if _portable_builtin_suffix(token) is not None else None


def _matches_mission_source(source_path: str, token: str) -> bool:
    if not _is_absolute_path(source_path):
        return False

    token_suffix = _portable_builtin_suffix(token)
    if token_suffix is None:
        return False
    expected_parts = PurePosixPath(token_suffix).parts
    source_parts = PurePosixPath(source_path.replace("\\", "/")).parts
    if len(source_parts) < len(expected_parts) or source_parts[-len(expected_parts) :] != expected_parts:
        return False

    try:
        current_builtin = is_built_in_pack_path(source_path)
        built_in_index = len(source_parts) - len(expected_parts)
        root_start = built_in_index - len(_BUILT_IN_ROOT_PARTS) + 1
        has_canonical_root_shape = root_start >= 0 and source_parts[root_start : built_in_index + 1] == _BUILT_IN_ROOT_PARTS
        if not current_builtin and not has_canonical_root_shape:
            return False

        source = Path(source_path)
        if source.is_symlink() and not current_builtin:
            return False
    except (OSError, RuntimeError, ValueError):
        return False

    return True


def _healable_references(charter_path: Path, document: Any | None = None) -> list[tuple[dict[str, Any], str]]:
    if not charter_path.is_file():
        return []

    if document is None:
        from charter.activation.charter_yaml_io import load_charter_yaml  # noqa: PLC0415

        document = load_charter_yaml(charter_path)
    catalog = document.get("catalog") if hasattr(document, "get") else None
    if not isinstance(catalog, dict):
        return []

    mission = catalog.get("mission")
    template_set = catalog.get("template_set")
    if not isinstance(template_set, str) or not template_set:
        return []
    expected_id = f"TEMPLATE_SET:{template_set}"
    token = _mission_token(mission)
    if token is None:
        return []

    references = catalog.get("references")
    if not isinstance(references, list):
        return []

    healable: list[tuple[dict[str, Any], str]] = []
    for reference in references:
        if not isinstance(reference, dict) or reference.get("kind") != _CATALOG_KIND:
            continue
        if reference.get("id") != expected_id:
            continue
        source_path = reference.get("source_path")
        if isinstance(source_path, str) and _matches_mission_source(source_path, token):
            healable.append((reference, token))
    return healable


def describe_template_set_leaks(project_path: Path) -> list[str]:
    """Return stale built-in template-set source paths without changing files."""
    charter_path = _charter_path(project_path)
    return [
        f"charter.yaml catalog[{reference.get('id', '?')}].source_path={reference.get('source_path')!r}" for reference, _token in _healable_references(charter_path)
    ]


@MigrationRegistry.register
class HealTemplateSetProvenanceMigration(BaseMigration):  # type: ignore[misc]  # follow_imports=skip erases BaseMigration's ABC type in narrow checks
    """Rewrite legacy built-in template-set source paths to portable tokens."""

    migration_id = MIGRATION_ID
    description = "Rewrite stale absolute built-in mission-template source_path entries in charter.yaml catalog references to portable pack tokens."
    target_version = TARGET_VERSION
    runs_on_worktrees = False

    def detect(self, project_path: Path) -> bool:
        return bool(_healable_references(_charter_path(project_path)))

    def can_apply(self, project_path: Path) -> tuple[bool, str]:
        if self.detect(project_path):
            return True, ""
        return False, "no stale built-in template_set source_path found in charter.yaml"

    def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:
        charter_path = _charter_path(project_path)
        if not charter_path.is_file():
            return MigrationResult(success=True)

        from charter.activation.charter_yaml_io import load_charter_yaml, update_charter_yaml_section  # noqa: PLC0415

        document = load_charter_yaml(charter_path)
        healable = _healable_references(charter_path, document)
        if not healable:
            return MigrationResult(success=True)

        catalog = document["catalog"]
        changes: list[str] = []
        for reference, token in healable:
            old_value = reference["source_path"]
            changes.append(f"charter.yaml catalog[{reference.get('id', '?')}].source_path: {old_value} -> {token}")
            if not dry_run:
                reference["source_path"] = token

        if changes and not dry_run:
            update_charter_yaml_section(charter_path, "catalog", catalog)
        return MigrationResult(success=True, changes_made=changes)
