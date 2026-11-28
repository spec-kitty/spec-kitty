"""#7860 (FR-005, C-001): no second copy of the default-Mission write-branch rule.

An AST scan of ``src/``: only ``mission_runtime/resolution.py`` calls ``default_mission_primary_ref``,
and no function outside it compares ``topology_source`` with ``"default"`` while reading a landing
signal (re-deriving the rule instead of reading the one predicate,
``mission_runtime.default_mission_rule_applies``). One priced exception:
``specify_cli/review/wp_range.py`` reads ``default_mission_primary_ref`` directly (C-001, operator
ruling: fold it onto the shared reader after #5604 lands; exit: #5604).
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = [pytest.mark.architectural]

_SRC = Path(__file__).resolve().parents[2] / "src"
_AUTHORITY = Path("mission_runtime/resolution.py")
#: The one priced exception (Standing Order #5): the review range keeps its own read until #5604 lands.
_REVIEW_RANGE_EXCEPTION = Path("specify_cli/review/wp_range.py")
#: Calls that decide a write branch on their own. The pure predicate ``default_mission_rule_applies``
#: is the one rule itself, so reading it (the topic-holder locator does) is reuse, not a copy.
_RULE_FUNCTIONS = frozenset({"default_mission_primary_ref"})
_LANDING_SIGNALS = frozenset({"merged_at", "mission_has_landed", "landed"})


def _called_name(node: ast.Call) -> str | None:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _names_in(node: ast.AST) -> set[str]:
    """Every identifier, attribute and string constant inside *node*."""
    found: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Name):
            found.add(child.id)
        elif isinstance(child, ast.Attribute):
            found.add(child.attr)
        elif isinstance(child, ast.Constant) and isinstance(child.value, str):
            found.add(child.value)
    return found


def _compares_topology_source_with_default(function: ast.AST) -> bool:
    for node in ast.walk(function):
        if isinstance(node, ast.Compare):
            names = _names_in(node)
            if "topology_source" in names and "default" in names:
                return True
    return False


def rule_copies(source: str) -> list[str]:
    """``<line>: <what>`` for each use of the default-Mission rule in *source* (a module outside the authority)."""
    tree = ast.parse(source)
    hits: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and _called_name(node) in _RULE_FUNCTIONS:
            hits.append(f"{node.lineno}: calls {_called_name(node)}")
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and _compares_topology_source_with_default(node) and _names_in(node) & _LANDING_SIGNALS:
            hits.append(f"{node.lineno}: {node.name} re-derives the default-Mission rule (topology_source == 'default' with a landing signal)")
    return hits


def _scan_src() -> dict[Path, list[str]]:
    found: dict[Path, list[str]] = {}
    for path in sorted(_SRC.rglob("*.py")):
        relative = path.relative_to(_SRC)
        if relative == _AUTHORITY:
            continue
        hits = rule_copies(path.read_text(encoding="utf-8"))
        if hits:
            found[relative] = hits
    return found


def test_the_default_mission_rule_has_one_home() -> None:
    """Only ``mission_runtime/resolution.py`` decides the rule; the review range is the one priced exception (#5604)."""
    found = _scan_src()

    assert set(found) <= {_REVIEW_RANGE_EXCEPTION}, f"a second copy of the default-Mission write-branch rule: {found}"
    assert _REVIEW_RANGE_EXCEPTION in found, "the review-range exception is gone: drop it from this test (its exit, #5604, has landed)"
    assert all("default_mission_primary_ref" in hit for hit in found[_REVIEW_RANGE_EXCEPTION]), found[_REVIEW_RANGE_EXCEPTION]


@pytest.mark.parametrize(
    "snippet",
    [
        "from mission_runtime import default_mission_primary_ref\nx = default_mission_primary_ref('default', 'b', False, 'main')\n",
        "import mission_runtime\nx = mission_runtime.default_mission_primary_ref('default', 'b', False, 'main')\n",
        "def f(meta):\n    return meta.get('topology_source') == 'default' and not meta.get('merged_at')\n",
    ],
)
def test_the_scan_catches_a_second_copy(snippet: str) -> None:
    """Self-mutation: each way of copying the rule is detected."""
    assert rule_copies(snippet)


def test_the_scan_accepts_a_reader_of_the_one_predicate() -> None:
    """Reading ``default_mission_rule_applies`` is reuse of the rule, not a copy of it."""
    reader = (
        "import mission_runtime\n"
        "def f(meta, landed):\n"
        "    return mission_runtime.default_mission_rule_applies(meta.get('topology_source'), meta.get('mission_branch'), landed)\n"
    )
    assert not rule_copies(reader)


def test_the_scan_ignores_the_settlement_rule() -> None:
    """``topology_source == 'default'`` with ``topology_settled`` (the settlement, not the landing) is a different rule."""
    assert not rule_copies("def f(meta):\n    return meta.get('topology_source') == 'default' and meta.get('topology_settled') is False\n")
