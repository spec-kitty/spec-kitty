"""FR-005 startup regression guard, tier 1a: the freshness pre-check shape in
``assess_global_agent_commands()`` (WP04).

Relocated here from ``tests/performance/`` in WP06 review cycle 2
(WP06-C1-001, severity 4): the deterministic structural half of the two-tier
guard must live in a directory a per-PR CI shard actually selects, per
Ruling 4 (``reviews/spec.ruling.md``) -- ``tests/performance/`` is nightly-only
(``.github/ci-module-registry.yml`` records the disposition around lines
640-655; ``.github/workflows/ci-router.yml`` has zero path-filters on
``tests/performance``). This file lives in ``tests/specify_cli/runtime/``,
which ``.github/ci-module-registry.yml``'s ``specify_cli_runtime`` module
(``test_dirs: tests/specify_cli/runtime``) selects via the diff-scoped
per-PR matrix in ``.github/workflows/ci-modules.yml`` (module-tests.yml,
``-m "not performance and not stress"``) -- this test carries neither
marker, so it is selected and runs on every PR touching
``src/specify_cli/runtime/**``.

This is a test-file relocation only (WP06-C1-001's remediation): no CI
workflow, router filter, or module registry edit, staying inside Ruling 4's
"no CI or router changes" bound. The wall-clock half (T022) stays in
``tests/performance/test_cli_startup_agent_commands_freshness.py``; the
sibling structural half (T021, register_commands()'s lazy-import shape)
moves to ``tests/cli/test_register_commands_lazy_import_shape.py``.

Modeled on the ``#4409``/``#4417`` precedent's
``test_jsonschema_stays_out_of_module_scope`` AST-based approach (see
``tests/performance/test_cli_startup_budget_4409.py``).
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.fast]

REPO_ROOT = Path(__file__).resolve().parents[3]
AGENT_COMMANDS_PATH = REPO_ROOT / "src" / "specify_cli" / "runtime" / "agent_commands.py"


def _find_function(tree: ast.Module, name: str) -> ast.FunctionDef:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"function {name!r} not found")


def _first_top_level_early_return_line(func: ast.FunctionDef) -> int | None:
    """Line of the first ``if ...: return ...`` DIRECTLY in *func*'s body.

    Scoped to *top-level* statements only -- an early return buried inside a
    nested helper (e.g. the render helper) is not reachable before that
    helper is even called, so it would not actually prove the short-circuit
    property WP04 adds. Renaming the local ``short_circuit`` variable or
    reordering unrelated statements elsewhere in the function does not
    change what this finds.
    """
    for stmt in func.body:
        if isinstance(stmt, ast.If) and any(isinstance(inner, ast.Return) for inner in stmt.body):
            return stmt.lineno
    return None


def _first_call_line(func: ast.FunctionDef, callee_name: str) -> int | None:
    """Line of the first call to *callee_name* anywhere inside *func*,
    including inside a nested function definition (e.g. the render helper
    the freshness check must run before calling)."""
    for node in ast.walk(func):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == callee_name:
            return node.lineno
    return None


def test_freshness_check_precedes_render_call_in_assess_global_agent_commands() -> None:
    """WP04/FR-005 structural guard: the freshness short-circuit's early
    return must sit, textually, before the first ``_render_agent_commands``
    call site inside ``assess_global_agent_commands()`` -- the shape that
    lets a fresh+healthy call return without ever constructing an
    ``AssetPreparation`` (see that function's own docstring, the SK-243
    immunity property). Deleting the early return (reverting WP04) collapses
    this back to the pre-fix "always render" shape.

    Red-first: confirmed to fail against the merge-base (``6b4164dbf``)
    version of this file, which has no ``_freshness_short_circuit`` call and
    no top-level early return before ``_render_agent_commands`` -- see
    WP06's report for the revert-and-restore transcript.
    """
    tree = ast.parse(AGENT_COMMANDS_PATH.read_text(encoding="utf-8"))
    func = _find_function(tree, "assess_global_agent_commands")

    early_return_line = _first_top_level_early_return_line(func)
    render_call_line = _first_call_line(func, "_render_agent_commands")

    assert early_return_line is not None, (
        "assess_global_agent_commands() has no top-level early-return branch -- the freshness short-circuit (WP04) appears to be missing"
    )
    assert render_call_line is not None, (
        "assess_global_agent_commands() never calls _render_agent_commands() -- the precedent shape changed; update this guard alongside it"
    )
    assert early_return_line < render_call_line, (
        f"early-return branch (line {early_return_line}) must precede the "
        f"_render_agent_commands call site (line {render_call_line}) -- a "
        "freshness check that only runs AFTER rendering has already started "
        "defeats the whole point of the short-circuit"
    )


@pytest.mark.parametrize(
    "source",
    (
        # Pre-WP04 shape: no early return anywhere before the nested render call.
        "def assess_global_agent_commands():\n"
        "    def _build():\n"
        "        rendered = _render_agent_commands(key, templates, script_type)\n"
        "        return rendered\n"
        "    return _build()\n",
        # An `if ...: return` exists, but textually AFTER the render call --
        # not an early return relative to rendering, so still non-conforming.
        "def assess_global_agent_commands():\n"
        "    def _build():\n"
        "        rendered = _render_agent_commands(key, templates, script_type)\n"
        "        return rendered\n"
        "    result = _build()\n"
        "    if result is not None:\n"
        "        return result\n"
        "    return None\n",
    ),
)
def test_freshness_check_shape_helper_is_non_vacuous(source: str) -> None:
    """The T020 AST helper genuinely discriminates -- it does not always pass."""
    tree = ast.parse(source)
    func = _find_function(tree, "assess_global_agent_commands")
    early_return_line = _first_top_level_early_return_line(func)
    render_call_line = _first_call_line(func, "_render_agent_commands")
    shaped_correctly = early_return_line is not None and render_call_line is not None and early_return_line < render_call_line
    assert not shaped_correctly


def test_freshness_check_shape_helper_accepts_the_real_shape() -> None:
    """Positive control mirroring the real (post-WP04) function structure."""
    source = (
        "def assess_global_agent_commands():\n"
        "    short_circuit = _freshness_short_circuit()\n"
        "    if short_circuit is not None:\n"
        "        return short_circuit\n"
        "    def _build():\n"
        "        rendered = _render_agent_commands(key, templates, script_type)\n"
        "        return rendered\n"
        "    return _build()\n"
    )
    tree = ast.parse(source)
    func = _find_function(tree, "assess_global_agent_commands")
    early_return_line = _first_top_level_early_return_line(func)
    render_call_line = _first_call_line(func, "_render_agent_commands")
    assert early_return_line is not None
    assert render_call_line is not None
    assert early_return_line < render_call_line
