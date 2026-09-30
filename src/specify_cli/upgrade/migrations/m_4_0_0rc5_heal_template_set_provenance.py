"""Heal legacy absolute paths for built-in template-set catalog references.

The 3.2.7 provenance migration intentionally excluded ``template_set`` rows.
That migration is already applied by some version-window projects, so this
forward migration owns only that previously excluded catalog field. A stale
absolute path is healed when it is under the current built-in pack root or is
proven to come from a former Spec Kitty checkout by its project metadata,
canonical Git origin, and tracked mission path. This also repairs a path that
still exists in another checkout, and a missing worktree file while its checkout
metadata and Git index remain available. A matching suffix alone is ambiguous;
paths without checkout evidence stay unchanged and are reported by the doctor.
"""

from __future__ import annotations

import subprocess
from collections.abc import Mapping
from pathlib import Path, PurePosixPath, PureWindowsPath
import stat
import tomllib
from typing import Any
from urllib.parse import urlsplit

from charter.bundle import CHARTER_YAML
from charter.missions import MissionsRootNotFound, MissionTemplateRepository
from charter.pack_paths import PackRootNotFound
from charter.provenance import is_built_in_pack_path, to_portable_source_path
from kernel.paths import BUILT_IN_PACK_SIBLING_PATTERN
from kernel.sibling_paths import SiblingPathNotFound

from ..registry import MigrationRegistry
from .base import BaseMigration, MigrationResult, MigrationStateUnreadableError

MIGRATION_ID = "4_0_0rc5_heal_template_set_provenance"
TARGET_VERSION = "4.0.0rc5"

_CATALOG_KIND = "template_set"
_MISSION_CONFIG_FILENAME = "mission.yaml"
_BUILT_IN_ROOT_PARTS = BUILT_IN_PACK_SIBLING_PATTERN.parts
_SPEC_KITTY_PROJECT_NAME = "spec-kitty-cli"
_SPEC_KITTY_REPOSITORY = "github.com/spec-kitty/spec-kitty"


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


def _expected_mission_suffix(mission: Any) -> str | None:
    if not isinstance(mission, str) or not mission or "/" in mission or "\\" in mission:
        return None
    if mission in {".", ".."}:
        return None
    return f"{_BUILT_IN_ROOT_PARTS[-1]}/missions/{mission}/{_MISSION_CONFIG_FILENAME}"


def _mission_token(mission: Any) -> str | None:
    if _expected_mission_suffix(mission) is None:
        return None

    try:
        repo = MissionTemplateRepository.default()
    except (MissionsRootNotFound, PackRootNotFound, SiblingPathNotFound, OSError, ValueError):
        return None

    source = repo._mission_config_path(mission) or (repo._missions_root / mission / _MISSION_CONFIG_FILENAME)
    token = to_portable_source_path(source, project_root=None)
    return token if _portable_builtin_suffix(token) is not None else None


def _matches_canonical_source_shape(source_path: str, token_suffix: str) -> bool:
    source_parts = PurePosixPath(source_path.replace("\\", "/")).parts
    expected_parts = PurePosixPath(token_suffix).parts
    if len(source_parts) < len(expected_parts) or source_parts[-len(expected_parts) :] != expected_parts:
        return False

    built_in_index = len(source_parts) - len(expected_parts)
    root_start = built_in_index - len(_BUILT_IN_ROOT_PARTS) + 1
    return root_start >= 0 and source_parts[root_start : built_in_index + 1] == _BUILT_IN_ROOT_PARTS


