"""Fail-closed default-charter provisioning for fresh-init projects.

``spec-kitty init`` seeds a brand-new project's ``.kittify/config.yaml`` with
an explicit, non-empty ``mission_type_activations`` list **copied** from the
built-in pack's ``default`` preset (never re-derived by scanning the
mission-type catalog), and fails closed with ``DEFAULT_PRESET_MISSING``
(:class:`charter.activation.compiler.DefaultPresetMissingError`) when that
preset cannot seed it.
"""

from __future__ import annotations

from specify_cli.provisioning.default_charter import provision_default_mission_type_activations

__all__ = [
    "provision_default_mission_type_activations",
]
