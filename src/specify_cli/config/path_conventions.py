"""Project-level path-convention override reader (#3016, per-type sections #7748).

Reads the ``project.path_conventions`` subkey of ``.kittify/config.yaml`` and returns a validated,
remap-only override. Resolved AHEAD of mission-type doctrine defaults by
``validators.paths.validate_mission_paths`` (see ADR project-path-convention-override-precedes-doctrine),
the override lets a project whose real source layout is not ``src/`` (Django ``apps/``, Go ``internal/``,
a content repository's ``packs/``) be accepted honestly -- WITHOUT changing the blocking-by-default policy
established by #3783.

Two shapes live side by side under ``project.path_conventions``:

* **flat** -- ``<path-key>: <directory>``: applies to every mission type that declares the key;
* **per-type section** (#7748) -- ``<mission-type-id>: {<path-key>: <directory>, ...}``: applies to
  Missions of that type only. Per key the resolved directory is the per-type value, else the flat value,
  else the mission default; the merge itself happens at the accept seam
  (:meth:`ProjectPathConventions.for_mission_type`).

Fail-closed policy (FR-008): a malformed ``path_conventions`` *section* -- present but not a mapping, a
non-string / null value, an unknown key, a per-type section keyed by an id outside the project's layered
mission-type roster (built-in -> org -> project), or a roster that cannot be read while a per-type section
exists -- raises :class:`PathConventionsConfigError`. This is scoped to the section shape only: an absent
key, or a whole ``config.yaml`` that is missing/unreadable, returns an empty override (lenient), matching
the co-resident section readers (e.g. ``charter_runtime/preflight/config.py``).
"""

from __future__ import annotations

import warnings
from collections.abc import Callable, Collection, Mapping
from pathlib import Path
from types import MappingProxyType
from typing import Any

from specify_cli.mission import VALID_PATH_KEYS

# Only the runtime entry point and its return type are exported. ``ARTIFACT_ROUTED_KEYS`` is a
# module-internal constant and ``PathConventionsConfigError`` propagates as a typed exception (SC-007)
# rather than being caught by a co-resident src caller; both stay importable by name (tests reference
# them directly) without entering the exported surface, keeping the symbol-level dead-code gate honest.
__all__ = ["ProjectPathConventions", "load_project_path_conventions"]

# Keys whose mission default value is a mission artifact token (they resolve on the mission's
# ``feature_dir`` rather than the repo root). Overriding one would flip its resolution surface and drop
# the mission-surface artifact check — ``validators.paths`` decides routing from ``declared[key]`` — so
# they are excluded from the override vocabulary (C-010). ``deliverables`` (default value ``contracts/``)
# is the sole such key across the four built-in mission types.
ARTIFACT_ROUTED_KEYS: frozenset[str] = frozenset({"deliverables"})

# The section key, hoisted so the error/warning f-strings below don't repeat the literal (Sonar S1192).
_SECTION = "project.path_conventions"

#: Supplies the ids a per-type section may be keyed by. Injectable for tests; production resolves the
#: layered mission-type roster (operator ruling Q3, Mission path-conventions-per-type-01M7VRQM).
MissionTypeIds = Callable[[], Collection[str]]


class PathConventionsConfigError(ValueError):
    """Raised when the ``project.path_conventions`` section is malformed (FR-008)."""


class ProjectPathConventions(dict[str, str]):
    """The validated override: the flat mapping (this dict's content) plus per-type sections.

    A ``dict`` subclass so the flat form compares and copies exactly as the plain mapping this reader
    returned before per-type sections existed (backward compatible, NFR-002).
    """

    def __init__(
        self,
        flat: Mapping[str, str] | None = None,
        per_type: Mapping[str, Mapping[str, str]] | None = None,
    ) -> None:
        super().__init__(flat or {})
        self._per_type: Mapping[str, Mapping[str, str]] = MappingProxyType(
            {type_id: MappingProxyType(dict(section)) for type_id, section in (per_type or {}).items()}
        )

    @property
    def per_type(self) -> Mapping[str, Mapping[str, str]]:
        """Read-only per-mission-type sections, keyed by mission-type id."""
        return self._per_type

    def for_mission_type(self, mission_type: str | None) -> dict[str, str]:
        """The overrides for a Mission of ``mission_type``: per-type over flat, key by key.

        ``None`` (or a type with no section) yields the flat overrides only.
        """
        resolved = dict(self)
        if mission_type is not None:
            resolved.update(self._per_type.get(mission_type, {}))
        return resolved


