"""FR-005 startup regression guard, tier 1b: the lazy-import shape in
``register_commands()`` (WP05).

Relocated here from ``tests/performance/`` in WP06 review cycle 2
(WP06-C1-001, severity 4): the deterministic structural half of the two-tier
guard must live in a directory a per-PR CI shard actually selects, per
Ruling 4 (``reviews/spec.ruling.md``) -- ``tests/performance/`` is
nightly-only. This file lives in the top-level ``tests/cli/`` directory,
which is selected by BOTH authorities: ``.github/workflows/ci-router.yml``'s
hardcoded ``tests-cli`` job (``if: needs.changes.outputs.cli == 'true'``,
``uv run --frozen pytest tests/cli -q`` -- no marker filter, so an unmarked
test like this one always runs there) AND the diff-scoped per-PR matrix in
``.github/workflows/ci-modules.yml`` (module-tests.yml) for the ``cli``
module (``.github/ci-module-registry.yml``'s ``cli`` row has no
``test_dirs`` override, so it falls back to the ``tests/{module}`` mirror,
i.e. ``tests/cli`` -- see ``module-tests.yml``'s
"falls back to the tests/{module} mirror" resolution step -- under
``-m "not performance and not stress"``, which this test also satisfies
since it carries neither marker).

Deliberately NOT ``tests/specify_cli/cli/`` (where WP05's own
``test_lazy_command_imports.py`` lives): that directory is not the ``cli``
module's default per-PR mirror and is not what
``ci-router.yml``'s ``tests-cli`` job invokes (``pytest tests/cli -q``, the
literal top-level path).

This is a test-file relocation only (WP06-C1-001's remediation): no CI
workflow, router filter, or module registry edit, staying inside Ruling 4's
"no CI or router changes" bound. The sibling structural half (T020, the
freshness pre-check shape) lives in
``tests/specify_cli/runtime/test_agent_commands_freshness_precheck_shape.py``;
the wall-clock half (T022) stays in
``tests/performance/test_cli_startup_agent_commands_freshness.py``.

WP06-C1-002 (severity 1, resolved here): the original exemption hardcoded
the two pre-existing fast-path predicate FUNCTION NAMES
(``_is_next_fast_path`` / ``_is_live_work_hook_fast_path``) in a frozenset,
so a harmless rename of either predicate would false-positive (the walk
would then descend into that branch and flag its one legitimate
``from . import`` as an offending eager import). This version never reads a
predicate's name at all -- it exempts an ``if`` branch purely by its own
BODY SHAPE: exactly one ``from . import <module>`` statement anywhere in the
branch, and the branch's last statement is an unconditional ``return``. That
is the actual structural signature both narrow fast paths share (each
imports exactly one command module for its own fast-pathed command and
returns immediately after registering it), so it survives any predicate
rename while still refusing to exempt a branch that imports more than one
module (the eager "import everything" shape this guard exists to catch,
even if someone tried to wrap it in a single guarding ``if``).
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.fast]

REPO_ROOT = Path(__file__).resolve().parents[2]
COMMANDS_INIT_PATH = REPO_ROOT / "src" / "specify_cli" / "cli" / "commands" / "__init__.py"


def _find_function(tree: ast.Module, name: str) -> ast.FunctionDef:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"function {name!r} not found")


def _is_relative_command_import(stmt: ast.stmt) -> bool:
    return isinstance(stmt, ast.ImportFrom) and stmt.module is None and stmt.level == 1


def _is_narrow_single_import_branch(if_node: ast.If) -> bool:
    """True when *if_node*'s own branch body imports exactly ONE command
    module and ends in an unconditional ``return`` -- the shared shape of
    both pre-existing narrow fast paths (WP06-C1-002: shape-based, never the
    predicate function's literal name, so a predicate rename cannot break
    this).

    K2 fix: counts imported NAMES, not ``ImportFrom`` *statements*. A single
    statement can import several modules at once (``from . import a as _a,
    b as _b``), and counting statements would misclassify that as a narrow
    one-module fast path -- exempting a branch that actually eager-imports
    two command modules. Both the statement count (exactly one ``from .
    import`` statement) and the alias count on that statement (exactly one
    imported name) must be 1.
    """
    body = if_node.body
    if not body or not isinstance(body[-1], ast.Return):
        return False
    import_stmts = [stmt for stmt in body if _is_relative_command_import(stmt)]
    if len(import_stmts) != 1:
        return False
    (only_import,) = import_stmts
    assert isinstance(only_import, ast.ImportFrom)
    return len(only_import.names) == 1


def _eager_relative_import_lines(func: ast.FunctionDef) -> list[int]:
    """Line numbers of ``from . import <name>`` statements reachable from
    *func*'s EAGER (non-fast-path) branch.

    Walks the function body but does not descend into an ``if`` block whose
    OWN body shape is a narrow single-import-then-return fast path (see
    ``_is_narrow_single_import_branch``) -- those branches keep their own
    single-module import, unrelated to the eager "import everything
    unconditionally" shape WP05 replaced with a lazy lookup table. Renaming
    the predicate the branch's ``if`` test calls does not change what this
    walk finds, because the test expression is never inspected. Reordering
    unrelated statements elsewhere in the function, or renaming local
    variables, does not change what this walk finds either. A branch that
    imports MORE than one module unconditionally -- even if wrapped in some
    guarding ``if`` -- is NOT exempt and is still walked into.
    """
    offending: list[int] = []

    def visit(node: ast.AST) -> None:
        if isinstance(node, ast.If) and _is_narrow_single_import_branch(node):
            # Still walk the `orelse` (elif/else) branch normally -- only the
            # narrow fast-path's own body is exempt.
            for child in node.orelse:
                visit(child)
            return
        if _is_relative_command_import(node):
            offending.append(node.lineno)
        for child in ast.iter_child_nodes(node):
            visit(child)

    for stmt in func.body:
        visit(stmt)
    return offending


def test_register_commands_has_no_eager_top_level_command_imports() -> None:
    """WP05/FR-005 structural guard: ``register_commands()``'s eager branch
    must not ``from . import <command_module>`` unconditionally for every
    command -- that is exactly the shape that forced importing (and thus
    module-scope-executing) every leaf command module on every CLI
    invocation before WP05. The lazy lookup table (``_COMMAND_REGISTRARS`` /
    ``_ALL_COMMAND_REGISTRARS``) each carry their OWN single import, one
    call deep, reached only for the command(s) actually invoked.

    Red-first: confirmed to fail against the merge-base (``6b4164dbf``)
    version of this file, which imports ~45 command modules directly and
    unconditionally inside ``register_commands()``'s own body -- see WP06's
    report for the revert-and-restore transcript.
    """
    tree = ast.parse(COMMANDS_INIT_PATH.read_text(encoding="utf-8"))
    func = _find_function(tree, "register_commands")

    offending = _eager_relative_import_lines(func)

    assert not offending, (
        f"register_commands() eagerly imports command modules at lines {offending} "
        "outside the narrow single-import-then-return fast-path branches -- this "
        "reintroduces the pre-WP05 eager-import-everything shape (#4417)"
    )


def test_eager_import_shape_helper_is_non_vacuous() -> None:
    """The T021 AST helper genuinely flags the pre-WP05 eager-import shape:
    two unconditional, unguarded ``from . import`` statements outside any
    narrow fast-path branch."""
    source = (
        "def register_commands(app):\n"
        "    if _is_next_fast_path(sys.argv):\n"
        "        from . import next_cmd as next_cmd_module\n"
        "        return\n"
        "    from . import accept as accept_module\n"
        "    from . import agent as agent_module\n"
        "    accept_module.register(app)\n"
        "    agent_module.register(app)\n"
    )
    tree = ast.parse(source)
    func = _find_function(tree, "register_commands")
    assert _eager_relative_import_lines(func)


def test_eager_import_shape_helper_accepts_the_real_shape() -> None:
    """Positive control mirroring the real (post-WP05) function structure:
    two narrow fast-path branches (each a single import + trailing return),
    then a lazy single-leaf lookup / full-registrar-loop split with no
    direct imports of its own."""
    source = (
        "def register_commands(app):\n"
        "    if _is_next_fast_path(sys.argv):\n"
        "        from . import next_cmd as next_cmd_module\n"
        "        app.command(name='next')(next_cmd_module.next_step)\n"
        "        return\n"
        "    if _is_live_work_hook_fast_path(sys.argv):\n"
        "        from . import live_work as live_work_module\n"
        "        app.add_typer(live_work_module.app, name='live-work')\n"
        "        return\n"
        "    single_leaf = _resolve_single_leaf_command(sys.argv)\n"
        "    if single_leaf is not None:\n"
        "        _COMMAND_REGISTRARS[single_leaf](app)\n"
        "    else:\n"
        "        for registrar in _ALL_COMMAND_REGISTRARS:\n"
        "            registrar(app)\n"
    )
    tree = ast.parse(source)
    func = _find_function(tree, "register_commands")
    assert _eager_relative_import_lines(func) == []


def test_eager_import_shape_helper_survives_fast_path_predicate_rename() -> None:
    """WP06-C1-002 regression control: renaming a fast-path predicate must
    NOT false-positive its branch's own single, legitimate import -- the
    exemption is shape-based, not name-based."""
    source = (
        "def register_commands(app):\n"
        "    if _is_next_fast_path_renamed_cosmetically(sys.argv):\n"
        "        from . import next_cmd as next_cmd_module\n"
        "        app.command(name='next')(next_cmd_module.next_step)\n"
        "        return\n"
        "    for registrar in _ALL_COMMAND_REGISTRARS:\n"
        "        registrar(app)\n"
    )
    tree = ast.parse(source)
    func = _find_function(tree, "register_commands")
    assert _eager_relative_import_lines(func) == []


def test_eager_import_shape_helper_flags_multi_name_single_statement_import() -> None:
    """K2 regression control: a single ``from . import a as _a, b as _b``
    statement inside a returning branch imports TWO command modules in ONE
    ``ImportFrom`` statement. Counting statements (the pre-fix bug) would
    misclassify this as the narrow one-module fast-path shape and exempt it;
    counting imported names must still flag it as an eager multi-module
    import."""
    source = (
        "def register_commands(app):\n"
        "    if _some_predicate(sys.argv):\n"
        "        from . import accept as _a, agent as _b\n"
        "        _a.register(app)\n"
        "        _b.register(app)\n"
        "        return\n"
    )
    tree = ast.parse(source)
    func = _find_function(tree, "register_commands")
    assert _eager_relative_import_lines(func)


def test_eager_import_shape_helper_still_flags_multi_import_branch_even_when_guarded() -> None:
    """A branch that imports MORE than one module unconditionally is not
    exempt just because it sits inside an ``if`` -- only a narrow
    single-import-then-return shape is exempt."""
    source = (
        "def register_commands(app):\n"
        "    if _some_predicate(sys.argv):\n"
        "        from . import accept as accept_module\n"
        "        from . import agent as agent_module\n"
        "        accept_module.register(app)\n"
        "        agent_module.register(app)\n"
        "        return\n"
    )
    tree = ast.parse(source)
    func = _find_function(tree, "register_commands")
    assert _eager_relative_import_lines(func)
