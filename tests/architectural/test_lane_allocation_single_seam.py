"""Structural guard for the lane-allocation parent-ref seam.

The guard anchors on symbols and AST def-use, not parent-ref spelling. Every
ref handed to lane creation must trace to ``resolve_lane_base_or_refuse``, and
each member of the closed allocation-route enum must reach that seam.
Synthetic fixtures prove both checks are non-vacuous.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

import pytest

pytestmark = pytest.mark.architectural

_REPO_ROOT = Path(__file__).resolve().parents[2]
_ALLOCATOR = _REPO_ROOT / "src" / "specify_cli" / "lanes" / "worktree_allocator.py"
_SEAM = "resolve_lane_base_or_refuse"
_ROUTE_ENUM = "LaneAllocationRoute"
_EXPECTED_ROUTES = frozenset(
    {"FRESH_COORD", "FRESH_LEGACY", "REUSE", "CRASH_RECOVERY"},
)
# ``_ensure_mission_branch`` ensures the mission INTEGRATION branch exists by
# its topology name (created from target_branch when absent) -- a sibling of
# the already-unpoliced ``_ensure_branch_exists``, NOT the origin-aware lane
# parent this seam owns for #4969. Forcing its argument to
# ``decision.parent_ref`` misnames the mission branch when a legacy lane
# exists only on origin (#5001), so it is intentionally left off this policed
# set; it is fed from ``decision.topology_parent_ref`` instead.
_CREATION_PARENT_ARG: dict[str, tuple[int, str]] = {
    "_create_lane_worktree": (3, "base_branch"),
}
_RULE_INLINE = "inline parent-ref computation outside resolve_lane_base_or_refuse"


@dataclass(frozen=True)
class Violation:
    """A flagged bypass with its file, line, and rule."""

    label: str
    lineno: int
    rule: str

    def __str__(self) -> str:
        return f"{self.label}:{self.lineno} -- {self.rule}"


def _parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _call_name(call: ast.Call) -> str | None:
    if isinstance(call.func, ast.Name):
        return call.func.id
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return None


def _enclosing_functions(
    tree: ast.Module,
) -> dict[int, ast.FunctionDef | ast.AsyncFunctionDef | None]:
    """Map call nodes to their nearest enclosing function."""

    functions: dict[int, ast.FunctionDef | ast.AsyncFunctionDef | None] = {}

    def visit(
        node: ast.AST,
        current: ast.FunctionDef | ast.AsyncFunctionDef | None,
    ) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                functions[id(child)] = current
                visit(child, child)
            else:
                if isinstance(child, ast.Call):
                    functions[id(child)] = current
                visit(child, current)

    visit(tree, None)
    return functions


def _is_seam_call(call: ast.Call) -> bool:
    return _call_name(call) == _SEAM


def _is_parent_ref_of_seam(
    value: ast.expr,
    seam_decisions: set[str],
) -> bool:
    if not (isinstance(value, ast.Attribute) and value.attr == "parent_ref"):
        return False
    receiver = value.value
    if isinstance(receiver, ast.Name) and receiver.id in seam_decisions:
        return True
    return isinstance(receiver, ast.Call) and _is_seam_call(receiver)


def _seam_derived_names(
    function: ast.FunctionDef | ast.AsyncFunctionDef,
) -> tuple[set[str], set[str]]:
    """Return seam decisions and names assigned from ``decision.parent_ref``."""

    assignments = [node for node in ast.walk(function) if isinstance(node, ast.Assign)]
    seam_decisions: set[str] = set()
    for assignment in assignments:
        if isinstance(assignment.value, ast.Call) and _is_seam_call(
            assignment.value,
        ):
            seam_decisions.update(target.id for target in assignment.targets if isinstance(target, ast.Name))

    parent_ref_names: set[str] = set()
    for assignment in assignments:
        if _is_parent_ref_of_seam(assignment.value, seam_decisions):
            parent_ref_names.update(target.id for target in assignment.targets if isinstance(target, ast.Name))
    return seam_decisions, parent_ref_names


def _parent_arg(
    call: ast.Call,
    positional_index: int,
    keyword_name: str,
) -> ast.expr | None:
    for keyword in call.keywords:
        if keyword.arg == keyword_name:
            return keyword.value
    if 0 <= positional_index < len(call.args):
        argument = call.args[positional_index]
        return None if isinstance(argument, ast.Starred) else argument
    return None


def _is_seam_parent(
    argument: ast.expr,
    seam_decisions: set[str],
    parent_ref_names: set[str],
) -> bool:
    if _is_parent_ref_of_seam(argument, seam_decisions):
        return True
    return isinstance(argument, ast.Name) and argument.id in parent_ref_names


def _allocation_violations(
    tree: ast.Module,
    label: str,
) -> list[Violation]:
    """Flag every creation-call parent that does not trace to the seam."""

    enclosing = _enclosing_functions(tree)
    seam_cache: dict[int, tuple[set[str], set[str]]] = {}
    violations: list[Violation] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        call_symbol = _call_name(node)
        if call_symbol not in _CREATION_PARENT_ARG:
            continue
        positional_index, keyword_name = _CREATION_PARENT_ARG[call_symbol]
        argument = _parent_arg(node, positional_index, keyword_name)
        if argument is None:
            continue
        function = enclosing.get(id(node))
        if function is None:
            violations.append(Violation(label, node.lineno, _RULE_INLINE))
            continue
        if id(function) not in seam_cache:
            seam_cache[id(function)] = _seam_derived_names(function)
        seam_decisions, parent_ref_names = seam_cache[id(function)]
        if not _is_seam_parent(
            argument,
            seam_decisions,
            parent_ref_names,
        ):
            violations.append(Violation(label, node.lineno, _RULE_INLINE))
    return violations


def _count_creation_calls(tree: ast.Module) -> int:
    return sum(1 for node in ast.walk(tree) if isinstance(node, ast.Call) and _call_name(node) in _CREATION_PARENT_ARG)


def _route_coverage(tree: ast.Module) -> set[str]:
    """Collect route enum members passed to the seam."""

    routes: set[str] = set()
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and _is_seam_call(node)):
            continue
        for keyword in node.keywords:
            if keyword.arg != "route":
                continue
            value = keyword.value
            if isinstance(value, ast.Attribute) and isinstance(value.value, ast.Name) and value.value.id == _ROUTE_ENUM:
                routes.add(value.attr)
    return routes


def _enum_members(tree: ast.Module, class_name: str) -> set[str]:
    members: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            for statement in node.body:
                if isinstance(statement, ast.Assign):
                    members.update(target.id for target in statement.targets if isinstance(target, ast.Name))
    return members


def _defines_symbol(tree: ast.Module, name: str) -> bool:
    return any(
        isinstance(
            node,
            (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef),
        )
        and node.name == name
        for node in ast.walk(tree)
    )


_ALLOC_BYPASS_FIXTURE = """
def allocate_bypass(repo_root, worktree, branch, coordination_branch, mission_branch):
    parent = coordination_branch or mission_branch
    _create_lane_worktree(repo_root, worktree, branch, parent)
