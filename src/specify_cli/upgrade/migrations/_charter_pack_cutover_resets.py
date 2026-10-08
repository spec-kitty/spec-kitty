"""Stale activation lists, kind gates and ``[]`` of the charter-pack cutover (FR-012 step 6, #3732).

Contract: ``kitty-specs/charter-pack-cutover-01M491G6/contracts/upgrade-migration.md`` step 6.

Surfaces: the resolved activation store (the ``charter.yaml`` that
``config.yaml``'s ``charter:`` pointer names, else ``config.yaml``), and the
other file when it also carries activation keys (a leftover ``config.yaml``
mirror). Per key, in :data:`charter.activation.pack_manager.ACTIVATION_YAML_KEYS`
order:

* ``mission_type_activations``: never touched, never reported;
* ``activated_kinds``: the released ``default`` 8-kind gate is reset; the
  released ``minimal`` gate ``[directives, tactics]`` is reset and a warning
  says it was a defect (DM-01M497F0NAQARAK3JZFVWF1SD0); any other gate is kept;
* a per-artifact ``activated_<kind>: []`` is reset and a warning names the file
  and the key to set back to ``[]`` (DM-01M497EW60HNWWJQCXDFA99R0H). No CLI
  command switches a whole kind off (``charter deactivate`` removes one id
  from an explicit list), so the warning names the key to set by hand;
* a list set-equal (after :func:`normalise_id`) to a released ``default``
  list for that key is reset;
* a list set-equal to a released ``minimal`` list is kept (``matches_minimal``);
* any other list is kept (``kept_for_review``).

Writes only remove keys, through the single activation writer
(:func:`charter.activation.pack_manager.prepare_activation_write` for the
resolved store, :func:`charter.activation.charter_yaml_io.prepare_charter_yaml_section`
for the other file); every other line is kept byte for byte. The comparison
reads the frozen snapshots of :mod:`._charter_pack_cutover_snapshots`, never a
live preset. The migration runs this step only on its first application.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from kernel.charter_pack_paths import KITTIFY_DIRNAME

from ._charter_pack_cutover_report import CutoverReport
from ._charter_pack_cutover_snapshots import (
    DEFAULT_KIND_GATE,
    DEFAULT_SNAPSHOTS,
    MINIMAL_KIND_GATE,
    MINIMAL_SNAPSHOTS,
    normalise_id,
)
from .base import MigrationStateUnreadableError

if TYPE_CHECKING:
    from charter.activation.charter_yaml_io import PreparedYamlWrite

__all__ = ["apply_resets", "plan_resets"]

_CONFIG_RELPATH = Path(KITTIFY_DIRNAME, "config.yaml")
_KINDS_KEY = "activated_kinds"
_MISSION_TYPES_KEY = "mission_type_activations"
_KEY_PREFIX = "activated_"
_REMEDY = "fix the file, then run `spec-kitty upgrade` again"
_ACTIVATION_SECTION = "activation"
_EMPTY_MAPPING = b"{}\n"


class ResetOutcome(Enum):
    """What the cutover does with one activation key."""

    RESET = "reset"
    KEPT_FOR_REVIEW = "kept_for_review"
    MATCHES_MINIMAL = "matches_minimal"


@dataclass(frozen=True)
class ResetAction:
    """One activation key of one file and what the cutover does with it."""

    path: Path
    key: str
    outcome: ResetOutcome
    line: str
    """The report line (file and key)."""
    hint: str | None = None
    """A warning-only line: how to restore what the reset removed."""


# --------------------------------------------------------------------------- #
# Reading
# --------------------------------------------------------------------------- #


def _rel(path: Path, project: Path) -> str:
    try:
        return path.relative_to(project).as_posix()
    except ValueError:
        return path.as_posix()


def _load_mapping(path: Path, project: Path) -> Mapping[str, Any] | None:
    """The YAML mapping at *path*; ``None`` when absent or not a mapping; unreadable raises."""
    if not path.is_file():
        return None
    try:
        data = YAML(typ="safe").load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, YAMLError) as exc:
        raise MigrationStateUnreadableError(f"{_rel(path, project)} could not be read ({exc}); {_REMEDY}") from exc
    return data if isinstance(data, Mapping) else None


def _activation_keys() -> tuple[str, ...]:
    from charter.activation.pack_manager import ACTIVATION_YAML_KEYS

    return tuple(key for key in ACTIVATION_YAML_KEYS if key != _MISSION_TYPES_KEY)


def _surfaces(project: Path) -> list[tuple[Path, Mapping[str, Any]]]:
    """``(file, mapping)`` per surface carrying activation keys; the resolved store first."""
    from charter.activation.pack_context import resolve_charter_yaml_pointer

    config_path = project / _CONFIG_RELPATH
    config = _load_mapping(config_path, project) or {}
    pointed = resolve_charter_yaml_pointer(project, dict(config))
    paths = [config_path] if pointed is None else [pointed, config_path]
    keys = _activation_keys()
    surfaces: list[tuple[Path, Mapping[str, Any]]] = []
    for path in paths:
        data = config if path == config_path else _load_mapping(path, project)
        if data and any(key in data for key in keys):
            surfaces.append((path, data))
    return surfaces


# --------------------------------------------------------------------------- #
# Classification
# --------------------------------------------------------------------------- #


def _id_set(key: str, value: Sequence[Any]) -> frozenset[str] | None:
    """The normalised ids of *value*; ``None`` when an entry is not a string."""
    if not all(isinstance(item, str) for item in value):
        return None
    return frozenset(normalise_id(key, item) for item in value)


def _absent_meaning(key: str) -> str:
    """What the key's absence means, for the warning text."""
    from charter.offering.artifact_kinds import ArtifactKind

    plural = key.removeprefix(_KEY_PREFIX)
    noun = plural.replace("_", " ")
    if ArtifactKind.from_plural(plural).effective_when_absent == "required":
        return f"only the {noun} your org packs require are in force"
    return f"all {noun} available"


