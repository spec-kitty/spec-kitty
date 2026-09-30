"""Non-vacuous guard for the single finalize planning-pin decision source."""

from __future__ import annotations

import ast
from copy import deepcopy
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_SOURCE_PATH = Path(__file__).resolve().parents[2] / "src/specify_cli/cli/commands/agent/mission_finalize.py"
_ROUTER_PATH = Path(__file__).resolve().parents[2] / "src/specify_cli/coordination/commit_router.py"


def _named_function(tree: ast.Module, name: str) -> ast.FunctionDef:
    matches = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name]
    assert len(matches) == 1, f"expected one {name} definition, found {len(matches)}"
    return matches[0]


def _has_keyword_call(function: ast.FunctionDef, callee: str, keyword: str) -> bool:
    return any(
        isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == callee and any(argument.arg == keyword for argument in node.keywords)
        for node in ast.walk(function)
    )


def _pin_wiring_violations(source: str) -> list[str]:
    tree = ast.parse(source)
    functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
    entrypoint = functions.get("finalize_tasks")
    if entrypoint is None:
        return ["finalize entrypoint is missing"]

    authority_calls = [
        node
        for node in ast.walk(entrypoint)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "_preserve_or_capture_planning_commit_sha"
    ]
    violations: list[str] = []
    if len(authority_calls) != 1:
        violations.append("finalize must resolve the planning pin once through its canonical authority")

    if not _has_keyword_call(entrypoint, "_emit_validate_only_report", "planning_sha"):
        violations.append("validate-only path does not receive the canonical planning pin decision")
    if not _has_keyword_call(entrypoint, "_run_commit_pipeline", "planning_sha"):
        violations.append("mutating path does not receive the canonical planning pin decision")

    pipeline = functions.get("_run_commit_pipeline")
    if pipeline is None or not any(argument.arg == "planning_sha" for argument in pipeline.args.kwonlyargs):
        violations.append("commit pipeline has no planning_sha input")
    return violations


def test_finalize_pin_decision_has_one_authority_and_two_consumers() -> None:
    source = _SOURCE_PATH.read_text(encoding="utf-8")
    assert _pin_wiring_violations(source) == []


def test_structural_guard_detects_removed_validate_only_pin_flow() -> None:
    tree = ast.parse(_SOURCE_PATH.read_text(encoding="utf-8"))

    class RemoveDryRunPin(ast.NodeTransformer):
        def visit_Call(self, node: ast.Call) -> ast.Call:
            self.generic_visit(node)
            if isinstance(node.func, ast.Name) and node.func.id == "_emit_validate_only_report":
                node.keywords = [keyword for keyword in node.keywords if keyword.arg != "planning_sha"]
            return node

    mutated_source = ast.unparse(RemoveDryRunPin().visit(deepcopy(tree)))
    violations = _pin_wiring_violations(mutated_source)
    assert any("validate-only path" in violation for violation in violations), "self-mutation must prove the guard notices a missing dry-run pin consumer"


def _refresh_lock_violations(wrapper: ast.FunctionDef) -> list[str]:
    calls = [node for node in ast.walk(wrapper) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)]
    violations: list[str] = []
    if not any(node.func.id == "lanes_json_lock" for node in calls):
        violations.append("pin-only refresh must hold the canonical lanes.json writer lock")
    if not any(node.func.id == "_commit_planning_pin_refresh_locked" for node in calls):
        violations.append("pin-only refresh must run its transaction inside the locked commit helper")
    return violations


def _commit_uses_expected_parent(call: ast.Call) -> bool:
    expected_parent = next((keyword.value for keyword in call.keywords if keyword.arg == "expected_parent_sha"), None)
    return isinstance(expected_parent, ast.Attribute) and expected_parent.attr == "expected_parent_sha"


