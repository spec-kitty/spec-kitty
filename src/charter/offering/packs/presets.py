"""Activation presets: the format, the loader, discovery and manifest hashing.

An **activation preset** is pack data (FR-019): a named file
``<pack>/presets/<name>.yaml`` holding activation keys that ``charter activate
--preset <name>`` applies with replace semantics (WP08). It is not an
:class:`~charter.offering.artifact_kinds.ArtifactKind`, has no URN, and is
hashed by the pack manifest (:func:`enumerate_presets`).

A preset file carries ``name`` (equal to the file stem), ``description``, any
of the per-kind ``activated_<plural>`` keys of the governed kinds,
``activated_kinds`` and ``mission_type_activations``. A key that is absent
leaves its kind unrestricted; an empty list activates nothing of that kind.
The documented contract is ``charter/offering/schemas/activation-preset.schema.yaml``;
its kind enums are pinned to the sets derived here by a test.

The kinds a preset governs are **derived** from ``ArtifactKind`` (never
hand-listed): every charter-activatable kind except ``skill`` and
``glossary_pack``, each of which has its own absence contract. Mission types
have their own key.

This module lives in the offering tier and must not import
``charter.activation`` (``test_charter_offering_does_not_import_activation``).
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict
from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from charter.offering.artifact_kinds import ArtifactKind
from charter.offering.drg.org_pack_config import load_pack_registry
from charter.offering.pack_paths import built_in_root
from charter.offering.packs.hashing import hash_content_bytes
from kernel.charter_pack_paths import pack_presets_dir, project_pack_root

__all__ = [
    "ACTIVATED_KINDS_KEY",
    "DEFAULT_PRESET_NAME",
    "MISSION_TYPE_ACTIVATIONS_KEY",
    "ActivationPreset",
    "OfferingPack",
    "PresetEntry",
    "PresetFormatError",
    "PresetNotFoundError",
    "discover_presets",
    "enumerate_presets",
    "kind_gate_omissions",
    "list_offering_packs",
    "load_preset",
    "load_preset_file",
    "preset_activation_key",
    "preset_activation_keys",
    "preset_files",
    "render_example_preset",
    "write_example_preset",
]

#: The built-in pack's preset that seeds ``mission_type_activations`` and that
#: ``charter activate --preset`` compares a customised list against (FR-003).
DEFAULT_PRESET_NAME = "default"

#: Kinds whose activation key a preset may not carry: each has its own absence
#: contract (``skill`` is ``effective_when_absent == "required"``; glossary packs
#: are governed by their own key), so a preset never writes or clears them.
_OWN_ABSENCE_CONTRACT_KINDS: frozenset[ArtifactKind] = frozenset({ArtifactKind.SKILL, ArtifactKind.GLOSSARY_PACK})

#: The kinds a preset governs with a per-kind ``activated_<plural>`` key, in
#: ``ArtifactKind`` declaration order.
_GOVERNED_KINDS: tuple[ArtifactKind, ...] = tuple(kind for kind in ArtifactKind if kind.activatable and kind not in _OWN_ABSENCE_CONTRACT_KINDS)

#: Every value ``activated_kinds`` may hold: the plural of every ``ArtifactKind``
#: (the universe the kind gate is read over).
_KIND_GATE_PLURALS: tuple[str, ...] = tuple(kind.plural for kind in ArtifactKind)

_ACTIVATED_PREFIX = "activated_"
_NAME_KEY = "name"
_DESCRIPTION_KEY = "description"
#: The kind-gate key.
ACTIVATED_KINDS_KEY = "activated_kinds"
#: The mission-type key.
MISSION_TYPE_ACTIVATIONS_KEY = "mission_type_activations"
#: The org-charter key for context-scoped activation entries; a preset has none.
_CONTEXT_SCOPED_KEY = "activations"

#: Grammar of a preset name (and therefore of its file stem).
_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$")
#: Longest preset name accepted.
_NAME_MAX_LENGTH = 64

#: The ``name`` of the built-in pack (``packs/built-in/pack.yaml``).
_BUILT_IN_PACK_NAME = "built-in"

#: The preset ``charter org init`` scaffolds into a new org pack.
_EXAMPLE_PRESET_NAME = "starter"

_PRESET_GLOB = "*.yaml"


def preset_activation_key(kind: ArtifactKind) -> str:
    """Return the ``activated_<plural>`` key of *kind*."""
    return f"{_ACTIVATED_PREFIX}{kind.plural}"


def preset_activation_keys() -> tuple[str, ...]:
    """Return the per-kind activation keys a preset may carry (derived)."""
    return tuple(preset_activation_key(kind) for kind in _GOVERNED_KINDS)


def _ungoverned_activation_keys() -> frozenset[str]:
    return frozenset(preset_activation_key(kind) for kind in _OWN_ABSENCE_CONTRACT_KINDS)


def _allowed_keys() -> frozenset[str]:
    return frozenset({_NAME_KEY, _DESCRIPTION_KEY, ACTIVATED_KINDS_KEY, MISSION_TYPE_ACTIVATIONS_KEY, *preset_activation_keys()})


# ---------------------------------------------------------------------------
# Model and errors
# ---------------------------------------------------------------------------


class PresetFormatError(ValueError):
    """A preset file is malformed; the message names the file and the field."""

    def __init__(self, path: Path, field: str, detail: str) -> None:
        self.path = path
        self.field = field
        self.detail = detail
        super().__init__(f"{path.name}: {field}: {detail}")


class PresetNotFoundError(LookupError):
    """No preset of that name exists in the pack; carries the available names."""

    def __init__(self, name: str, pack_root: Path, available: tuple[str, ...]) -> None:
        self.name = name
        self.pack_root = pack_root
        self.available = available
        listing = ", ".join(available) if available else "none"
        super().__init__(f"preset {name!r} not found in {pack_root} (available: {listing})")


@dataclass(frozen=True)
class ActivationPreset:
    """One loaded preset.

    ``activations`` holds only the per-kind keys present in the file (absent
    means unrestricted; an empty tuple means none). ``activated_kinds`` and
    ``mission_type_activations`` are ``None`` when the file does not carry them.
    """

    name: str
    description: str
    activations: Mapping[str, tuple[str, ...]]
    activated_kinds: tuple[str, ...] | None
    mission_type_activations: tuple[str, ...] | None
    source: Path

    def listed_kinds(self) -> tuple[ArtifactKind, ...]:
        """Return the kinds the preset lists ids for (a key is present)."""
        return tuple(kind for kind in _GOVERNED_KINDS if preset_activation_key(kind) in self.activations)


def kind_gate_omissions(preset: ActivationPreset) -> tuple[str, ...]:
    """Return the plurals the preset lists ids for but leaves out of ``activated_kinds``.

    Empty when the preset carries no kind gate. A non-empty result means the
    preset would switch off a kind it activates ids for (FR-002).
    """
    if preset.activated_kinds is None:
        return ()
    gate = set(preset.activated_kinds)
    return tuple(kind.plural for kind in preset.listed_kinds() if kind.plural not in gate)


# ---------------------------------------------------------------------------
# Strict loader
# ---------------------------------------------------------------------------


def _read_mapping(path: Path) -> dict[str, Any]:
    try:
        data = YAML(typ="safe").load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError) as exc:
        raise PresetFormatError(path, "<file>", f"cannot be read: {exc}") from exc
    except YAMLError as exc:
        raise PresetFormatError(path, "<file>", f"YAML parse error: {exc}") from exc
    if not isinstance(data, dict):
        raise PresetFormatError(path, "<file>", "expected a YAML mapping at top level")
    return data


def _check_keys(path: Path, data: Mapping[str, Any]) -> None:
    unknown = sorted(str(key) for key in data if key not in _allowed_keys())
    if not unknown:
        return
    if _CONTEXT_SCOPED_KEY in unknown:
        raise PresetFormatError(path, _CONTEXT_SCOPED_KEY, "a preset carries no context-scoped activation entries")
    ungoverned = [key for key in unknown if key in _ungoverned_activation_keys()]
    if ungoverned:
        raise PresetFormatError(path, ungoverned[0], "presets do not govern this kind; it keeps its own activation contract")
    raise PresetFormatError(path, unknown[0], f"unknown key(s): {', '.join(unknown)}")


def _check_name(path: Path, value: Any) -> str:
    if not isinstance(value, str):
        raise PresetFormatError(path, _NAME_KEY, "must be a string")
    if len(value) > _NAME_MAX_LENGTH:
        raise PresetFormatError(path, _NAME_KEY, f"is longer than {_NAME_MAX_LENGTH} characters")
    if not _NAME_PATTERN.match(value):
        raise PresetFormatError(path, _NAME_KEY, f"{value!r} does not match {_NAME_PATTERN.pattern}")
    if value != path.stem:
        raise PresetFormatError(path, _NAME_KEY, f"{value!r} must equal the file stem {path.stem!r}")
    return value


def _check_description(path: Path, value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PresetFormatError(path, _DESCRIPTION_KEY, "must be a non-empty string")
    return value


def _check_id_list(path: Path, key: str, value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise PresetFormatError(path, key, "must be a list of strings")
    ids: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise PresetFormatError(path, key, f"entry {item!r} is not a non-empty string")
        if item in ids:
            raise PresetFormatError(path, key, f"duplicate entry {item!r}")
        ids.append(item)
    return tuple(ids)


def _check_kind_gate(path: Path, value: Any) -> tuple[str, ...]:
    plurals = _check_id_list(path, ACTIVATED_KINDS_KEY, value)
    unknown = [plural for plural in plurals if plural not in _KIND_GATE_PLURALS]
    if unknown:
        raise PresetFormatError(path, ACTIVATED_KINDS_KEY, f"unknown kind(s): {', '.join(unknown)}")
    return plurals


def load_preset_file(path: Path) -> ActivationPreset:
    """Load and strictly validate one preset file.

    Raises :class:`PresetFormatError` naming the offending field for an
    unreadable file, an unknown key (``activated_skills`` and
    ``activated_glossary_packs`` with their own message), a context-scoped
    ``activations:`` list, a ``name`` that breaks the grammar or differs from
    the file stem, and a list value that is not unique non-empty strings.
    """
    data = _read_mapping(path)
    _check_keys(path, data)
    if _NAME_KEY not in data:
        raise PresetFormatError(path, _NAME_KEY, "is required")
    if _DESCRIPTION_KEY not in data:
        raise PresetFormatError(path, _DESCRIPTION_KEY, "is required")
    name = _check_name(path, data[_NAME_KEY])
    description = _check_description(path, data[_DESCRIPTION_KEY])
    activations = {key: _check_id_list(path, key, data[key]) for key in preset_activation_keys() if key in data}
    kind_gate = _check_kind_gate(path, data[ACTIVATED_KINDS_KEY]) if ACTIVATED_KINDS_KEY in data else None
    mission_types = _check_id_list(path, MISSION_TYPE_ACTIVATIONS_KEY, data[MISSION_TYPE_ACTIVATIONS_KEY]) if MISSION_TYPE_ACTIVATIONS_KEY in data else None
    return ActivationPreset(
        name=name,
        description=description,
        activations=activations,
        activated_kinds=kind_gate,
        mission_type_activations=mission_types,
        source=path,
    )


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------


def preset_files(pack_root: Path) -> tuple[Path, ...]:
    """Return the preset files of the pack at *pack_root*, sorted by name.

    A pack without a ``presets/`` directory has none (a pack without presets
    works).
    """
    presets_dir = pack_presets_dir(pack_root)
    if not presets_dir.is_dir():
        return ()
    return tuple(sorted((path for path in presets_dir.glob(_PRESET_GLOB) if path.is_file()), key=lambda path: path.stem))


def discover_presets(pack_root: Path) -> tuple[ActivationPreset, ...]:
    """Load every preset of the pack at *pack_root*, sorted by name.

    Raises :class:`PresetFormatError` on the first malformed file; use
    ``validate_pack`` to collect every finding.
    """
    return tuple(load_preset_file(path) for path in preset_files(pack_root))


def load_preset(pack_root: Path, name: str) -> ActivationPreset:
    """Load the preset *name* of the pack at *pack_root*.

    Raises :class:`PresetNotFoundError` (carrying the available names) when the
    pack has no such preset, including for a name outside the preset grammar.
    """
    files = preset_files(pack_root)
    for path in files:
        if path.stem == name and _NAME_PATTERN.match(name):
            return load_preset_file(path)
    raise PresetNotFoundError(name, pack_root, tuple(path.stem for path in files))


# ---------------------------------------------------------------------------
# Offering packs of a project (FR-004)
# ---------------------------------------------------------------------------

PackTier = Literal["built-in", "org", "project"]


@dataclass(frozen=True)
class OfferingPack:
    """One pack in a project's offering, in layer order.

    The ``project`` tier ships no presets (spec Key Entities): callers never
    consult :func:`discover_presets` for it (:attr:`ships_presets` is false).
    """

    name: str
    tier: PackTier
    root: Path

    @property
    def ships_presets(self) -> bool:
        """Whether presets are read from this pack (every tier but ``project``)."""
        return self.tier != "project"


def list_offering_packs(repo_root: Path) -> tuple[OfferingPack, ...]:
    """Return the packs of the project at *repo_root*: built-in, org packs, project.

    Org packs come from the project's pack registry in declaration order; a
    pack fetched with ``spec-kitty charter fetch`` is an org pack whose root is
    populated. An unfetched root is still listed, and
    :func:`discover_presets` returns ``()`` for it. No artifact id is resolved
    here.
    """
    packs: list[OfferingPack] = [OfferingPack(_BUILT_IN_PACK_NAME, "built-in", built_in_root())]
    registry = load_pack_registry(repo_root, quiet=True)
    packs.extend(OfferingPack(entry.name, "org", entry.effective_root(repo_root)) for entry in registry.packs)
    packs.append(OfferingPack("project", "project", project_pack_root(repo_root)))
    return tuple(packs)


# ---------------------------------------------------------------------------
# Manifest hashing
# ---------------------------------------------------------------------------


class PresetEntry(BaseModel):
    """One preset recorded in a pack manifest (``presets:``)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    path: str
    """Pack-relative POSIX path of the preset file."""
    content_hash: str
    """SHA-256 over the LF-normalised file bytes."""


