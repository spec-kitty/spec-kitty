"""``charter.packs`` is a pure identity facade over ``charter.offering.packs``.

Mission ``charter-pack-cutover-01M491G6`` WP04 (#3732, FR-010 / OD-9, research
A.3 #8): ``specify_cli`` reaches the pack model and tooling only through this
facade. Every exported name must *be* the offering object (no wrapper, alias
or shim), and the facade itself reaches neither ``specify_cli`` nor
``charter.activation`` (offering-side names only until WP05 adds the
org-charter composing entries).
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

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_OFFERING_MODULES = [importlib.import_module(f"charter.offering.packs.{info.name}") for info in pkgutil.iter_modules(charter.offering.packs.__path__)]


def test_facade_exports_something() -> None:
    assert charter.packs.__all__, "control: the facade exports names"
    assert len(set(charter.packs.__all__)) == len(charter.packs.__all__)


@pytest.mark.parametrize("name", charter.packs.__all__)
def test_every_facade_name_is_the_offering_object(name: str) -> None:
    value = getattr(charter.packs, name)
    owners = [module.__name__ for module in _OFFERING_MODULES if getattr(module, name, None) is value]
    assert owners, f"charter.packs.{name} is not an object of any charter.offering.packs module"


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
    assert all(module == "__future__" or module.startswith("charter.offering.packs.") for module in imported), sorted(imported)


@pytest.mark.parametrize("module", _OFFERING_MODULES, ids=lambda module: module.__name__)
def test_offering_pack_modules_import_neither_activation_nor_specify_cli(module: ModuleType) -> None:
    imported = _imported_modules(Path(str(module.__file__)))
    offenders = sorted(name for name in imported if name.startswith(("charter.activation", "specify_cli", "charter.packs")))
    assert offenders == []


def test_offering_package_holds_the_pack_tooling() -> None:
    names = {module.__name__.rsplit(".", 1)[1] for module in _OFFERING_MODULES}
    assert {"extends", "hashing", "pack_descriptor", "pack_lineage", "pack_manifest", "builtin_manifest", "pack_validator", "pack_assembler"} <= names
