"""Measure a project's effective charter set (NFR-001, research ``postspec-squad-testability.md`` §C).

WORK PACKAGES NEVER EDIT THIS MODULE. Its source digest is pinned in the golden
header (``tests/fixtures/charter_pack_cutover/golden_before/_meta.json``
``effective_set_digest``). If a later rename breaks an import here, that is a WP01
follow-up: fix the helper, regenerate the golden data at the base, and log it.

The measurement:

* the activation-aware service (``build_activation_aware_doctrine_service``; the
  planned WP20 name ``build_active_charter_service`` is tried first): for every
  artifact kind it exposes, the key set of its mapping, directives included;
* ``activated_kinds`` applied, mirroring ``drg_activation.py``: a kind outside the
  gate is empty;
* ``mission_types`` from ``PackContext.from_config``; ``skills`` from
  ``establish_in_force_skill_ids``.

Each kind is recorded as ``{"form": "ALL_BUILTIN" | "explicit", "ids": [...],
"extra": [...]}``: ``ALL_BUILTIN`` when the kind is unrestricted (key absent and not
gated out), else the explicit sorted id list; ``extra`` is always the project and org
ids of that kind (the ids the built-in inventory does not have). :func:`expand` turns a
record back into id sets against the built-in inventory read at comparison time.
"""

from __future__ import annotations

import importlib
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

ALL_BUILTIN = "ALL_BUILTIN"
EXPLICIT = "explicit"

#: (record key == activation plural, service attribute). ``anti_patterns`` has no service mapping.
KINDS: tuple[str, ...] = (
    "directives",
    "tactics",
    "styleguides",
    "toolguides",
    "paradigms",
    "procedures",
    "agent_profiles",
    "mission_step_contracts",
    "glossary_packs",
)

_BUILDERS = (
    ("charter.activation.active_charter_service_builder", "build_active_charter_service"),
    ("charter.activation.doctrine_service_builder", "build_activation_aware_doctrine_service"),
)


def _service_builder() -> Any:
    last: Exception | None = None
    for module_name, attr in _BUILDERS:
        try:
            return getattr(importlib.import_module(module_name), attr)
        except (ImportError, AttributeError) as exc:
            last = exc
    raise ImportError(f"no activation-aware service builder found: {last}")


def _pack_context(repo_root: Path) -> Any:
    return importlib.import_module("charter.activation.pack_context").PackContext.from_config(repo_root)


def _service_ids(repo_root: Path) -> dict[str, set[str]]:
    service = _service_builder()(repo_root)
    return {kind: {str(k) for k in getattr(service, kind)} for kind in KINDS}


def builtin_inventory() -> dict[str, list[str]]:
    """Every built-in id per kind: the unrestricted service of an empty project."""
    with tempfile.TemporaryDirectory(prefix="charter-pack-cutover-inventory-") as tmp:
        root = Path(tmp)
        (root / ".kittify").mkdir()
        return {kind: sorted(ids) for kind, ids in _service_ids(root).items()}


def _skills(repo_root: Path) -> list[str] | None:
    module = importlib.import_module("charter.activation.skill_preparation")
    ids = module.establish_in_force_skill_ids(repo_root).ids
    return None if ids is None else sorted(ids)


def effective_set(repo_root: Path, builtin: Mapping[str, list[str]] | None = None) -> dict[str, Any]:
    """The effective set of *repo_root* in the recorded form (see the module docstring)."""
    inventory = builtin if builtin is not None else builtin_inventory()
    ctx = _pack_context(repo_root)
    ids = _service_ids(repo_root)
    kinds: dict[str, dict[str, Any]] = {}
    for kind in KINDS:
        gated_out = kind not in ctx.activated_kinds
        effective = set() if gated_out else ids[kind]
        extra = sorted(effective - set(inventory.get(kind, ())))
        restricted = getattr(ctx, f"activated_{kind}", None) is not None
        if gated_out or restricted:
            kinds[kind] = {"form": EXPLICIT, "ids": sorted(effective), "extra": extra}
        else:
            kinds[kind] = {"form": ALL_BUILTIN, "extra": extra}
    return {
        "kinds": kinds,
        "mission_types": sorted(ctx.activated_mission_types),
        "skills": _skills(repo_root),
    }


def expand(record: Mapping[str, Any], builtin_now: Mapping[str, list[str]]) -> dict[str, frozenset[str]]:
    """Id set per kind: ``ALL_BUILTIN`` expanded against *builtin_now*, plus ``extra``."""
    out: dict[str, frozenset[str]] = {}
    for kind, entry in record["kinds"].items():
        if entry["form"] == ALL_BUILTIN:
            out[kind] = frozenset(builtin_now.get(kind, ())) | frozenset(entry["extra"])
        else:
            out[kind] = frozenset(entry["ids"])
    return out
