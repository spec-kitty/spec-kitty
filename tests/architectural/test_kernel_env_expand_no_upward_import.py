"""C-EXP-5: ``kernel.env_expand`` holds no doctrine-/specify_cli-identifying
vocabulary (WP01 T005).

Mirrors ``test_kernel_no_charter_offering_import.py``'s full-AST walk (module-level
imports, in-function imports, and string-literal/f-string occurrences), but
scoped to the single new WP01 module rather than the whole ``src/kernel/``
tree, so this test's own failure message is unambiguous about which file
regressed.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.architectural.test_kernel_no_charter_offering_import import (
    _FORBIDDEN_IMPORT_ROOTS,
    collect_forbidden_vocabulary,
)

pytestmark = pytest.mark.architectural

_ENV_EXPAND_MODULE = Path(__file__).resolve().parents[2] / "src" / "kernel" / "env_expand.py"


def test_env_expand_holds_no_charter_or_specify_cli_vocabulary() -> None:
    """``kernel/env_expand.py`` must import nothing from ``specify_cli``/``doctrine``.

    Reuses the exact walker ``test_kernel_no_charter_offering_import.py`` proves
    non-vacuous (import statements, in-function imports, string-literal and
    f-string components; docstrings excluded by position).
    """
    violations = collect_forbidden_vocabulary(_ENV_EXPAND_MODULE.parent, relative_to=_ENV_EXPAND_MODULE.parent)
    module_violations = [v for v in violations if v[0] == _ENV_EXPAND_MODULE.name]

    assert module_violations == [], (
        "kernel/env_expand.py must hold no doctrine-/specify_cli-identifying "
        "string or import vocabulary (C-EXP-5).\nViolations:\n"
        + "\n".join(f"  {rel}:{lineno} — {detail}" for rel, lineno, detail in module_violations)
    )


def test_env_expand_module_actually_exists_and_is_scanned() -> None:
    """Non-vacuity: the module under test is real and is part of the scanned tree."""
    assert _ENV_EXPAND_MODULE.is_file()


def test_env_expand_imports_only_kernel_paths_and_stdlib() -> None:
    """Direct check on ``env_expand``'s own import statements (belt-and-braces).

    ``kernel.paths`` is the one intra-kernel import permitted by T002
    ("Stdlib + kernel.paths only"); every ``ast.Import``/``ast.ImportFrom``
    module root must be either stdlib or ``kernel`` itself -- never a
    forbidden upward root.
    """
    import ast

    tree = ast.parse(_ENV_EXPAND_MODULE.read_text(encoding="utf-8"))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".", 1)[0])

    assert roots & _FORBIDDEN_IMPORT_ROOTS == set()
    assert roots <= {"os", "re", "collections", "kernel", "__future__"}
