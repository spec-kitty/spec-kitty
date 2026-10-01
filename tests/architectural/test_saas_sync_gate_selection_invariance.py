"""``SPEC_KITTY_ENABLE_SAAS_SYNC`` is a single collection-time authority.

**Live premise (post-#3980).** Product still reads
``SPEC_KITTY_ENABLE_SAAS_SYNC`` at *runtime* as a process-global opt-out kill
switch (``src/specify_cli/core/saas_sync_config.py:28``,
``src/specify_cli/tracker/saas_readiness.py``). A module-level write of that
flag — e.g. ``os.environ["SPEC_KITTY_ENABLE_SAAS_SYNC"] = "0"`` at import time
— therefore pollutes every later test in the same worker process, whatever
selection collected that module: the flag is a process-wide variable, not a
test-scoped one, so the pollution outlives the module that set it and reaches
tests that never asked for it. No other gate in this suite bans a module-scope
env write in ``tests/``, so retiring this one would remove the only guard
against that class of pollution (C-002).

**History.** The flag was originally gated here against import-time
``@pytest.mark.skipif(not os.environ.get("SPEC_KITTY_ENABLE_SAAS_SYNC"))``
selection-dependence (#3213): such gates are evaluated at *collection*, so a
module setting the flag at import via its own module-level
``os.environ.setdefault(...)`` made the gate's decision depend on whether that
module happened to be collected in the current selection — the SAME node
skipped under ``pytest tests/regression`` but ran under ``pytest tests/ -m
regression``. Zero such import-time ``skipif`` gates remain in this codebase
today; the premise above is what makes this guard still load-bearing.

The fix makes ``tests/conftest.py``'s ``pytest_configure`` the single authority
that sets the flag once, collection-wide, before any module import. These two
guards pin that authority:

1. the flag IS set at collection time (so any runtime reader, including the
   opt-out kill switch above, sees a stable value);
2. NO test module re-introduces a module-level write of the flag (which would
   restore the cross-test pollution).

Note: with the flag consistently set, every runtime reader of it makes the
same decision under ``pytest tests/regression`` and ``pytest tests/ -m
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
    """``pytest_configure`` sets the flag before any module import, so the
    runtime kill-switch readers (``saas_sync_config.py``,
    ``saas_readiness.py``) see a consistent value regardless of collection
    order (history: #3213)."""
    import os

    assert os.environ.get(_FLAG) == "1", (
        f"{_FLAG} must be set collection-wide by tests/conftest.py "
        "pytest_configure, or the runtime kill-switch readers see an "
        "inconsistent value depending on collection order."
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
    """Only tests/conftest.py may set the flag; a module-level write pollutes
    every later test in the same worker process via the runtime kill-switch
    readers (history: #3213 was the selection-dependence precursor)."""
    offenders = _module_level_flag_writers()
    assert not offenders, (
        f"These test modules set {_FLAG} at import time, which pollutes every "
        "later test in the same worker process via the runtime kill-switch "
        "readers in saas_sync_config.py / saas_readiness.py. Remove the "
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