def _layered_mission_type_ids(repo_root: Path) -> MissionTypeIds:
    """The production roster: the layered mission-type roster (built-in -> org -> project).

    Reuses the one CLI seam (``resolve_layered_roster``) rather than re-deriving the
    ``(mission_types_dirs, PackContext)`` construction (DIRECTIVE_044). Imported lazily: it is only
    needed when a per-type section exists (NFR-001), and keeps this config module import-light.
    """

    def _ids() -> Collection[str]:
        from specify_cli.cli.commands.charter.mission_type import resolve_layered_roster  # noqa: PLC0415

        return frozenset(resolve_layered_roster(repo_root))

    return _ids


def _validated_value(label: str, value: object) -> str:
    """Validate one override value; ``label`` is ``key`` (flat) or ``type.key`` (per-type)."""
    if not isinstance(value, str):
        raise PathConventionsConfigError(f"{_SECTION}.{label} must be a string directory, got {type(value).__name__}.")
    if not value.strip():
        # An empty/blank value collapses `Path("")` to the repo root under
        # `validate_mission_paths`, which always exists — silently defeating strict
        # enforcement (SC-006/SC-007) instead of naming the missing directory.
        raise PathConventionsConfigError(f"{_SECTION}.{label} must not be empty or blank.")
    normalized_value = value.strip()
    candidate = Path(normalized_value)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise PathConventionsConfigError(f"{_SECTION}.{label} must be a repo-relative path with no '..' traversal, got {value!r}.")
    return normalized_value


#: ``warnings.warn`` stack depths that point a deliverables warning at the caller of
#: :func:`load_project_path_conventions` (flat: warn <- _is_artifact_routed <- _split_section <-
#: load <- caller; per-type: one frame deeper, through _validated_per_type).
_FLAT_WARN_STACKLEVEL = 4
_SECTION_WARN_STACKLEVEL = 5


def _is_artifact_routed(key: str, label: str, *, stacklevel: int) -> bool:
    """Warn about (and report) an artifact-routed key, which is never overridable (C-010)."""
    if key not in ARTIFACT_ROUTED_KEYS:
        return False
    warnings.warn(
        f"{_SECTION}.{label} is ignored: {key!r} is artifact-routed and cannot be "
        "overridden (it would flip the artifact-resolution surface). See ADR "
        "project-path-convention-override-precedes-doctrine.",
        stacklevel=stacklevel,
    )
    return True


def _validated_section(type_id: str, section: object) -> dict[str, str]:
    """Validate one per-type section's inner keys and values (FR-004)."""
    if not isinstance(section, dict):
        raise PathConventionsConfigError(f"{_SECTION}.{type_id} must be a mapping of path-convention key to directory, got {type(section).__name__}.")
    validated: dict[str, str] = {}
    for key, value in section.items():
        label = f"{type_id}.{key}"
        if key not in VALID_PATH_KEYS:
            raise PathConventionsConfigError(f"Unknown path-convention key {label!r} in {_SECTION}. Known keys: {sorted(VALID_PATH_KEYS)}.")
        if _is_artifact_routed(str(key), label, stacklevel=_SECTION_WARN_STACKLEVEL):
            continue
        validated[str(key)] = _validated_value(label, value)
    return validated


def _is_section_candidate(key: object, value: object) -> bool:
    """Decide by the value's shape whether an entry is a per-type section (review cycle 1).

    A flat value is always a string, so every mapping value is a per-type section -- also under a
    key that is a path key as well (``documentation`` is both a path key and a mission-type id). A
    non-string under a key that is not a path key is a malformed section, never a flat typo.
    """
    return isinstance(value, dict) or (key not in VALID_PATH_KEYS and not isinstance(value, str))


def _split_section(section: Mapping[Any, Any]) -> tuple[dict[str, str], dict[str, object]]:
    """Split the section into validated flat overrides and raw per-type candidates."""
    flat: dict[str, str] = {}
    candidates: dict[str, object] = {}
    for key, value in section.items():
        if _is_section_candidate(key, value):
            candidates[str(key)] = value
            continue
        if key not in VALID_PATH_KEYS:
            raise PathConventionsConfigError(f"Unknown path-convention key {key!r} in {_SECTION}. Known keys: {sorted(VALID_PATH_KEYS)}.")
        if _is_artifact_routed(str(key), str(key), stacklevel=_FLAT_WARN_STACKLEVEL):
            continue
        flat[str(key)] = _validated_value(str(key), value)
    return flat, candidates


