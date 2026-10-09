"""``charter.packs`` is a pure identity facade over ``charter.offering.packs``.

Mission ``charter-pack-cutover-01M491G6`` WP04 (#3732, FR-010 / OD-9, research
A.3 #8): ``specify_cli`` reaches the pack model and tooling only through this
facade. Every exported name must *be* the offering object (no wrapper, alias
or shim), except the two org-charter composing entries WP05 added, which must
*be* the :mod:`charter.activation.org_charter` objects. The facade never
reaches ``specify_cli``, and reaches ``charter.activation`` only through
``charter.activation.org_charter``.
"""

from __future__ import annotations

import ast
import importlib
import pkgutil
from pathlib import Path
from types import ModuleType

import pytest

import charter.offering.packs
import charter.packs
from charter.activation import org_charter

pytestmark = [pytest.mark.unit, pytest.mark.fast]

#: The org-charter composing entries (research A.3 #4): activation objects.
_COMPOSING_ENTRIES = ("validate_pack_with_org_charter", "assemble_pack_with_org_charter")
_ORG_CHARTER_MODULE = "charter.activation.org_charter"

_OFFERING_MODULES = [importlib.import_module(f"charter.offering.packs.{info.name}") for info in pkgutil.iter_modules(charter.offering.packs.__path__)]


def test_facade_exports_something() -> None:
    assert charter.packs.__all__, "control: the facade exports names"
    assert len(set(charter.packs.__all__)) == len(charter.packs.__all__)


@pytest.mark.parametrize("name", [n for n in charter.packs.__all__ if n not in _COMPOSING_ENTRIES])
def test_every_facade_name_is_the_offering_object(name: str) -> None:
    value = getattr(charter.packs, name)
    owners = [module.__name__ for module in _OFFERING_MODULES if getattr(module, name, None) is value]
    assert owners, f"charter.packs.{name} is not an object of any charter.offering.packs module"


@pytest.mark.parametrize("name", _COMPOSING_ENTRIES)
def test_composing_entries_are_the_org_charter_objects(name: str) -> None:
    assert name in charter.packs.__all__
    assert getattr(charter.packs, name) is getattr(org_charter, name)


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
        elif isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
    return found


def test_facade_imports_only_the_offering_pack_modules() -> None:
    imported = _imported_modules(Path(str(charter.packs.__file__)))
    assert imported, "control: the facade has imports"
    assert _ORG_CHARTER_MODULE in imported, sorted(imported)
    assert all(module in {"__future__", _ORG_CHARTER_MODULE} or module.startswith("charter.offering.packs.") for module in imported), sorted(imported)


@pytest.mark.parametrize("module", _OFFERING_MODULES, ids=lambda module: module.__name__)
def test_offering_pack_modules_import_neither_activation_nor_specify_cli(module: ModuleType) -> None:
    imported = _imported_modules(Path(str(module.__file__)))
    offenders = sorted(name for name in imported if name.startswith(("charter.activation", "specify_cli", "charter.packs")))
    assert offenders == []


def test_offering_package_holds_the_pack_tooling() -> None:
    names = {module.__name__.rsplit(".", 1)[1] for module in _OFFERING_MODULES}
    assert {"extends", "hashing", "pack_descriptor", "pack_lineage", "pack_manifest", "builtin_manifest", "pack_validator", "pack_assembler"} <= names
