"""Item 5 (optional, this mission's pre-merge R4 fixer pass): a narrow,
statement-order AST guard for ``record_analysis`` specifically.

PR-CONTRACT-001 fixed a live ordering fork: the dirty-worktree preflight
(``_enforce_analysis_report_write_preflight``) must run BEFORE the request
body is read (``_read_record_analysis_body``), matching the host CLI's own
``mission_record_analysis.record_analysis`` ordering. An earlier fixer
judged a general "by construction" guard for this validation-ordering class
infeasible across this mission's several structurally-different mutating
verbs (record-analysis's body-read + dirty-tree pair vs. defer/cancel-
decision's ``--rationale`` check vs. answer-decision's ``--result`` check).
A verifier judged that overstated for ``record_analysis`` specifically: a
guard scoped to just this one function's two known statements is cheap and
does not require a shared cross-verb abstraction.

This test re-derives the statement order directly from the live AST on
every run (not a hand-copied line-number pair), so it fails the moment the
two calls are reordered -- proven non-vacuous below in this file's own
history (see the mission fixer's report: a manual local swap-and-restore
against the source produced the expected failure before this file was
committed).
"""

from __future__ import annotations

import ast
import pathlib

import pytest

pytestmark = [pytest.mark.fast]

_DESIGN_PHASE_PY = pathlib.Path(__file__).resolve().parents[3] / "src" / "specify_cli" / "orchestrator_api" / "design_phase.py"

_PREFLIGHT_CALL = "_enforce_analysis_report_write_preflight"
_BODY_READ_CALL = "_read_record_analysis_body"


def _find_function(tree: ast.Module, name: str) -> ast.FunctionDef:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"function {name!r} not found in {_DESIGN_PHASE_PY}")


def _statement_contains_call(stmt: ast.stmt, func_name: str) -> bool:
    return any(isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name) and sub.func.id == func_name for sub in ast.walk(stmt))


def _first_top_level_statement_index_calling(body: list[ast.stmt], func_name: str) -> int:
    for index, stmt in enumerate(body):
        if _statement_contains_call(stmt, func_name):
            return index
    raise AssertionError(
        f"no top-level statement in the function body calls {func_name!r} -- "
        "the guard's premise (both calls exist as direct top-level "
        "statements) no longer holds; re-derive this guard against the "
        "current source instead of trusting this message"
    )


def test_record_analysis_preflight_runs_before_body_read() -> None:
    """PR-CONTRACT-001: the dirty-tree preflight must precede the body read
    as TOP-LEVEL statements in ``record_analysis``'s own body -- re-derived
    from the live AST, not a hardcoded line-number pair that can drift.
    """
    tree = ast.parse(_DESIGN_PHASE_PY.read_text())
    record_analysis = _find_function(tree, "record_analysis")

    preflight_index = _first_top_level_statement_index_calling(record_analysis.body, _PREFLIGHT_CALL)
    body_read_index = _first_top_level_statement_index_calling(record_analysis.body, _BODY_READ_CALL)

    assert preflight_index < body_read_index, (
        f"record_analysis calls {_BODY_READ_CALL!r} (statement #{body_read_index}) "
        f"before {_PREFLIGHT_CALL!r} (statement #{preflight_index}) -- this is "
        "exactly the PR-CONTRACT-001 ordering fork: the dirty-worktree "
        "preflight must run BEFORE the body is read, matching the host "
        "CLI's own mission_record_analysis.record_analysis ordering."
    )
