"""#2600: ``ordering`` holds merge ordering only; the mission_number cluster lives under ``mission_number``.

Structural pins for the relocation (behaviour is pinned by the bake seam tests):

* ``consolidation/ordering.py`` defines only the dependency merge-ordering surface.
* ``consolidation/mission_number/__init__.py`` keeps its own imports
  standard-library-only (its documented leaf contract, #4900) and never imports
  its ``bake`` submodule. This pins the file, not the import closure: importing
  any ``specify_cli.consolidation`` submodule first runs the package
  ``__init__``, which re-exports ``assign_next_mission_number`` and so loads
  the bake cluster, exactly as it loaded ``ordering`` before #2600.
* ``consolidation/mission_number/bake.py`` owns the assign / bake / write / verify cluster.
"""

from __future__ import annotations

import ast
import importlib
import inspect
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.fast

_ORDERING_SURFACE = frozenset({"MergeOrderError", "has_dependency_info", "get_merge_order"})
_BAKE_CLUSTER = frozenset(
    {
        "assign_next_mission_number",
        "_already_baked",
        "_mark_mission_number_baked",
        "_is_assigned_mission_number",
        "_compute_next_mission_number_or_none",
        "_surface_unbaked_mission_number",
        "_bake_mission_number_on_primary_tree",
        "_write_mission_number_to_branch",
        "_refuse_unassignable_mission_slug",
        "_bake_mission_number_into_mission_branch",
        "_assign_planning_only_mission_number_if_needed",
        "_bake_mission_number_onto_target_tree",
        "_read_target_tree_mission_number",
    }
)


def _top_level_definitions(module_name: str) -> set[str]:
    tree = ast.parse(inspect.getsource(importlib.import_module(module_name)))
    return {node.name for node in tree.body if isinstance(node, ast.FunctionDef | ast.ClassDef)}


def test_ordering_defines_only_the_merge_ordering_surface() -> None:
    assert _top_level_definitions("specify_cli.consolidation.ordering") == _ORDERING_SURFACE


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


def test_bake_module_owns_the_mission_number_cluster() -> None:
    assert _top_level_definitions("specify_cli.consolidation.mission_number.bake") == _BAKE_CLUSTER


def test_leaf_predicate_is_unchanged() -> None:
    from specify_cli.consolidation.mission_number import is_assigned_mission_number

    assert [is_assigned_mission_number(v) for v in (1, 7, 0, -1, True, None, "3")] == [True, True, False, False, False, False, False]
