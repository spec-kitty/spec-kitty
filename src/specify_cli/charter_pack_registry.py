"""Built-in charter pack registry + shared pack -> ``config.yaml`` merge logic.

A *charter pack* is a small YAML document shaped like
``src/charter/activation/packs/default.yaml``: ``activated_kinds``,
``mission_type_activations``, and the per-kind ``activated_<plural>`` lists.
Spec Kitty ships two built-in packs side by side in
``src/charter/activation/packs/``:

* ``default`` — activates every built-in artifact across every kind.
* ``minimal`` — a small, curated starting baseline (relocated from the
  doctrine-asset tier to first-class pack status, #3064 follow-up).

This module is the single place that knows:

1. Which built-in packs exist and where they live on disk
   (:data:`BUILTIN_PACKS`, :func:`resolve_builtin_pack_path`).
2. How to merge a loaded pack's activation keys into an in-memory
   ``config.yaml`` document (:func:`merge_pack_into_config`).

Both ``spec-kitty charter pack {list,path,apply}``
(``specify_cli.cli.commands.charter.pack``) and the
``3.2.0rc35_default_charter_pack`` upgrade migration
(``specify_cli.upgrade.migrations.m_3_2_0rc35_default_charter_pack``) import
from here so the pack -> config merge logic is written exactly once.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

from charter.activation.pack_manager import YAML_KEY_MAP

__all__ = [
    "BUILTIN_PACKS",
    "UnknownPackError",
    "resolve_builtin_pack_path",
    "load_pack_yaml",
    "merge_pack_into_config",
]

#: ``YAML_KEY_MAP`` values deliberately NOT carried into
#: :data:`PER_KIND_ACTIVATION_KEYS`:
#:
#: * ``mission_type_activations`` -- the ``mission-type`` charter-kind token
#:   is the documented outlier (``charter.activation.pack_manager._yaml_key_for_token``):
#:   it does not follow the ``activated_<plural>`` pattern, and
#:   :data:`ACTIVATION_KEYS` below already lists it separately.
#: * ``activated_glossary_packs`` -- glossary-pack activation is intentionally
#:   NOT declared by either built-in charter pack (``src/charter/packs/
#:   default.yaml`` / ``minimal.yaml``). Its three-state absence (unset /
#:   empty / populated) is owned by the later
#:   ``m_3_2_x_normalize_activation_absence`` migration; folding it into the
#:   packs' per-kind keys here would fight that migration's contract instead
#:   of composing with it. Mirrors the special-case comment style in
#:   ``charter.activation.charter_yaml_io._ACTIVATION_KEYS``.
#: * ``activated_skills`` -- pack-skill activation is opt-in
#:   (``ArtifactKind.effective_when_absent == "required"``, ADR
#:   2026-09-27-1): an ABSENT key puts only the org-required skills in
#:   force, so a built-in charter pack must never write the key (it would
#:   flip default-in-force to an explicit set).
_NON_PACK_ACTIVATION_KEYS: frozenset[str] = frozenset(
    {"mission_type_activations", "activated_glossary_packs", "activated_skills"}
)

#: The per-kind activation keys a charter pack may populate. DERIVED from
#: ``charter.activation.pack_manager.YAML_KEY_MAP`` (the canonical charter-kind ->
#: ``config.yaml``-key table, itself derived from
#: ``charter.offering.artifact_kinds.CHARTER_KIND_TOKENS``) rather than hand-maintained,
#: so a newly added charter kind is picked up here automatically instead of
#: silently drifting from the registry. See :data:`_NON_PACK_ACTIVATION_KEYS`
#: for what is deliberately excluded and why; today's result is byte-identical
#: to the previous hand-written eight-key tuple (guarded by
#: ``tests/specify_cli/test_charter_pack_registry.py``).
PER_KIND_ACTIVATION_KEYS: tuple[str, ...] = tuple(
    key for key in YAML_KEY_MAP.values() if key not in _NON_PACK_ACTIVATION_KEYS
)

#: The full set of ``config.yaml`` keys a charter pack may populate.
ACTIVATION_KEYS: tuple[str, ...] = (
    *PER_KIND_ACTIVATION_KEYS,
    "activated_kinds",
    "mission_type_activations",
)

#: Directory that ships the built-in charter packs, relative to this file:
#: specify_cli/ -> src/ -> charter/activation/packs/. Two ``.parent`` hops.
#: ``packs/`` relocated under ``charter/activation/`` by mission
#: charter-activation-split-01M16ZSE (MAP-A MOVE).
_PACKS_DIR: Path = Path(__file__).parent.parent / "charter" / "activation" / "packs"

#: Shipped built-in pack names, mapped to a one-line operator-facing
#: description. Both packs live at ``src/charter/activation/packs/<name>.yaml``.
BUILTIN_PACKS: dict[str, str] = {
    "default": "Activates every built-in artifact across every charter kind.",
    "minimal": (
        "A small, curated starting baseline: 5 directives, 2 tactics, "
        "the software-dev mission type."
    ),
}


class UnknownPackError(ValueError):
    """Raised when a pack name is not in :data:`BUILTIN_PACKS`."""

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(
            f"Unknown built-in charter pack '{name}'. "
            f"Valid packs: {', '.join(sorted(BUILTIN_PACKS))}"
        )


def resolve_builtin_pack_path(name: str) -> Path:
    """Resolve a built-in pack *name* to its shipped filesystem path.

    Fail-closed in two ways so ``list``/``path``/``apply`` never hand back a
    nonexistent path:

    * raises :class:`UnknownPackError` for any name outside
      :data:`BUILTIN_PACKS`, naming the offending value and the valid set;
    * raises :class:`FileNotFoundError` if *name* is a registered built-in
      pack but its shipped YAML file is missing (a broken install or a
      :data:`BUILTIN_PACKS` entry added without its file) — never a silent
      fallback to a path that does not resolve.
    """
    if name not in BUILTIN_PACKS:
        raise UnknownPackError(name)
    path = _PACKS_DIR / f"{name}.yaml"
    if not path.exists():
        raise FileNotFoundError(
            f"Built-in charter pack '{name}' is registered but its shipped "
            f"file is missing at {path}. This indicates a broken spec-kitty "
            "install."
        )
    return path


def load_pack_yaml(path: Path) -> dict[str, Any]:
    """Load a charter pack YAML file's activation keys (values only, safe mode)."""
    yaml = YAML(typ="safe")
    data = yaml.load(path) or {}
    if not isinstance(data, dict):
        return {}
    return dict(data)


def merge_pack_into_config(
    config_data: dict[str, Any],
    pack_data: dict[str, Any],
    *,
    force: bool = False,
) -> tuple[list[str], list[str]]:
    """Merge *pack_data*'s activation keys into *config_data* in place.

    Only keys in :data:`ACTIVATION_KEYS` are considered. By default (``force``
    is ``False``) a key already present in ``config_data`` is left untouched
    — this is the additive, non-clobbering merge (User Customization
    Preservation): a project's existing activations are never silently
    overwritten. Passing ``force=True`` overwrites every key the pack
    declares, regardless of what is already present.

    Returns
    -------
    tuple[list[str], list[str]]
        ``(keys_written, keys_skipped)`` — ``keys_skipped`` lists keys the
        pack declares that were left alone because they already existed and
        ``force`` was not set.
    """
    keys_written: list[str] = []
    keys_skipped: list[str] = []
    for key in ACTIVATION_KEYS:
        if key not in pack_data:
            continue
        if key in config_data and not force:
            keys_skipped.append(key)
            continue
        config_data[key] = list(pack_data[key])
        keys_written.append(key)
    return keys_written, keys_skipped