def _lf_normalised(raw: bytes) -> bytes:
    return raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def enumerate_presets(pack_root: Path) -> list[PresetEntry]:
    """Return a manifest entry per preset file of *pack_root*, sorted by name.

    Hashes the bytes as shipped (LF-normalised) and does not validate them;
    ``validate_pack`` owns validation.
    """
    return [
        PresetEntry(
            name=path.stem,
            path=path.relative_to(pack_root).as_posix(),
            content_hash=hash_content_bytes(_lf_normalised(path.read_bytes())),
        )
        for path in preset_files(pack_root)
    ]


# ---------------------------------------------------------------------------
# Scaffold
# ---------------------------------------------------------------------------

_EXAMPLE_PRESET = f"""\
# Example activation preset, scaffolded by `spec-kitty charter org init`.
# Apply it with: spec-kitty charter activate --preset {_EXAMPLE_PRESET_NAME}
#
# A preset replaces the activation keys it carries. A key left out keeps its
# kind unrestricted (every artifact effective); an empty list activates none.
# To curate a kind, add its key, for example:
#
#   activated_directives:
#     - 010-specification-fidelity-requirement
#   activated_tactics:
#     - acceptance-test-first
name: {_EXAMPLE_PRESET_NAME}
description: Starter preset for this pack; activates the software-dev mission type.
mission_type_activations:
  - software-dev
"""


def render_example_preset() -> str:
    """Return the example preset ``charter org init`` writes (lists no artifact ids)."""
    return _EXAMPLE_PRESET


def write_example_preset(pack_root: Path) -> Path:
    """Write the example preset into the pack at *pack_root*; return its path."""
    path = pack_presets_dir(pack_root) / f"{_EXAMPLE_PRESET_NAME}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_example_preset(), encoding="utf-8")
    return path
