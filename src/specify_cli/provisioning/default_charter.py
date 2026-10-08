"""Fresh-init ``mission_type_activations`` provisioning (FR-003).

The seed is the built-in pack's ``default`` preset (``presets/default.yaml``):
``spec-kitty init`` writes its mission types into a brand-new project's
``.kittify/config.yaml``, so skipping charter activation during ``init`` leaves
the project exactly as ``spec-kitty charter activate --preset default`` would.

**Seed-read is shared, write is not.** What the preset lists, or failing
closed, is answered by
:func:`charter.activation.compiler.default_preset_mission_types`, the same
reader ``spec-kitty charter generate`` and the upgrade provisioning use, so the
provisioners can never seed divergent sets. This module owns only its write
target, ``config.yaml``.

Design constraints:

* **Copy, not re-scan.** The preset's list is copied verbatim; it is never
  re-derived by scanning the mission-type catalog.
* **No catalog intersection.** Provisioning never trims the copied (or
  already-present) list down to the built-in catalog, so a project's custom,
  non-built-in mission types always survive.
* **Additive-only.** :func:`provision_default_mission_type_activations` only
  ever *writes* the key when it is entirely absent from ``config.yaml``. An
  authored empty list (``mission_type_activations: []``) and any
  already-present list (built-in, custom, or a mix) are left untouched byte-
  for-byte, which makes re-provisioning idempotent and customization-safe.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

from charter.activation.compiler import default_preset_mission_types

__all__ = [
    "provision_default_mission_type_activations",
]

#: The single ``config.yaml`` key this module provisions; the other activation
#: keys a preset can govern are not written by ``init``.
_MISSION_TYPE_ACTIVATIONS_KEY = "mission_type_activations"


def provision_default_mission_type_activations(project_path: Path) -> bool:
    """Seed ``.kittify/config.yaml``'s ``mission_type_activations`` for a fresh project.

    Copies the mission types of the built-in pack's ``default`` preset into
    ``project_path/.kittify/config.yaml``, but only when the key is entirely
    absent: an authored empty list or any already-present list (custom entries
    included) is left untouched, and ``config.yaml`` is not rewritten at all.

    Args:
        project_path: Root of the project being initialized (``.kittify``'s
            parent). Created if it does not already exist.

    Returns:
        ``True`` if ``config.yaml`` was created or modified, ``False`` if
        provisioning was a no-op because the key was already present.

    Raises:
        DefaultPresetMissingError: the built-in ``default`` preset is absent,
            malformed or lists no mission types (fail closed, never an empty or
            implicit set). Raised before ``config.yaml`` is read or written.
    """
    mission_types = default_preset_mission_types()

    kittify_dir = project_path / ".kittify"
    config_file = kittify_dir / "config.yaml"

    yaml = YAML()
    yaml.preserve_quotes = True

    raw_config: Any = None
    if config_file.exists():
        with config_file.open("r", encoding="utf-8") as fh:
            raw_config = yaml.load(fh)
    config_data: dict[str, Any] = raw_config if isinstance(raw_config, dict) else {}

    if _MISSION_TYPE_ACTIVATIONS_KEY in config_data:
        return False
    config_data[_MISSION_TYPE_ACTIVATIONS_KEY] = mission_types

    kittify_dir.mkdir(parents=True, exist_ok=True)
    with config_file.open("w", encoding="utf-8") as fh:
        yaml.dump(config_data, fh)
    return True
