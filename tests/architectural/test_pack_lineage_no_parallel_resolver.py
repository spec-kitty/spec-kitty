"""Architectural guardrail (T013, C-002/NFR-001): no parallel lineage resolver.

``charter.offering.packs.extends.resolve_extends_order`` is the single canonical
resolver for lineage-chain topology (cycle detection, missing-base
detection, base-first ordering). ``src/charter/offering/packs/pack_lineage.py``
adapts ``pack_id``-keyed edges into the name-keyed shape that resolver
already consumes (see that module's docstring) -- it must never grow its own
graph-walking logic.

This guard AST-scans every ``pack_*.py`` module under
``src/charter/offering/packs/`` (the pack-module surface pack_lineage.py
belongs to) for two things:

1. **Positive**: ``pack_lineage.py`` actually calls
   ``resolve_extends_order`` -- lineage resolution genuinely routes through
   the canonical resolver, not just "doesn't do anything else".
2. **Negative**: no scanned module defines an *order-producing traversal* of
   its own -- structurally, a function that walks a chain (a ``while`` loop
   or self-recursion accumulating results via ``.append``/``.insert``)
   without delegating to ``resolve_extends_order``. That is exactly the
   shape of the retired ``org_charter._resolve_chain`` walker this mission
   forbids reintroducing (see ``charter/offering/packs/extends.py``'s own module docstring,
   C-005/R-10).

Falsifiability (non-vacuousness): the guard is proven to actually
discriminate by injecting a fake second walker into a fixture source below
and confirming the scan flags it (``test_guard_flags_injected_second_walker``).
A fixture with an equivalent-looking loop that *does* delegate to
``resolve_extends_order`` is confirmed NOT flagged, so the guard isn't so
broad it would reject legitimate adapter code (``pack_lineage.py`` itself
included).
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = pytest.mark.architectural

_REPO_ROOT = Path(__file__).resolve().parents[2]
_PACK_MODULES_ROOT = _REPO_ROOT / "src" / "charter" / "offering" / "packs"
_CANONICAL_RESOLVER = "resolve_extends_order"
_ACCUMULATOR_CALLS = {"append", "insert", "extend"}


def _iter_pack_modules(root: Path) -> list[Path]:
    """Every ``pack_*.py`` module directly under *root* (the pack-module surface)."""
    return sorted(root.glob("pack_*.py"))


def _rel(path: Path) -> str:
    return path.relative_to(_REPO_ROOT).as_posix()


def calls_resolve_extends_order(tree: ast.AST) -> bool:
    """True iff *tree* contains a call to ``resolve_extends_order`` (by name)."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name) and func.id == _CANONICAL_RESOLVER:
            return True
        if isinstance(func, ast.Attribute) and func.attr == _CANONICAL_RESOLVER:
            return True
    return False


def _is_accumulator_call(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in _ACCUMULATOR_CALLS
    )


def _body_has_accumulation(nodes: list[ast.stmt]) -> bool:
    for stmt in nodes:
        for node in ast.walk(stmt):
            if _is_accumulator_call(node):
                return True
    return False


