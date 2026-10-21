"""Test factory for the activation ledger (``.kittify/charter/activation.yaml``).

Seed activation state the way production writes it, and read it back:

* :func:`seed_activation_ledger` writes the ledger through the seam's single
  writer (:func:`charter.activation.activation_ledger.prepare_ledger_write`),
  passing ``deny_change=DenyListChoice.DEACTIVATE`` when deny keys are given.
* :func:`read_activation_ledger` returns the ledger mapping (``{}`` when absent).
* :func:`legacy_seed` writes the pre-ledger legacy shape for class-A tests whose
  subject *is* the legacy surface. Such a project is unmigrated: its reads use
  the legacy allow keys, and a deny write refuses until the ledger migration
  runs. A test of the migration itself wraps its reads in
  ``legacy_activation_scope(repo_root)``.
* :func:`legacy_target_scope` runs a block inside the upgrade scope for one or
  more roots, for a test whose subject is the legacy writer itself (its byte
  round trip on a keyless ``config.yaml`` / ``charter.yaml``): outside the
  scope such a project is fresh and writes the ledger instead (FR-019).
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from pathlib import Path
from typing import Any

import yaml

from charter.activation.activation_ledger import DENY_KEYS, DenyListChoice, prepare_ledger_write
from charter.activation.charter_yaml_io import apply_yaml_write
from kernel.activation_ledger_store import activation_ledger_path, legacy_activation_scope

__all__ = ["enter_legacy_target_scope", "legacy_seed", "legacy_target_scope", "read_activation_ledger", "seed_activation_ledger"]

_CHARTER_POINTER = ".kittify/charter/charter.yaml"
_CONFIG = Path(".kittify", "config.yaml")
_SURFACES = ("charter_yaml", "config_yaml")


def seed_activation_ledger(repo_root: Path, **keys: Any) -> Path:
    """Write *keys* into the ledger of *repo_root* and return the ledger path."""
    deny_change = DenyListChoice.DEACTIVATE if any(key in DENY_KEYS for key in keys) else None
    apply_yaml_write(prepare_ledger_write(repo_root, dict(keys), deny_change=deny_change))
    return activation_ledger_path(repo_root)


def read_activation_ledger(repo_root: Path) -> dict[str, Any]:
    """Return the ledger mapping of *repo_root*, or ``{}`` when there is none."""
    path = activation_ledger_path(repo_root)
    if not path.exists():
        return {}
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    return dict(loaded or {})


def _merge_yaml(path: Path, values: dict[str, Any]) -> Path:
    data: dict[str, Any] = {}
    if path.exists():
        data = dict(yaml.safe_load(path.read_text(encoding="utf-8")) or {})
    data.update(values)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return path


def legacy_seed(repo_root: Path, *, surface: str = "charter_yaml", **keys: Any) -> Path:
    """Write *keys* onto a legacy activation surface and return its path.

    ``surface="charter_yaml"`` writes the ``config.yaml`` ``charter:`` pointer
    and the activation keys into the pointed ``charter.yaml``;
    ``surface="config_yaml"`` writes them into a no-pointer ``config.yaml``.
    """
    if surface not in _SURFACES:
        raise ValueError(f"Unknown legacy surface {surface!r}; expected one of {_SURFACES}")
    config = repo_root / _CONFIG
    if surface == "config_yaml":
        return _merge_yaml(config, dict(keys))
    _merge_yaml(config, {"charter": _CHARTER_POINTER})
    return _merge_yaml(repo_root / _CHARTER_POINTER, dict(keys))


@contextmanager
def legacy_target_scope(*roots: Path) -> Iterator[None]:
    """Run the block inside the upgrade scope for every root in *roots* (the legacy target stays the write target)."""
    with ExitStack() as stack:
        for root in roots:
            stack.enter_context(legacy_activation_scope(root))
        yield


def enter_legacy_target_scope(request: Any, *roots: Path) -> None:
    """Enter :func:`legacy_target_scope` for *roots* until *request*'s test finishes (``request.addfinalizer``)."""
    scope = legacy_target_scope(*roots)
    scope.__enter__()
    request.addfinalizer(lambda: scope.__exit__(None, None, None))
