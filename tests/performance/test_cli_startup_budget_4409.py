"""#4409: `spec-kitty --help` must not re-acquire its import-time tax.

Before this guard, a bare ``--help`` cost ~3.2 s while importing the package
itself cost ~0.2 s. Almost all of the difference was one transitive import:
``jsonschema`` eagerly loads its format checkers, and one of those
(``rfc3987_syntax.syntax_helpers``, which builds a Lark grammar at import
time) costs ~1.8 s on its own. Eight modules imported ``jsonschema`` at module
scope, so whichever the CLI touched first paid for all of them — on a path
that validates nothing.

Deferring those imports to their single call sites took ``--help`` to ~1.0 s.
The tax is easy to reintroduce by accident: one ``import jsonschema`` at the
top of a module the CLI imports is enough. This test is the ratchet.

It lives in the ``performance`` lane (nightly) rather than the per-PR gate —
wall-clock budgets are environment-sensitive, and a shared runner under load
should not turn a green change red. The structural half of the guard (no
module-scope ``jsonschema`` import in the CLI's import graph) is cheap and
deterministic, so that half runs everywhere.
"""

from __future__ import annotations

import ast
import subprocess
import sys
import time
from pathlib import Path

import pytest

from tests._perf_helpers import assert_timing_budget

REPO_ROOT = Path(__file__).resolve().parents[2]

#: Generous enough to absorb a loaded laptop or CI runner, tight enough to
#: catch the ~1.8 s regression this issue removed (pre-fix was ~3.2 s).
_HELP_BUDGET_SECONDS = 2.5


def _module_scope_jsonschema_imports(source: str) -> list[int]:
    """Return line numbers importing jsonschema outside deferred call sites."""
    offending: list[int] = []

    def visit(node: ast.AST) -> None:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            return
        is_jsonschema_import = (
            isinstance(node, ast.Import) and any(alias.name == "jsonschema" or alias.name.startswith("jsonschema.") for alias in node.names)
        ) or (isinstance(node, ast.ImportFrom) and node.module is not None and (node.module == "jsonschema" or node.module.startswith("jsonschema.")))
        if is_jsonschema_import:
            offending.append(node.lineno)
        for child in ast.iter_child_nodes(node):
            visit(child)

    visit(ast.parse(source))
    return offending


def test_jsonschema_stays_out_of_module_scope() -> None:
    """The structural half scans every source module, not a hand-picked list.

    A module-scope ``import jsonschema`` anywhere in the CLI source tree can
    reintroduce the whole format-checker chain for every CLI invocation.
    """
    offending = {
        path.relative_to(REPO_ROOT).as_posix(): lines
        for path in sorted((REPO_ROOT / "src").rglob("*.py"))
        if (lines := _module_scope_jsonschema_imports(path.read_text(encoding="utf-8")))
    }

    assert not offending, (
        f"#4409: source modules import jsonschema at module scope ({offending}). "
        "That pulls jsonschema._format -> rfc3987_syntax (~1.8s) into every "
        "`spec-kitty` invocation. Import it inside the function that validates."
    )


@pytest.mark.parametrize(
    "source",
    (
        "try:\n    import jsonschema\nexcept ImportError:\n    pass\n",
        "from typing import TYPE_CHECKING\nif TYPE_CHECKING:\n    from jsonschema import validate\n",
        "class Validator:\n    import jsonschema\n",
    ),
)
def test_indented_module_scope_jsonschema_import_is_detected(source: str) -> None:
    """The structural guard remains non-vacuous for indented module blocks."""
    assert _module_scope_jsonschema_imports(source)


def test_function_local_jsonschema_import_is_allowed() -> None:
    """Deferred call-site imports are the intended fast-startup pattern."""
    assert _module_scope_jsonschema_imports("def validate():\n    import jsonschema\n") == []


@pytest.mark.performance
def test_help_stays_inside_its_startup_budget() -> None:
    """The wall-clock half: nightly-only, measured through the real entry point."""
    started = time.monotonic()
    completed = subprocess.run(
        [sys.executable, "-m", "specify_cli.__init__", "--help"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )
    elapsed = time.monotonic() - started

    measured = elapsed if completed.returncode == 0 else float("inf")
    name = "spec-kitty --help startup"
    if completed.returncode != 0:
        name = f"{name}; exit={completed.returncode}; stderr={completed.stderr[-2000:]}"
    assert_timing_budget(measured, _HELP_BUDGET_SECONDS, name=name)