def _function_calls_itself(func: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    return any(
        isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == func.name
        for node in ast.walk(func)
    )


def find_order_producing_traversals(tree: ast.Module) -> list[str]:
    """Return descriptions of second-walker-shaped functions in *tree*.

    Flags a function as an order-producing traversal when it does **not**
    delegate to :data:`_CANONICAL_RESOLVER` anywhere in its body, and it
    either:

    * contains a ``while`` loop whose body accumulates into a list
      (``.append``/``.insert``/``.extend``) -- the exact shape of
      ``resolve_extends_order``'s own walk and the retired
      ``org_charter._resolve_chain``; or
    * is self-recursive and its body accumulates into a list.

    A function that calls ``resolve_extends_order`` is exempt regardless of
    its own loops (it may legitimately loop to build the *input* edge map,
    as ``resolve_pack_lineage_order`` does).
    """
    offenders: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        if calls_resolve_extends_order(node):
            continue

        has_while_accumulation = any(
            isinstance(inner, ast.While) and _body_has_accumulation(inner.body)
            for inner in ast.walk(node)
        )
        is_recursive_accumulator = _function_calls_itself(node) and _body_has_accumulation(node.body)

        if has_while_accumulation or is_recursive_accumulator:
            offenders.append(node.name)
    return offenders


def test_pack_lineage_routes_only_through_extends() -> None:
    """Positive check: pack_lineage.py's lineage resolution calls resolve_extends_order."""
    pack_lineage_path = _PACK_MODULES_ROOT / "pack_lineage.py"
    assert pack_lineage_path.is_file(), f"expected {pack_lineage_path} to exist"

    tree = ast.parse(pack_lineage_path.read_text(encoding="utf-8"))
    assert calls_resolve_extends_order(tree), (
        "pack_lineage.py must route lineage resolution through "
        "charter.offering.packs.extends.resolve_extends_order (C-002/NFR-001) -- no "
        "call to the canonical resolver was found."
    )


def test_no_pack_module_defines_a_second_walker() -> None:
    """Negative check: no pack_*.py module hand-rolls its own chain walk."""
    offenders: dict[str, list[str]] = {}
    for path in _iter_pack_modules(_PACK_MODULES_ROOT):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        found = find_order_producing_traversals(tree)
        if found:
            offenders[_rel(path)] = found

    assert not offenders, (
        "Found order-producing traversal(s) that do not delegate to "
        f"resolve_extends_order -- a second lineage resolver: {offenders}. "
        "Lineage resolution must route only through "
        "charter.offering.packs.extends.resolve_extends_order (C-002/NFR-001)."
    )


# ---------------------------------------------------------------------------
# Non-vacuousness self-tests: prove the guard actually discriminates.
# ---------------------------------------------------------------------------

_FAKE_SECOND_WALKER_WHILE = """
def _sneaky_resolve_order(start, edges):
    chain = []
    current = start
    while current is not None:
        chain.append(current)
        current = edges.get(current)
    chain.reverse()
    return chain
"""

_FAKE_SECOND_WALKER_RECURSIVE = """
def _sneaky_recursive_resolve(node, edges, acc=None):
    acc = acc if acc is not None else []
    acc.append(node)
    parent = edges.get(node)
    if parent is not None:
        _sneaky_recursive_resolve(parent, edges, acc)
    return acc
"""

_LEGITIMATE_ADAPTER_LOOP = """
from charter.offering.packs.extends import resolve_extends_order

def resolve_pack_lineage_order(start_pack_id, parent_edges, pack_names):
    name_edges = {}
    for pack_id, parent_id in parent_edges.items():
        name_edges[pack_id] = parent_id
    return resolve_extends_order(start_pack_id, name_edges)
"""

_WHILE_LOOP_WITHOUT_ACCUMULATION = """
def _count_down(n):
    while n > 0:
        n -= 1
    return n
"""


@pytest.mark.parametrize(
    "source",
    [_FAKE_SECOND_WALKER_WHILE, _FAKE_SECOND_WALKER_RECURSIVE],
)
def test_guard_flags_injected_second_walker(source: str) -> None:
    """An injected second walker IS flagged -- the guard is not vacuous."""
    tree = ast.parse(source)
    assert find_order_producing_traversals(tree), (
        f"Expected the guard to flag an injected second walker in:\n{source}\n"
        "but it found nothing -- the ratchet would be vacuous."
    )


@pytest.mark.parametrize(
    "source",
    [_LEGITIMATE_ADAPTER_LOOP, _WHILE_LOOP_WITHOUT_ACCUMULATION],
)
def test_guard_does_not_flag_legitimate_adapter_code(source: str) -> None:
    """A loop that delegates to resolve_extends_order (or doesn't accumulate) is NOT flagged."""
    tree = ast.parse(source)
    assert not find_order_producing_traversals(tree), (
        f"Guard incorrectly flagged legitimate adapter code:\n{source}\n"
        "A function that delegates to resolve_extends_order (or has a "
        "non-accumulating loop) must not be treated as a second walker."
    )
