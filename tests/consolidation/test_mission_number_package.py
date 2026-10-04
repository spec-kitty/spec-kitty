"""#2600: the ``mission_number`` package ``__init__`` stays a standard-library-only leaf (#4900).

``consolidation/mission_number/__init__.py`` keeps its own imports
standard-library-only (its documented leaf contract) and never imports its
``bake`` submodule. This pins the file, not the import closure: importing any
``specify_cli.consolidation`` submodule first runs the package ``__init__``,
which re-exports ``assign_next_mission_number`` and so loads the bake cluster,
exactly as it loaded ``ordering`` before #2600.
"""

from __future__ import annotations

import ast
import inspect
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.fast


def test_mission_number_leaf_imports_only_the_standard_library() -> None:
    import specify_cli.consolidation.mission_number as leaf

    source = Path(inspect.getfile(leaf))
    assert source.name == "__init__.py", "mission_number must be a package whose __init__ is the leaf"
    roots: set[str] = set()
    for node in ast.walk(ast.parse(source.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            # A relative import (``from .bake import ...``) would make the leaf
            # file itself depend on the bake cluster: refuse it outright.
            assert node.level == 0, "mission_number leaf must not import its own submodules (relative import)"
            if node.module:
                roots.add(node.module.split(".")[0])
    non_stdlib = {root for root in roots if root != "__future__" and root not in sys.stdlib_module_names}
    assert not non_stdlib, f"mission_number leaf file must import only the standard library, imports {sorted(non_stdlib)}"
