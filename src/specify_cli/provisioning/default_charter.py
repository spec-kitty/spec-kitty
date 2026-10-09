"""Fresh-init ``mission_type_activations`` provisioning (FR-009/010/011).

The provisioned surface is ``src/charter/activation/packs/default.yaml`` — the same
shipped file the ``3.2.0rc35_default_charter_pack`` upgrade migration reads
(``specify_cli.upgrade.migrations.m_3_2_0rc35_default_charter_pack``).  This
module is the *fresh-init* counterpart: it seeds a brand-new project's
``.kittify/config.yaml`` the first time ``spec-kitty init`` runs, so removing
the config-absent implicit backfill (mission WP04, out of scope here) does
not leave new projects with zero mission types.

**Seed-read is shared, write is not.** The actual "what is the authored
``mission_type_activations`` list, or fail closed" question is answered by
:func:`charter.activation.default_pack.load_default_mission_type_activations` — the
same helper ``charter.activation.compiler.provision_mission_type_activations`` (the
``spec-kitty charter generate`` path) consumes, so the two provisioners can
never seed a divergent set from the same shipped ``default.yaml``. This
module still owns its own path resolution
(:func:`specify_cli.charter_pack_registry.resolve_builtin_pack_path`) and
its own write target (``merge_pack_into_config`` into ``config.yaml``) —
only the parse-and-validate step is shared.

Design constraints (data-model Seam 2, invariants I-8/I-9/I-10; research
D-07):

* **Copy, not re-scan.** The authored ``mission_type_activations`` list is
  copied verbatim from ``default.yaml``. It is never re-derived via
  ``charter.offering.missions.mission_type_repository.builtin_mission_type_id_set()``
  (the disk-scanned, ``SPEC_KITTY_PACKS_ROOT``-sensitive built-in-type
  roster) — that would make this seam depend on the pack-root resolver at
  runtime, defeating the "disjoint halves" property the mission establishes.
* **No catalog intersection.** Provisioning never trims the copied (or
  already-present) list down to the built-in catalog, so a project's custom,
  non-built-in mission types always survive.
* **Additive-only.** :func:`provision_default_mission_type_activations` only
  ever *writes* the key when it is entirely absent from ``config.yaml``. An
  authored empty list (``mission_type_activations: []``) and any
  already-present list (built-in, custom, or a mix) are left untouched byte-
  for-byte — this is what makes re-provisioning idempotent (NFR-004) and
  customization-safe in the same step: there is nothing to "merge" once a
  key exists, so whatever the project already declared is never disturbed.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

from charter.activation.default_pack import load_default_mission_type_activations
from charter.activation.pack_context import ActiveCharterConfigError
from specify_cli.charter_pack_registry import (
    merge_pack_into_config,
    resolve_builtin_pack_path,
)

__all__ = [
    "DefaultCharterPackMissingError",
    "provision_default_mission_type_activations",
]

#: The single ``config.yaml`` key this module provisions. A charter pack
#: (``src/charter/packs/*.yaml``) may declare other activation keys too
#: (``activated_directives``, ``activated_kinds``, ...) but this seam is
#: scoped to mission-type activation only (T015) — those other keys are a
#: different contract, untouched here.
_MISSION_TYPE_ACTIVATIONS_KEY = "mission_type_activations"

#: Name of the built-in charter pack fresh-init provisioning copies from.
#: Resolved through :func:`specify_cli.charter_pack_registry.resolve_builtin_pack_path`
#: rather than a locally hand-rolled path, so this module and the rc35
#: migration + ``spec-kitty charter pack`` CLI never drift on where
#: ``default.yaml`` lives.
_DEFAULT_PACK_NAME = "default"


class DefaultCharterPackMissingError(RuntimeError):
    """Raised when the shipped default charter pack cannot be provisioned.

    Fresh-init provisioning (FR-011) fails closed rather than writing an
    implicit or empty ``mission_type_activations`` set when
    ``src/charter/activation/packs/default.yaml`` is missing or does not declare the
    key — a broken spec-kitty install, never a legitimate project state.
    """


def _load_default_pack_activations() -> list[Any]:
    """Return the authored ``mission_type_activations`` list from default.yaml.

    Path resolution stays local (``resolve_builtin_pack_path``, the same
    seam ``spec-kitty charter pack`` and the rc35 migration use); the actual
    parse-and-validate step delegates to the shared, fail-closed
    :func:`charter.activation.default_pack.load_default_mission_type_activations` so
    this provisioner and ``charter.activation.compiler.provision_mission_type_activations``
    (the ``spec-kitty charter generate`` path) can never read a divergent
    activation set from the same shipped file (squad-found maintainability
    defect: the two used to be independent, near-identical readers).

    Raises:
        DefaultCharterPackMissingError: the shipped default pack is missing
            (broken install) or does not declare a non-empty
            ``mission_type_activations`` list. Kept as this module's own
            historical exception type (rather than the shared helper's
            ``ActiveCharterConfigError``) so existing ``specify_cli`` callers
            and tests are undisturbed.
    """
    try:
        default_pack_path = resolve_builtin_pack_path(_DEFAULT_PACK_NAME)
    except FileNotFoundError as exc:
        raise DefaultCharterPackMissingError(
            "spec-kitty could not find its shipped default charter pack "
            f"({exc}). Cannot provision this project's mission types. "
            "This indicates a broken spec-kitty install — reinstall "
            "spec-kitty and re-run `spec-kitty init`."
        ) from exc

    try:
        return load_default_mission_type_activations(pack_path=default_pack_path)
    except ActiveCharterConfigError as exc:
        raise DefaultCharterPackMissingError(
            f"{default_pack_path} does not declare a non-empty "
            f"'{_MISSION_TYPE_ACTIVATIONS_KEY}' list. Cannot provision this "
            "project's mission types. This indicates a broken spec-kitty "
            "install — reinstall spec-kitty and re-run `spec-kitty init`."
        ) from exc


def provision_default_mission_type_activations(project_path: Path) -> bool:
    """Seed ``.kittify/config.yaml``'s ``mission_type_activations`` for a fresh project.

    Copies the authored ``mission_type_activations`` list from the shipped
    ``src/charter/activation/packs/default.yaml`` into ``project_path/.kittify/config.yaml``
    (C-A3), but only when the key is entirely absent — an authored empty list
    (``mission_type_activations: []``, C-008/C-A2) or any already-present
    list (custom entries included, C-A5/I-8) is left untouched. Re-running
    this function against an already-provisioned project is a no-op:
    ``config.yaml`` is not rewritten at all (NFR-004/I-9).

    Args:
        project_path: Root of the project being initialized (``.kittify``'s
            parent). Created if it does not already exist.

    Returns:
        ``True`` if ``config.yaml`` was created or modified, ``False`` if
        provisioning was a no-op because the key was already present.

    Raises:
        DefaultCharterPackMissingError: the shipped default charter pack is
            missing or malformed (FR-011 fail-closed) — never an empty or
            implicit set.
    """
    pack_activations = _load_default_pack_activations()

    kittify_dir = project_path / ".kittify"
    config_file = kittify_dir / "config.yaml"

    yaml = YAML()
    yaml.preserve_quotes = True

    raw_config: Any = None
    if config_file.exists():
        with config_file.open("r", encoding="utf-8") as fh:
            raw_config = yaml.load(fh)
    config_data: dict[str, Any] = raw_config if isinstance(raw_config, dict) else {}

    # Reuse the shared pack -> config merge helper (the same one the rc35
    # migration and `spec-kitty charter pack apply` use, D-07/T015): a
    # single-key pack_data dict scopes the merge to `mission_type_activations`
    # only, and force=False gives the additive, key-already-present-is-a-noop
    # semantics this function documents.
    keys_written, _keys_skipped = merge_pack_into_config(
        config_data,
        {_MISSION_TYPE_ACTIVATIONS_KEY: pack_activations},
        force=False,
    )
    if not keys_written:
        return False

    kittify_dir.mkdir(parents=True, exist_ok=True)
    with config_file.open("w", encoding="utf-8") as fh:
        yaml.dump(config_data, fh)
    return True
