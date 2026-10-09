"""Fail-closed loader for the shipped default pack's ``mission_type_activations``.

The per-kind ``activated_<kind>`` lists of ``default.yaml`` are no longer read
here: what an absent key means is answered by the one public effective-set seam,
:mod:`charter.activation.effective_set` (FR-015, #4400), never by a shipped id
list. What remains is the mission-type provisioning seed below, until WP09
replaces it with the ``default`` preset and removes this module.

The remaining seam, :func:`load_default_mission_type_activations`, is the single fail-closed
seed-READ for ``mission_type_activations`` consumed by both
``specify_cli.provisioning.default_charter.provision_default_mission_type_activations``
(``spec-kitty init``/``upgrade``) and
``charter.activation.compiler.provision_mission_type_activations`` (``spec-kitty charter
generate``). Those two functions previously read the same shipped
``default.yaml`` through independent stacks with divergent fail-closed
behaviour (one silently accepted an authored-empty list, the other did not) —
this function is the one place that decides what "the authored
``mission_type_activations`` list, or fail closed" means; the two callers
keep their own write targets and their own historically-typed exceptions
(see each call site for why).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

from charter.activation.pack_context import ActiveCharterConfigError

__all__ = [
    "load_default_mission_type_activations",
]

#: The single ``mission_type_activations`` key name, shared by both
#: provisioner call sites and the pack YAML itself.
_MISSION_TYPE_ACTIVATIONS_KEY = "mission_type_activations"


def _default_pack_yaml_path(charter_pkg_root: Path | None) -> Path:
    """Resolve the ``packs/default.yaml`` path under *charter_pkg_root*.

    Defaults to this module's own package directory (``src/charter``) —
    i.e. the shipped built-in pack — when *charter_pkg_root* is omitted.
    """
    root = charter_pkg_root if charter_pkg_root is not None else Path(__file__).resolve().parent
    return root / "packs" / "default.yaml"


def _load_raw_pack_mapping(pack_path: Path) -> dict[str, Any]:
    """Load *pack_path* as a YAML mapping, degrading to ``{}`` on any failure.

    :func:`load_default_mission_type_activations` treats an empty mapping as
    "cannot provision" and raises (fail closed).
    """
    if not pack_path.exists():
        return {}
    yaml = YAML(typ="safe")
    try:
        raw: Any = yaml.load(pack_path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        # Malformed YAML degrades to empty; the caller decides how to react.
        return {}
    if not isinstance(raw, dict):
        return {}
    return raw


def load_default_mission_type_activations(pack_path: Path | None = None) -> list[str]:
    """Return the authored ``mission_type_activations`` list, failing closed.

    This is the single seed-READ both ``spec-kitty init``/``upgrade``
    (:func:`specify_cli.provisioning.default_charter.provision_default_mission_type_activations`)
    and ``spec-kitty charter generate``
    (:func:`charter.activation.compiler.provision_mission_type_activations`) now consume,
    so the two provisioners can never seed a divergent activation set from the
    same shipped ``default.yaml`` (squad-found maintainability defect: they
    previously read it through two independent stacks).

    This helper is deliberately fail-closed: a missing file, unreadable/malformed YAML, a
    non-list value, or an authored-but-empty list all raise. An authored
    empty ``mission_type_activations: []`` in the *shipped* default pack is
    itself a broken-install signal, not a legitimate "no mission types" pack
    (that distinction only applies to a *project's* own ``config.yaml`` /
    ``charter.yaml``, which is a completely different write target handled
    by each caller).

    Args:
        pack_path: Explicit override for the default pack's YAML file
            (primarily for callers that already resolved/validated a path —
            e.g. ``specify_cli``'s ``resolve_builtin_pack_path`` seam — and
            for tests exercising a synthetic pack file). Defaults to the
            shipped ``src/charter/activation/packs/default.yaml``.

    Raises:
        ActiveCharterConfigError: the resolved pack file does not declare a
            non-empty ``mission_type_activations`` list.
    """
    resolved_path = pack_path if pack_path is not None else _default_pack_yaml_path(None)
    raw = _load_raw_pack_mapping(resolved_path)
    activations = raw.get(_MISSION_TYPE_ACTIVATIONS_KEY)
    if not isinstance(activations, list) or not activations:
        raise ActiveCharterConfigError(
            f"{resolved_path} does not declare a non-empty "
            f"'{_MISSION_TYPE_ACTIVATIONS_KEY}' list. Cannot provision "
            "mission-type activations. This indicates a broken spec-kitty "
            "install — reinstall spec-kitty (or run `spec-kitty upgrade`) "
            "to restore the default charter pack."
        )
    return list(activations)