def _is_spec_kitty_repository(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized.startswith("git@github.com:"):
        normalized = f"ssh://{normalized.replace(':', '/', 1)}"
    parsed = urlsplit(normalized)
    repository = f"{parsed.hostname}{parsed.path.rstrip('/').removesuffix('.git')}"
    if repository != _SPEC_KITTY_REPOSITORY:
        return False
    return parsed.scheme in {"https", "ssh"}


def _source_path_snapshot(checkout_root: Path, relative_source: PurePosixPath) -> tuple[tuple[int, int, int], ...] | None:
    if not checkout_root.is_absolute() or relative_source.is_absolute():
        return None

    components = (*checkout_root.parts[1:], *relative_source.parts)
    if any(part in {"", ".", ".."} for part in components):
        return None

    current = Path(checkout_root.anchor)
    snapshot: list[tuple[int, int, int]] = []
    for index, part in enumerate(components):
        current /= part
        try:
            metadata = current.lstat()
        except FileNotFoundError:
            return tuple(snapshot)
        mode = metadata.st_mode
        if stat.S_ISLNK(mode):
            return None
        is_final = index == len(components) - 1
        if is_final and not stat.S_ISREG(mode):
            return None
        if not is_final and not stat.S_ISDIR(mode):
            return None
        snapshot.append((metadata.st_dev, metadata.st_ino, stat.S_IFMT(mode)))
    return tuple(snapshot)


def _checkout_tracks_mission(
    checkout_root: Path,
    relative_source: PurePosixPath,
    initial_source_snapshot: tuple[tuple[int, int, int], ...],
) -> bool:
    try:
        metadata = tomllib.loads((checkout_root / "pyproject.toml").read_text(encoding="utf-8"))
        project = metadata.get("project")
        if not isinstance(project, dict) or project.get("name") != _SPEC_KITTY_PROJECT_NAME:
            return False
        urls = project.get("urls")
        repository = (
            next(
                (value for key, value in urls.items() if key.lower() == "repository" and isinstance(value, str)),
                None,
            )
            if isinstance(urls, dict)
            else None
        )
        if repository is None or not _is_spec_kitty_repository(repository):
            return False

        top_level = subprocess.run(
            ["git", "-C", str(checkout_root), "rev-parse", "--show-toplevel"],
            check=True,
            capture_output=True,
            text=True,
            timeout=2,
        ).stdout.strip()
        if Path(top_level).resolve() != checkout_root.resolve():
            return False
        origin = subprocess.run(
            ["git", "-C", str(checkout_root), "remote", "get-url", "origin"],
            check=True,
            capture_output=True,
            text=True,
            timeout=2,
        ).stdout.strip()
        if not _is_spec_kitty_repository(origin):
            return False
        before_query = _source_path_snapshot(checkout_root, relative_source)
        if before_query is None or before_query != initial_source_snapshot:
            return False
        index_entries = subprocess.run(
            ["git", "-C", str(checkout_root), "ls-files", "--stage", "--error-unmatch", "--", relative_source.as_posix()],
            check=True,
            capture_output=True,
            text=True,
            timeout=2,
        ).stdout.splitlines()
        after_query = _source_path_snapshot(checkout_root, relative_source)
    except (OSError, subprocess.SubprocessError, tomllib.TOMLDecodeError, ValueError):
        return False
    if after_query is None or after_query != before_query:
        return False
    if len(index_entries) != 1:
        return False
    index_metadata, separator, indexed_path = index_entries[0].partition("\t")
    fields = index_metadata.split()
    return bool(separator) and indexed_path == relative_source.as_posix() and len(fields) == 3 and fields[0] in {"100644", "100755"} and fields[2] == "0"


def _has_former_checkout_proof(source_path: str, token_suffix: str) -> bool:
    source = Path(source_path)
    relative_parts = (*_BUILT_IN_ROOT_PARTS, *PurePosixPath(token_suffix).parts[1:])
    relative_source = PurePosixPath(*relative_parts)
    checkout_root = source
    for _part in relative_parts:
        checkout_root = checkout_root.parent

    initial_source_snapshot = _source_path_snapshot(checkout_root, relative_source)
    if initial_source_snapshot is None:
        return False
    resolved_root = checkout_root.resolve()
    expected_source = resolved_root.joinpath(*relative_parts)
    if source.resolve() != expected_source.resolve():
        return False
    return _checkout_tracks_mission(checkout_root, relative_source, initial_source_snapshot)


def _matches_mission_source(source_path: str, token: str) -> bool:
    source = Path(source_path)
    if not _is_absolute_path(source_path) or not source.is_absolute():
        return False

    token_suffix = _portable_builtin_suffix(token)
    if token_suffix is None or not _matches_canonical_source_shape(source_path, token_suffix):
        return False

    try:
        return is_built_in_pack_path(source_path) or _has_former_checkout_proof(source_path, token_suffix)
    except (OSError, RuntimeError, ValueError):
        return False


def _load_charter_document(charter_path: Path) -> Any:
    """Load ``charter.yaml``, failing closed when it cannot be read.

    An unreadable charter is not "nothing to heal": treating it that way lets
    the runner record a skip and stamp past this migration for good. Raise
    :class:`MigrationStateUnreadableError` so the upgrade fails and retries.
    """
    from charter.activation.charter_yaml_io import load_charter_yaml  # noqa: PLC0415
    from ruamel.yaml.error import YAMLError  # noqa: PLC0415

    try:
        return load_charter_yaml(charter_path)
    except (YAMLError, OSError, UnicodeDecodeError) as exc:
        raise MigrationStateUnreadableError(f"{charter_path} could not be read ({type(exc).__name__}); provenance was not evaluated") from exc


def _healable_references(project_path: Path, document: Any | None = None) -> list[tuple[dict[str, Any], str]]:
    from charter.activation.charter_yaml_io import catalog_field_from_document  # noqa: PLC0415

    charter_path = _charter_path(project_path)
    if not charter_path.is_file():
        return []

    if document is None:
        document = _load_charter_document(charter_path)
    # Same Mapping predicate as `catalog_field_from_document`, so the two
    # "is this document-like" gates cannot disagree on a non-dict Mapping.
    catalog = document.get("catalog") if isinstance(document, Mapping) else None
    if not isinstance(catalog, Mapping):
        return []

    # Read the mission from the already-loaded document: no second disk read.
    mission = catalog_field_from_document(document, "mission")
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
    return [
        f"charter.yaml catalog[{reference.get('id', '?')}].source_path={reference.get('source_path')!r}" for reference, _token in _healable_references(project_path)
    ]


def describe_template_set_ambiguities(project_path: Path) -> list[str]:
    """Return candidate legacy template paths whose checkout identity is unproven."""
    from charter.activation.charter_yaml_io import catalog_field_from_document  # noqa: PLC0415

    charter_path = _charter_path(project_path)
    if not charter_path.is_file():
        return []

    document = _load_charter_document(charter_path)
    # Same Mapping predicate as `catalog_field_from_document`, so the two
    # "is this document-like" gates cannot disagree on a non-dict Mapping.
    catalog = document.get("catalog") if isinstance(document, Mapping) else None
    if not isinstance(catalog, Mapping):
        return []
    # Read the mission from the document just loaded: no second disk read.
    suffix = _expected_mission_suffix(catalog_field_from_document(document, "mission"))
    if suffix is None:
        return []
    template_set = catalog.get("template_set")
    if not isinstance(template_set, str) or not template_set:
        return []
    expected_id = f"TEMPLATE_SET:{template_set}"
    references = catalog.get("references")
    if not isinstance(references, list):
        return []

    ambiguous: list[str] = []
    for reference in references:
        if not isinstance(reference, dict) or reference.get("kind") != _CATALOG_KIND or reference.get("id") != expected_id:
            continue
        source_path = reference.get("source_path")
        if not isinstance(source_path, str) or not _is_absolute_path(source_path):
            continue
        if not PureWindowsPath(source_path).is_absolute() and not Path(source_path).is_absolute():
            continue
        if _matches_mission_source(source_path, f"${{SPEC_KITTY_PACKS_ROOT}}/{suffix}"):
            continue
        source_parts = PurePosixPath(source_path.replace("\\", "/")).parts
        suffix_parts = PurePosixPath(suffix).parts
        if len(source_parts) >= len(suffix_parts) and source_parts[-len(suffix_parts) :] == suffix_parts:
            ambiguous.append(
                f"ambiguous template-set provenance (checkout identity cannot be verified; path not healed and left unchanged): "
                f"charter.yaml catalog[{expected_id}].source_path={source_path!r}"
            )
    return ambiguous


@MigrationRegistry.register
class HealTemplateSetProvenanceMigration(BaseMigration):
    """Rewrite legacy built-in template-set source paths to portable tokens."""

    migration_id = MIGRATION_ID
    description = "Rewrite stale absolute built-in mission-template source_path entries in charter.yaml catalog references to portable pack tokens."
    target_version = TARGET_VERSION
    runs_on_worktrees = False

    def detect(self, project_path: Path) -> bool:
        return bool(_healable_references(project_path))

    def can_apply(self, project_path: Path) -> tuple[bool, str]:
        if self.detect(project_path):
            return True, ""
        return False, "no stale built-in template_set source_path found in charter.yaml"

    def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:
        charter_path = _charter_path(project_path)
        if not charter_path.is_file():
            return MigrationResult(success=True)

        from charter.activation.charter_yaml_io import update_charter_yaml_section  # noqa: PLC0415

        document = _load_charter_document(charter_path)
        healable = _healable_references(project_path, document)
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