def _refresh_safety_violations(finalize_source: str, router_source: str) -> list[str]:
    finalize_tree = ast.parse(finalize_source)
    functions = {node.name: node for node in finalize_tree.body if isinstance(node, ast.FunctionDef)}
    entrypoint = functions.get("finalize_tasks")
    refresh_wrapper = functions.get("_commit_planning_pin_refresh")
    refresh = functions.get("_commit_planning_pin_refresh_locked")
    prepare = functions.get("_prepare_primary_pin_refresh_commit")
    if entrypoint is None or refresh_wrapper is None or refresh is None or prepare is None:
        return ["refresh entrypoint or pin-only commit helper is missing"]

    violations = _refresh_lock_violations(refresh_wrapper)

    calls = [node for node in ast.walk(entrypoint) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)]
    guard_lines = [node.lineno for node in calls if node.func.id == "_preflight_refresh_planning_commit"]
    writer_names = {
        "_persist_branch_contract_for_finalize",
        "_scaffold_issue_matrix_if_present",
        "_flush_frontmatter_writes",
        "_emit_tasks_started",
        "_run_commit_pipeline",
    }
    writer_lines = [node.lineno for node in calls if node.func.id in writer_names]
    if len(guard_lines) != 1 or (writer_lines and min(guard_lines, default=0) > min(writer_lines)):
        violations.append("refresh safety preflight must run once before finalize writers and event emitters")
    validate_only_gate = any(
        isinstance(node, ast.If)
        and isinstance(node.test, ast.UnaryOp)
        and isinstance(node.test.op, ast.Not)
        and isinstance(node.test.operand, ast.Name)
        and node.test.operand.id == "validate_only"
        and any(isinstance(call, ast.Call) and isinstance(call.func, ast.Name) and call.func.id == "_preflight_refresh_planning_commit" for call in ast.walk(node))
        for node in ast.walk(entrypoint)
    )
    if not validate_only_gate:
        violations.append("validate-only must bypass the mutating refresh preflight")

    refresh_calls = [node for node in ast.walk(refresh) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)]
    commit_calls = [node for node in refresh_calls if node.func.id == "commit_for_mission"]
    if len(commit_calls) != 1:
        violations.append("pin-only refresh must have one canonical commit seam call")
    else:
        files_arg = next((keyword.value for keyword in commit_calls[0].keywords if keyword.arg == "files"), None)
        file_assignment = next(
            (
                node
                for node in prepare.body
                if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "files" for target in node.targets)
            ),
            None,
        )
        assigned_files = file_assignment.value if file_assignment is not None else None

        def is_exact_lanes_tuple(node: ast.expr | None) -> bool:
            if isinstance(node, ast.IfExp):
                return is_exact_lanes_tuple(node.body) and is_exact_lanes_tuple(node.orelse)
            # #5445: ``OwnedCheckout.files(paths: list[Path])`` is list-typed
            # (mypy --strict invariance forbids passing a tuple there), so the
            # owned branch of the ternary is now a single-element LIST literal
            # (``owned.files([lanes_path])``) while the non-owned branch stays
            # a tuple (``(lanes_path,)``). Both carry the identical containment
            # guarantee this check polices -- exactly one element, the
            # ``lanes_path`` name -- so a List is accepted on the same terms
            # as a Tuple; only the element shape is asserted, never the
            # container type.
            if isinstance(node, (ast.Tuple, ast.List)):
                return len(node.elts) == 1 and isinstance(node.elts[0], ast.Name) and node.elts[0].id == "lanes_path"
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "tuple" and len(node.args) == 1:
                return is_exact_lanes_tuple(node.args[0])
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "files" and len(node.args) == 1:
                return is_exact_lanes_tuple(node.args[0])
            return False

        files_from_preflighted_plan = (
            isinstance(files_arg, ast.Attribute) and isinstance(files_arg.value, ast.Name) and files_arg.value.id == "plan" and files_arg.attr == "files"
        )
        if not (files_from_preflighted_plan and is_exact_lanes_tuple(assigned_files)):
            violations.append("pin-only commit seam must receive exactly lanes_path")
        kind_arg = next((keyword.value for keyword in commit_calls[0].keywords if keyword.arg == "kind"), None)
        if not (isinstance(kind_arg, ast.Attribute) and kind_arg.attr == "LANE_STATE" and _commit_uses_expected_parent(commit_calls[0])):
            violations.append("pin-only commit seam must declare LANE_STATE and the captured expected parent SHA")

    forbidden_refresh_calls = {
        "_emit_local_canonical_events",
        "_emit_tasks_started",
        "_scaffold_issue_matrix_if_present",
        "_scaffold_acceptance_matrix_if_lane_based",
    }
    prepare_calls = [node for node in ast.walk(prepare) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)]
    if any(node.func.id in forbidden_refresh_calls for node in refresh_calls + prepare_calls):
        violations.append("pin-only refresh must not emit or scaffold coordination artifacts")

    router_tree = ast.parse(router_source)
    router_functions = {node.name for node in router_tree.body if isinstance(node, ast.FunctionDef)}
    if {"_rollback_partition_commits", "_rollback_partition_refs", "_reset_partition_indexes"} & router_functions:
        violations.append("the shared commit router must not implement broad multi-partition rollback")
    if any(isinstance(node, ast.List) and any(isinstance(value, ast.Constant) and value.value == "reset" for value in node.elts) for node in ast.walk(router_tree)):
        violations.append("the shared commit router must not reset git indexes during refresh rollback")
    return violations