def _classify_kind_gate(path: Path, rel: str, value: frozenset[str]) -> ResetAction:
    if value == DEFAULT_KIND_GATE:
        return ResetAction(path, _KINDS_KEY, ResetOutcome.RESET, f"{rel}: {_KINDS_KEY} (matched the released default kind gate; now absent)")
    if value == MINIMAL_KIND_GATE:
        line = f"{rel}: {_KINDS_KEY} [directives, tactics] (the released minimal kind gate; now absent)"
        hint = (
            f"{rel}: {_KINDS_KEY} was [directives, tactics], the kind gate of the released `minimal` preset; "
            "it switched every other kind off, which was a defect, so it is now absent (every kind available). "
            f"To gate kinds again, set {_KINDS_KEY} in {rel}."
        )
        return ResetAction(path, _KINDS_KEY, ResetOutcome.RESET, line, hint)
    return ResetAction(path, _KINDS_KEY, ResetOutcome.KEPT_FOR_REVIEW, f"{rel}: {_KINDS_KEY} customised; not changed")


def _classify_list(path: Path, rel: str, key: str, value: frozenset[str]) -> ResetAction:
    if value in DEFAULT_SNAPSHOTS.get(key, ()):
        return ResetAction(path, key, ResetOutcome.RESET, f"{rel}: {key} (matched a released default list; now absent, every built-in available)")
    if value in MINIMAL_SNAPSHOTS.get(key, ()):
        return ResetAction(path, key, ResetOutcome.MATCHES_MINIMAL, f"{rel}: {key} matches preset minimal; not changed")
    return ResetAction(path, key, ResetOutcome.KEPT_FOR_REVIEW, f"{rel}: {key} customised; not changed")


