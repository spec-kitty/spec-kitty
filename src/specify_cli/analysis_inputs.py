"""Conservative declarative dependency closure for report-only analysis.

Runtime/status/cache outputs are deliberately not inputs. Explicit authority
references are included even when absent; directory membership is represented
by the set of entries, so adding a new authority also invalidates a report.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from charter.activation.context_renderers.authority_paths import DEFAULT_AUTHORITY_PATHS
from charter.activation.pack_context import resolve_charter_yaml_pointer
from charter.bundle import CHARTER_MD, CHARTER_YAML
from charter.drg import load_pack_registry
from charter.pack_paths import PackRootNotFound, built_in_root
from kernel.paths import get_package_asset_root


class MaterialInputError(ValueError):
    """The declared dependency closure cannot be safely represented."""


def _mapping(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        value = YAML(typ="safe").load(path.read_text(encoding="utf-8"))
    except YAMLError as exc:
        raise MaterialInputError(f"Malformed material input: {path.name}") from exc
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise MaterialInputError(f"Expected mapping in {path.name}")
    return value


def _safe_path(root: Path, path: Path) -> Path:
    try:
        relative = path.relative_to(root)
    except ValueError as exc:
        raise MaterialInputError("External mutable analysis authority is unsupported") from exc
    cursor = root
    for part in relative.parts:
        if part == "..":
            raise MaterialInputError("Analysis authority escapes repository")
        cursor /= part
        if cursor.is_symlink():
            raise MaterialInputError("Analysis authority contains a symlink")
    return path


def _declared_paths(charter: dict[str, Any]) -> list[str]:
    from charter.activation.sync import apply_legacy_governance_selection_key_compat

    governance = charter.get("governance", {})
    doctrine = apply_legacy_governance_selection_key_compat(governance).get("charter", {}) if isinstance(governance, dict) else {}
    if not isinstance(doctrine, dict):
        raise MaterialInputError("governance.doctrine must be a mapping")
    paths = list(DEFAULT_AUTHORITY_PATHS)
    for key in ("authority_paths", "governance_references"):
        declared = doctrine.get(key, [])
        if not isinstance(declared, list) or not all(isinstance(value, str) for value in declared):
            raise MaterialInputError(f"{key} must be a list of paths")
        paths.extend(declared)
    return paths


def _references(value: Any, field: str) -> list[str]:
    paths = []
    if isinstance(value, dict):
        for key, nested in value.items():
            if key == field and isinstance(nested, str) and nested:
                paths.append(nested)
            else:
                paths.extend(_references(nested, field))
    elif isinstance(value, list):
        for nested in value:
            paths.extend(_references(nested, field))
    return paths


def _entry(path: Path, root: Path, feature_dir: Path) -> dict[str, str | None]:
    from specify_cli.analysis_report import _artifact_hash_entry, _sha256_text
    from specify_cli.frontmatter import FrontmatterError, FrontmatterManager
    from specify_cli.migration.strip_frontmatter import MUTABLE_FIELDS

    relative = path.relative_to(root).as_posix()
    if path.is_dir():
        return {"path": relative, "sha256": "directory"}
    if not path.exists():
        return {"path": relative, "sha256": None}
    if path.parent == feature_dir / "tasks" and path.suffix == ".md" and path.name.startswith("WP"):
        try:
            metadata, body = FrontmatterManager().read(path)
        except FrontmatterError as exc:
            raise MaterialInputError(f"Invalid WP definition: {path.name}") from exc
        static = {key: value for key, value in metadata.items() if key not in MUTABLE_FIELDS}
        return {"path": relative, "sha256": _sha256_text(json.dumps(static, sort_keys=True, default=str) + "\n" + body)}
    return _artifact_hash_entry(path, root)


def _source_paths(charter: dict[str, Any], root: Path) -> list[Path]:
    paths = []
    for value in _references(charter, "source_path"):
        # Bundled provenance is covered by its digest; URL provenance is
        # declarative charter text, not a filesystem dependency.
        if value.startswith("${SPEC_KITTY_PACKS_ROOT}/") or "://" in value:
            continue
        if "$" in value:
            raise MaterialInputError("Unresolved external authority source is unsupported")
        paths.append(root / value)
    return paths


def _package_inputs() -> dict[str, dict[str, str | None]]:
    """Content-pin bundled authority without embedding machine-local paths."""
    from specify_cli.analysis_report import _sha256_file, _sha256_text

    if os.environ.get("SPEC_KITTY_PACKS_ROOT") or os.environ.get("SPEC_KITTY_TEMPLATE_ROOT"):
        raise MaterialInputError("Environment-selected mutable package authority is unsupported")
    result = {}
    try:
        roots = (("built-in", built_in_root()), ("mission-assets", get_package_asset_root()))
    except (PackRootNotFound, OSError) as exc:
        raise MaterialInputError("Bundled analysis authority unavailable") from exc
    for label, root in roots:
        rows = []
        for path in sorted(root.rglob("*")):
            if path.is_symlink():
                raise MaterialInputError("Bundled analysis authority contains a symlink")
            if path.is_file() and "__pycache__" not in path.parts:
                rows.append(f"{path.relative_to(root).as_posix()}:{_sha256_file(path)}")
        result[f"package:{label}"] = {"path": None, "sha256": _sha256_text("\n".join(rows))}
    return result


def _resolved_template_paths(root: Path, feature_dir: Path) -> list[Path]:
    from charter.activation.mission_type_profiles import resolve_mission_type_context
    from charter.activation.pack_context import CharterPackConfigError
    from specify_cli.runtime.resolver import ResolutionTier, resolve_configured_template

    metadata = _mapping(feature_dir / "meta.json")
    mission_type = metadata.get("mission_type")
    if mission_type is None:
        return []
    try:
        context = resolve_mission_type_context(root, mission_type=mission_type)
    except CharterPackConfigError as exc:
        raise MaterialInputError("Configured charter activation is invalid") from exc
    paths = []
    for kind in context.template_set or {}:
        resolved = resolve_configured_template(kind, root, context)
        if resolved.tier in (ResolutionTier.GLOBAL, ResolutionTier.GLOBAL_MISSION):
            raise MaterialInputError("External mutable global template authority is unsupported")
        if resolved.tier is not ResolutionTier.PACKAGE_DEFAULT:
            paths.append(resolved.path)
    return paths


def collect_material_inputs(feature_dir: Path, repo_root: Path) -> dict[str, dict[str, str | None]]:
    """Collect project-owned material inputs, using canonical path authorities.

    This mode rejects external mutable org packs rather than pretending that a
    project Git transaction can establish their committed state.
    """
    from specify_cli.analysis_report import _hash_inputs

    root = repo_root.absolute()
    paths: set[Path] = set()

    def include(path: Path) -> None:
        path = _safe_path(root, path)
        if path.is_dir():
            paths.add(path)
            for child in sorted(path.iterdir()):
                include(child)
        else:
            if path.exists() and not path.is_file():
                raise MaterialInputError("Non-regular analysis authority is unsupported")
            paths.add(path)

    config_path = root / ".kittify/config.yaml"
    include(config_path)
    config = _mapping(config_path)
    charter_path = resolve_charter_yaml_pointer(root, config) or root / CHARTER_YAML
    include(charter_path)
    charter = _mapping(charter_path)
    for name in (*_hash_inputs(), "meta.json", "wps.yaml"):
        include(feature_dir / name)
    include(feature_dir / "tasks")
    # Only declarative subtrees: no charter context-state, synthesis manifest,
    # operation logs, runtime cache, status streams or generated task state.
    for name in ("missions", "overrides", "doctrine", "templates", "command-templates"):
        include(root / ".kittify" / name)
    for name in (CHARTER_MD.name, "interview/answers.yaml", "_LIBRARY"):
        include(charter_path.parent / name)
    for value in _declared_paths(charter):
        include(root / value)
    for pack in load_pack_registry(root).packs:
        include(pack.effective_root(root))

    for value in _references(charter, "local_path"):
        include(charter_path.parent / value)
    for path in _source_paths(charter, root):
        include(path)
    for path in _resolved_template_paths(root, feature_dir):
        include(path)

    result: dict[str, dict[str, str | None]] = {}
    for path in sorted(paths):
        relative = path.relative_to(root).as_posix()
        # Directory sentinels and missing-file sentinels are distinct. The
        # complete key set detects additions/removals without hashing outputs.
        result[f"material:{relative}"] = _entry(path, root, feature_dir)
    result.update(_package_inputs())
    return result
