"""#3213 — the SaaS-sync feature flag is a single collection-time authority.

Import-time ``@pytest.mark.skipif(not os.environ.get("SPEC_KITTY_ENABLE_SAAS_SYNC"))``
gates are evaluated at *collection*. If any test
module sets that flag at import via its own module-level
``os.environ.setdefault(...)``, the gate's decision depends on whether that
module happens to be collected in the current selection — so the SAME node
skips under ``pytest tests/regression`` but runs under ``pytest tests/ -m
regression``. That selection-dependence is the #3213 defect.

The fix makes ``tests/conftest.py``'s ``pytest_configure`` the single authority
that sets the flag once, collection-wide, before any module import. These two
guards pin that authority:

1. the flag IS set at collection time (so import-time gates see a stable value);
2. NO test module re-introduces a module-level write of the flag (which would
   restore the selection-dependence).

Note: with the flag consistently set, every import-time SaaS-sync gate makes the
same skip/run decision under ``pytest tests/regression`` and ``pytest tests/ -m
regression`` — that is the intended, honest effect. (Historically this also
re-exposed the then-open #2782 P0 red under ``pytest tests/regression``; #2782
has since been resolved and its reproduction retired, so nothing in
``tests/regression`` is red today.)
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from tests.architectural._ast_scan import parse_file

pytestmark = [pytest.mark.architectural, pytest.mark.unit]

_FLAG = "SPEC_KITTY_ENABLE_SAAS_SYNC"
_TESTS_ROOT = Path(__file__).resolve().parents[1]
#: The single sanctioned authority that sets the flag collection-wide: the ROOT
#: tests/conftest.py only. A NESTED conftest.py writing the flag would apply to
#: its subtree alone -- reintroducing the exact selection-dependence this guards
#: against -- so it is NOT exempt.
_ALLOWED_RELPATHS = {Path("conftest.py")}


def test_flag_is_set_at_collection_time() -> None:
    """``pytest_configure`` set the flag before any module import (#3213)."""
    import os

    assert os.environ.get(_FLAG) == "1", (
        f"{_FLAG} must be set collection-wide by tests/conftest.py "
        "pytest_configure so import-time skipif gates are selection-invariant."
    )


def _module_level_flag_writers() -> list[str]:
    """Test files that write ``SPEC_KITTY_ENABLE_SAAS_SYNC`` at module scope.

    AST-based (not a text grep) so comments and string literals mentioning the
    flag do not count — only real module-level ``os.environ[...] = ...`` /
    ``os.environ.setdefault(...)`` statements do.
    """
    offenders: list[str] = []
    for path in _TESTS_ROOT.rglob("*.py"):
        if path.relative_to(_TESTS_ROOT) in _ALLOWED_RELPATHS:
            continue
        tree = parse_file(path)
        for node in tree.body:  # module scope only — nested (in-test) writes are fine
            if _statement_writes_flag(node):
                offenders.append(str(path.relative_to(_TESTS_ROOT)))
                break
    return offenders


def _statement_writes_flag(node: ast.stmt) -> bool:
    if isinstance(node, ast.Assign):
        return any(_is_environ_subscript_of_flag(t) for t in node.targets)
    if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
        return _is_environ_setdefault_of_flag(node.value)
    return False


def _is_environ_subscript_of_flag(target: ast.expr) -> bool:
    # os.environ["SPEC_KITTY_ENABLE_SAAS_SYNC"] = ...
    return (
        isinstance(target, ast.Subscript)
        and _is_os_environ(target.value)
        and _is_flag_constant(target.slice)
    )


def _is_environ_setdefault_of_flag(call: ast.Call) -> bool:
    # os.environ.setdefault("SPEC_KITTY_ENABLE_SAAS_SYNC", ...)
    func = call.func
    return (
        isinstance(func, ast.Attribute)
        and func.attr == "setdefault"
        and _is_os_environ(func.value)
        and bool(call.args)
        and _is_flag_constant(call.args[0])
    )


def _is_os_environ(expr: ast.expr) -> bool:
    return (
        isinstance(expr, ast.Attribute)
        and expr.attr == "environ"
        and isinstance(expr.value, ast.Name)
        and expr.value.id == "os"
    )


def _is_flag_constant(expr: ast.expr) -> bool:
    return isinstance(expr, ast.Constant) and expr.value == _FLAG


def test_no_test_module_sets_the_flag_at_import_time() -> None:
    """Only tests/conftest.py may set the flag; module-level writes bring back
    the #3213 selection-dependence."""
    offenders = _module_level_flag_writers()
    assert not offenders, (
        f"These test modules set {_FLAG} at import time, which makes import-time "
        "skipif gates depend on the current selection (#3213). Remove the "
        "module-level write; the flag is set collection-wide in "
        "tests/conftest.py pytest_configure:\n"
        + "\n".join(f"    - {o}" for o in sorted(offenders))
    )


def test_scan_is_not_vacuous() -> None:
    """The AST scan actually detects a module-level flag write (bite proof)."""
    sample = f'import os\nos.environ.setdefault("{_FLAG}", "1")\n'
    tree = ast.parse(sample)
    assert any(_statement_writes_flag(node) for node in tree.body)
    # ...and does NOT flag a nested (in-function) write or a mere mention.
    nested = f'import os\ndef f():\n    os.environ["{_FLAG}"] = "1"\n'
    assert not any(_statement_writes_flag(node) for node in ast.parse(nested).body)