"""

_ALLOC_CLEAN_FIXTURE = """
def allocate_clean(
    repo_root, worktree, branch, base, coordination_branch,
    mission_branch, wp_id,
):
    decision = resolve_lane_base_or_refuse(
        base=base,
        route=LaneAllocationRoute.FRESH_LEGACY,
        coordination_branch=coordination_branch,
        mission_branch=mission_branch,
        wp_id=wp_id,
    )
    _ensure_mission_branch(repo_root, decision.parent_ref, "main")
    _create_lane_worktree(repo_root, worktree, branch, decision.parent_ref)
"""

_ALLOC_INLINE_SEAM_FIXTURE = """
def allocate_inline(
    repo_root, worktree, branch, base, coordination_branch,
    mission_branch, wp_id,
):
    _create_lane_worktree(
        repo_root,
        worktree,
        branch,
        resolve_lane_base_or_refuse(
            base=base,
            route=LaneAllocationRoute.FRESH_COORD,
            coordination_branch=coordination_branch,
            mission_branch=mission_branch,
            wp_id=wp_id,
        ).parent_ref,
    )
"""

_ROUTE_MISSING_FIXTURE = """
def only_three_routes(base, wp_id):
    resolve_lane_base_or_refuse(base=base, route=LaneAllocationRoute.REUSE, wp_id=wp_id)
    resolve_lane_base_or_refuse(base=base, route=LaneAllocationRoute.CRASH_RECOVERY, wp_id=wp_id)
    resolve_lane_base_or_refuse(base=base, route=LaneAllocationRoute.FRESH_COORD, wp_id=wp_id)
"""


def _fixture_line(source: str, lineno: int) -> str:
    return source.splitlines()[lineno - 1]


def test_allocator_defines_the_anchored_symbols() -> None:
    tree = _parse(_ALLOCATOR)
    assert _defines_symbol(tree, _SEAM)
    assert _defines_symbol(tree, _ROUTE_ENUM)
    for creation_symbol in _CREATION_PARENT_ARG:
        assert _defines_symbol(tree, creation_symbol)


def test_every_lane_parent_ref_traces_to_the_seam() -> None:
    tree = _parse(_ALLOCATOR)
    assert _count_creation_calls(tree) >= 2
    violations = _allocation_violations(tree, "worktree_allocator.py")
    assert not violations, "inline parent-ref bypass(es):\n" + "\n".join(str(violation) for violation in violations)


def test_all_four_routes_reach_the_seam() -> None:
    tree = _parse(_ALLOCATOR)
    members = _enum_members(tree, _ROUTE_ENUM)
    coverage = _route_coverage(tree)
    assert members == set(_EXPECTED_ROUTES)
    assert coverage == set(_EXPECTED_ROUTES), f"routes not reaching the seam: {set(_EXPECTED_ROUTES) - coverage}"


def test_allocation_checker_flags_an_inline_parent_ref() -> None:
    tree = ast.parse(_ALLOC_BYPASS_FIXTURE)
    violations = _allocation_violations(tree, "<synthetic_alloc_bypass>")
    assert len(violations) == 1
    flagged = violations[0]
    assert flagged.rule == _RULE_INLINE
    assert flagged.label == "<synthetic_alloc_bypass>"
    assert "_create_lane_worktree" in _fixture_line(
        _ALLOC_BYPASS_FIXTURE,
        flagged.lineno,
    )


def test_allocation_checker_passes_seam_routed_forms() -> None:
    assert (
        _allocation_violations(
            ast.parse(_ALLOC_CLEAN_FIXTURE),
            "<clean>",
        )
        == []
    )
    assert (
        _allocation_violations(
            ast.parse(_ALLOC_INLINE_SEAM_FIXTURE),
            "<inline>",
        )
        == []
    )


def test_route_coverage_checker_is_non_vacuous() -> None:
    coverage = _route_coverage(ast.parse(_ROUTE_MISSING_FIXTURE))
    assert coverage == {"REUSE", "CRASH_RECOVERY", "FRESH_COORD"}
    assert coverage < set(_EXPECTED_ROUTES)