def test_refresh_is_guarded_early_and_commits_only_primary_pin() -> None:
    violations = _refresh_safety_violations(
        _SOURCE_PATH.read_text(encoding="utf-8"),
        _ROUTER_PATH.read_text(encoding="utf-8"),
    )
    assert violations == []


def test_structural_guard_detects_coord_path_added_to_pin_commit() -> None:
    source = _SOURCE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)

    class AddCoordPathToRefreshCommit(ast.NodeTransformer):
        def visit_Tuple(self, node: ast.Tuple) -> ast.Tuple:
            self.generic_visit(node)
            if any(isinstance(item, ast.Name) and item.id == "lanes_path" for item in node.elts):
                node.elts.append(ast.Name(id="coordination_path", ctx=ast.Load()))
            return node

    mutated_source = ast.unparse(AddCoordPathToRefreshCommit().visit(deepcopy(tree)))
    violations = _refresh_safety_violations(mutated_source, _ROUTER_PATH.read_text(encoding="utf-8"))
    assert any("exactly lanes_path" in violation for violation in violations), "self-mutation must prove the guard rejects coordination paths"


def test_structural_guard_detects_unconditional_dirty_worktree_refusal() -> None:
    tree = ast.parse(_SOURCE_PATH.read_text(encoding="utf-8"))

    class RemoveValidateOnlyGate(ast.NodeTransformer):
        def visit_If(self, node: ast.If) -> ast.If | list[ast.stmt]:
            self.generic_visit(node)
            is_validate_only_gate = (
                isinstance(node.test, ast.UnaryOp)
                and isinstance(node.test.op, ast.Not)
                and isinstance(node.test.operand, ast.Name)
                and node.test.operand.id == "validate_only"
            )
            preflights_refresh = any(
                isinstance(call, ast.Call) and isinstance(call.func, ast.Name) and call.func.id == "_preflight_refresh_planning_commit"
                for statement in node.body
                for call in ast.walk(statement)
            )
            if is_validate_only_gate and preflights_refresh:
                return node.body
            return node

    mutated_source = ast.unparse(RemoveValidateOnlyGate().visit(deepcopy(tree)))
    violations = _refresh_safety_violations(mutated_source, _ROUTER_PATH.read_text(encoding="utf-8"))
    assert any("validate-only must bypass" in violation for violation in violations), "self-mutation must detect an unconditional dirty-worktree refusal"