def _empty_list_action(path: Path, rel: str, key: str) -> ResetAction:
    meaning = _absent_meaning(key)
    line = f"{rel}: {key} was [] (nothing active); now absent ({meaning})"
    hint = f"{rel}: {key} was [] (nothing active); it is now absent ({meaning}). To switch the kind off again, set {key}: [] in {rel}."
    return ResetAction(path, key, ResetOutcome.RESET, line, hint)


def _classify(path: Path, rel: str, key: str, value: Any) -> ResetAction:
    if not isinstance(value, list):
        return ResetAction(path, key, ResetOutcome.KEPT_FOR_REVIEW, f"{rel}: {key} is not a list; not changed")
    ids = _id_set(key, value)
    if ids is None:
        return ResetAction(path, key, ResetOutcome.KEPT_FOR_REVIEW, f"{rel}: {key} holds a non-string id; not changed")
    if key == _KINDS_KEY:
        return _classify_kind_gate(path, rel, ids)
    if not value:
        return _empty_list_action(path, rel, key)
    return _classify_list(path, rel, key, ids)


def plan_resets(project_path: Path) -> list[ResetAction]:
    """Classify every activation key of every surface (pure; nothing is written).

    Raises :class:`MigrationStateUnreadableError` when a surface is not readable YAML.
    """
    actions: list[ResetAction] = []
    keys = _activation_keys()
    for path, data in _surfaces(project_path):
        rel = _rel(path, project_path)
        actions.extend(_classify(path, rel, key, data[key]) for key in keys if key in data)
    return actions


# --------------------------------------------------------------------------- #
# Writing
# --------------------------------------------------------------------------- #


def _prepare_removal(project: Path, path: Path, keys: list[str], resolved_store: Path | None) -> PreparedYamlWrite:
    from charter.activation.charter_yaml_io import prepare_charter_yaml_section, prepare_yaml_write
    from charter.activation.pack_manager import prepare_activation_write

    if set(_load_mapping(path, project) or {}) <= set(keys):
        # Removing every key leaves no mapping for the span-preserving renderer to keep.
        return prepare_yaml_write(path, _EMPTY_MAPPING, section=_ACTIVATION_SECTION)
    if path == resolved_store:
        return prepare_activation_write(project, {}, remove=keys)
    return prepare_charter_yaml_section(path, _ACTIVATION_SECTION, {}, remove=keys)


def _remove_keys(project: Path, path: Path, keys: list[str], resolved_store: Path | None) -> None:
    from charter.activation.charter_yaml_io import apply_yaml_write

    apply_yaml_write(_prepare_removal(project, path, keys, resolved_store))


def _resolved_store(project: Path) -> Path | None:
    """The activation write target; ``None`` when the ``charter:`` pointer dangles."""
    from charter.activation.pack_context import ActiveCharterConfigError
    from charter.activation.pack_manager import resolve_activation_write_target

    try:
        target: Path = resolve_activation_write_target(project)[0]
    except ActiveCharterConfigError:
        return None
    return target


def apply_resets(project_path: Path, actions: Sequence[ResetAction], *, dry_run: bool) -> CutoverReport:
    """Remove every ``RESET`` key (unless *dry_run*) and return the report fragment."""
    report = CutoverReport()
    by_file: dict[Path, list[str]] = {}
    for action in actions:
        getattr(report, action.outcome.value).append(action.line)
        if action.hint is not None:
            report.restore_hints.append(action.hint)
        if action.outcome is ResetOutcome.RESET:
            by_file.setdefault(action.path, []).append(action.key)
    if dry_run:
        return report
    from charter.activation.pack_context import ActiveCharterConfigError

    resolved_store = _resolved_store(project_path) if by_file else None
    for path, keys in by_file.items():
        try:
            _remove_keys(project_path, path, keys, resolved_store)
        except (OSError, ValueError, ActiveCharterConfigError) as exc:
            report.errors.append(f"{_rel(path, project_path)} could not be written ({exc}); {_REMEDY}")
    return report