def _known_mission_types(mission_type_ids: MissionTypeIds) -> frozenset[str]:
    """Read the roster once; any failure is a fail-closed configuration error (FR-003)."""
    try:
        return frozenset(mission_type_ids())
    except Exception as exc:  # noqa: BLE001 — translated, never swallowed: a per-type key cannot be validated.
        raise PathConventionsConfigError(f"{_SECTION}: could not read the mission-type roster to validate per-type sections: {exc}") from exc


def _unknown_section_message(type_id: str, known: frozenset[str]) -> str:
    """Name the mistake for a section whose id is not in the roster."""
    if type_id in VALID_PATH_KEYS:
        return (
            f"{_SECTION}.{type_id} is a mapping, so it is read as a per-type section, but {type_id!r} is not a "
            f"mission type. A path-convention value must be a string directory. Known mission types: {sorted(known)}."
        )
    return f"Unknown mission type {type_id!r} in {_SECTION}. Known mission types: {sorted(known)}."


def _validated_per_type(candidates: Mapping[str, object], mission_type_ids: MissionTypeIds) -> dict[str, dict[str, str]]:
    """Validate the per-type candidates' ids against the roster, then their contents."""
    if not candidates:
        return {}
    known = _known_mission_types(mission_type_ids)
    per_type: dict[str, dict[str, str]] = {}
    for type_id, section in candidates.items():
        if type_id not in known:
            raise PathConventionsConfigError(_unknown_section_message(type_id, known))
        per_type[type_id] = _validated_section(type_id, section)
    return per_type


def _read_section(repo_root: Path) -> object:
    """Return the raw ``project.path_conventions`` value, or ``None`` when absent/unreadable (lenient)."""
    config_path = repo_root / ".kittify" / "config.yaml"
    if not config_path.exists():
        return None
    try:
        from ruamel.yaml import YAML

        yaml = YAML(typ="safe")
        data = yaml.load(config_path)
    except Exception:  # noqa: BLE001 — best-effort file read; a corrupt file never breaks accept.
        return None
    if not isinstance(data, dict):
        return None
    project = data.get("project")
    if not isinstance(project, dict):
        return None
    return project.get("path_conventions")


def load_project_path_conventions(
    repo_root: Path,
    *,
    mission_type_ids: MissionTypeIds | None = None,
) -> ProjectPathConventions:
    """Return the validated project ``path_conventions`` override (empty when absent).

    Reads ONLY the ``project.path_conventions`` subkey — never the whole ``project:`` block, which
    carries identity fields (``uuid``/``slug``/``node_id``/``build_id``) that must not be rejected (C-011).
    Remap-only: an artifact-routed key (``deliverables``) is warned-and-ignored (C-010), flat or per-type;
    filtering to keys a given mission actually declares happens at the merge site in
    ``validate_mission_paths``.

    Args:
        repo_root: Repository root containing ``.kittify/config.yaml``.
        mission_type_ids: The ids a per-type section may be keyed by. Defaults to the project's layered
            mission-type roster; called at most once, and only when a per-type section exists (NFR-001).

    Returns:
        The flat overrides (the mapping content) plus per-type sections (``per_type``).

    Raises:
        PathConventionsConfigError: the section is present but not a mapping, names a key outside
            :data:`specify_cli.mission.VALID_PATH_KEYS` (a typo), carries a non-string/null value, an
            empty/blank-string value (a bare ``Path("")`` collapses to the repo root, which always
            exists, silently defeating strict enforcement), or a value that is an absolute path or
            contains a ``..`` traversal segment (override values are repo-relative layout dirs only);
            or a per-type section is keyed by an unknown mission type, is not a mapping, breaks any of
            the value rules above, or the roster needed to validate it cannot be read.
            Section-shape only — a missing or unreadable ``config.yaml`` is lenient and returns empty.
    """
    section = _read_section(repo_root)
    if section is None:
        return ProjectPathConventions()
    if not isinstance(section, dict):
        raise PathConventionsConfigError(f"{_SECTION} must be a mapping of path-convention key to directory, got {type(section).__name__}.")
    flat, candidates = _split_section(section)
    roster = mission_type_ids if mission_type_ids is not None else _layered_mission_type_ids(repo_root)
    return ProjectPathConventions(flat, _validated_per_type(candidates, roster))
