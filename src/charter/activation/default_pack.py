"""Shared loader for the shipped default charter pack's activation ID lists.

Two ``specify_cli`` consumers both need the real built-in ``activated_<kind>``
id sets from ``src/charter/activation/packs/default.yaml``, as the ``default_ids``
argument to :func:`charter.activation.activation_engine.promote_activations` (the WP06
absent-key LAND-BLOCKER safety: promoting into a previously-absent
``activated_<kind>`` config key must materialize every built-in id first,
never write a bare restrictive list):

- :func:`charter.activation.org_charter._promote_org_required_to_config`
  (org-required-artefact promotion)
- :class:`specify_cli.upgrade.migrations.m_unify_charter_activation.UnifyCharterActivationMigration`
  (answers-only-selection promotion)

Both landed in the same PR with independent, near-identical readers of the
same file (squad finding #2530). This module is the single canonical loader
both now import — the ``charter`` layer is the correct home because
``org_charter.py`` (specify_cli) and the migration (also specify_cli) are
peers with no dependency relationship to each other, and both are permitted
to import from ``charter`` (specify_cli sits above charter in the layer
chain: kernel <- doctrine <- charter <- glossary/runtime <- specify_cli).

A THIRD, distinct seam lives here too:
:func:`load_default_mission_type_activations`. It is the single fail-closed
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

from charter.activation.pack_context import CharterPackConfigError

__all__ = [
    "load_default_mission_type_activations",
    "load_default_pack_activation_ids",
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

    Shared by both :func:`load_default_pack_activation_ids` (fail-open — an
    empty mapping is a valid "nothing here" answer for its callers) and
    :func:`load_default_mission_type_activations` (fail-closed — an empty
    mapping there means "cannot provision", so it raises instead).
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


def load_default_pack_activation_ids(
    charter_pkg_root: Path | None = None,
) -> dict[str, list[str]]:
    """Load the shipped default-pack's ``activated_<kind>`` id lists.

    Reads ``<charter_pkg_root>/packs/default.yaml`` (defaults to
    ``src/charter/activation/packs/default.yaml``, the pack shipped with spec-kitty) and
    returns every top-level list-valued key verbatim — already in
    ``activated_<kind>`` form (``config.yaml``'s own key naming), so callers
    select only the keys they need via ``dict.get``.

    Returns ``{}`` when the file is absent, unreadable, empty, malformed
    YAML, or not a mapping — callers must treat an empty dict as "no real
    built-in default available" and must NOT silently synthesize one (see
    the WP06 absent-key LAND-BLOCKER note in
    :func:`charter.activation.activation_engine.promote_activations`).

    Args:
        charter_pkg_root: Optional override for the ``charter`` package root
            (primarily for tests exercising a synthetic pack directory).
            Defaults to this module's own directory.
    """
    raw = _load_raw_pack_mapping(_default_pack_yaml_path(charter_pkg_root))
    return {key: list(value) for key, value in raw.items() if isinstance(value, list)}


def load_default_mission_type_activations(pack_path: Path | None = None) -> list[str]:
    """Return the authored ``mission_type_activations`` list, failing closed.

    This is the single seed-READ both ``spec-kitty init``/``upgrade``
    (:func:`specify_cli.provisioning.default_charter.provision_default_mission_type_activations`)
    and ``spec-kitty charter generate``
    (:func:`charter.activation.compiler.provision_mission_type_activations`) now consume,
    so the two provisioners can never seed a divergent activation set from the
    same shipped ``default.yaml`` (squad-found maintainability defect: they
    previously read it through two independent stacks).

    Unlike :func:`load_default_pack_activation_ids` (fail-open, ``{}`` on any
    problem — several other callers rely on that), this helper is
    deliberately fail-closed: a missing file, unreadable/malformed YAML, a
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
        CharterPackConfigError: the resolved pack file does not declare a
            non-empty ``mission_type_activations`` list.
    """
    resolved_path = pack_path if pack_path is not None else _default_pack_yaml_path(None)
    raw = _load_raw_pack_mapping(resolved_path)
    activations = raw.get(_MISSION_TYPE_ACTIVATIONS_KEY)
    if not isinstance(activations, list) or not activations:
        raise CharterPackConfigError(
            f"{resolved_path} does not declare a non-empty "
            f"'{_MISSION_TYPE_ACTIVATIONS_KEY}' list. Cannot provision "
            "mission-type activations. This indicates a broken spec-kitty "
            "install — reinstall spec-kitty (or run `spec-kitty upgrade`) "
            "to restore the default charter pack."
        )
    return list(activations)
