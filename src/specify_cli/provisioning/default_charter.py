"""Fresh-init ``mission_type_activations`` provisioning (FR-003, FR-019).

The seed is the built-in pack's ``default`` preset (``presets/default.yaml``):
``spec-kitty init`` writes its mission types into the project's activation
authority, so skipping charter activation during ``init`` leaves the project
exactly as ``spec-kitty charter activate --preset default`` would.

**Seed-read and write are shared.** What the preset lists, or failing closed,
is answered by the compiler's ``default_preset_mission_types``, and the write goes through
:func:`charter.activation.compiler.provision_mission_type_activations`, the
same provisioner ``spec-kitty charter generate`` and the upgrade provisioning
use, so the provisioners can never seed divergent sets or targets.

The target is the one the activation ledger seam resolves: a fresh project
(no ledger, no legacy activation key) gets ``.kittify/charter/activation.yaml``;
an unmigrated project (legacy keys, no ledger) keeps its legacy target, so no
ledger is ever created beside legacy keys (hole 3).

Design constraints:

* **Copy, not re-scan.** The preset's list is copied verbatim; it is never
  re-derived by scanning the mission-type catalog.
* **No catalog intersection.** Provisioning never trims the copied (or
  already-present) list down to the built-in catalog, so a project's custom,
  non-built-in mission types always survive.
* **Additive-only.** The key is written only when it is entirely absent. An
  authored empty list (``mission_type_activations: []``) and any
  already-present list (built-in, custom, or a mix) are left untouched byte-
  for-byte, which makes re-provisioning idempotent and customization-safe.
"""

from __future__ import annotations

from pathlib import Path

from charter.activation.compiler import provision_mission_type_activations

__all__ = [
    "provision_default_mission_type_activations",
]


def provision_default_mission_type_activations(project_path: Path) -> bool:
    """Seed ``mission_type_activations`` into *project_path*'s activation authority.

    Copies the mission types of the built-in pack's ``default`` preset into
    the target the activation ledger seam resolves (the ledger for a fresh
    project, FR-019; the legacy surface for an unmigrated one), but only when
    the key is entirely absent: an authored empty list or any already-present
    list (custom entries included) is left untouched and nothing is rewritten.

    Args:
        project_path: Root of the project being initialized (``.kittify``'s
            parent).

    Returns:
        ``True`` if the key was written, ``False`` if provisioning was a no-op
        because the key was already present.

    Raises:
        DefaultPresetMissingError: the built-in ``default`` preset is absent,
            malformed or lists no mission types (fail closed, never an empty or
            implicit set). Raised before anything is written.
    """
    written: bool = provision_mission_type_activations(project_path)
    return written
