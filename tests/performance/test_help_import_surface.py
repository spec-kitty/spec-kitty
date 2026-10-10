"""#5991 / FR-010: ``next_cmd`` must not eagerly import the ``next`` runtime stack.

``next_cmd`` once imported ``runtime.next.decision`` and friends at module
scope, dragging ``charter.activation``, the runtime schema and the status
duplicate-key repair onto every ``--help`` (about 230 ms).

The full ``--help`` eager-import shave is deferred to #5999 (follow-up to
#5991); this test guards ``next_cmd.py``'s own import surface only. Other
modules (``runtime/next/run_index.py``, ``init.py``, ``status/__init__.py``)
still pull the same chains, so the whole-app check is an ``xfail`` below.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from tests._perf_helpers import cli_argv

pytestmark = [pytest.mark.fast]

REPO_ROOT = Path(__file__).resolve().parents[2]
_HELP_MODULE = "specify_cli.__init__"

#: Modules that only the ``next`` command bodies need.
FORBIDDEN_ON_HELP: tuple[str, ...] = (
    "charter.activation",
    "runtime.next._internal_runtime.schema",
    "runtime.next.decision",
    "status.dup_key_repair",
)

#: Child program: record every ``import`` statement executed by ``next_cmd``'s
#: module body. Recording the *statement* (not whether the module loaded) keeps
#: the check independent of what other modules already put in ``sys.modules``.
_PROBE = r"""
import builtins, json, sys
module_scope = []
real_import = builtins.__import__

def hook(name, globals=None, locals=None, fromlist=(), level=0):
    if globals is not None and globals.get("__name__") == "specify_cli.cli.commands.next_cmd":
        frame = sys._getframe(1)
        if frame.f_code.co_name == "<module>":
            module_scope.append(name)
    return real_import(name, globals, locals, fromlist, level)

builtins.__import__ = hook
import specify_cli.cli.commands.next_cmd  # noqa: F401
print(json.dumps({"loaded": "specify_cli.cli.commands.next_cmd" in sys.modules, "module_scope": module_scope}))
"""


def _is_forbidden(name: str) -> bool:
    return any(name == f or name.startswith(f + ".") or name.endswith("." + f) for f in FORBIDDEN_ON_HELP)


def _env() -> dict[str, str]:
    """This checkout's own ``src/`` first, so the code under test is this tree."""
    return {**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")}


def _next_cmd_module_scope_imports() -> list[str]:
    proc = subprocess.run([sys.executable, "-c", _PROBE], cwd=REPO_ROOT, env=_env(), capture_output=True, text=True, check=False, timeout=120)
    assert proc.returncode == 0, proc.stderr[-2000:]
    report = json.loads(proc.stdout.strip().splitlines()[-1])
    assert report["loaded"], "next_cmd was not imported: the control is vacuous"
    names: list[str] = report["module_scope"]
    assert "typer" in names, "probe saw no module-scope import in next_cmd: the control is vacuous"
    return names


def test_next_cmd_defers_next_runtime_stack() -> None:
    leaked = sorted({n for n in _next_cmd_module_scope_imports() if _is_forbidden(n)})
    assert not leaked, f"next_cmd imports at module scope: {leaked}"


def _imported_modules_on_help() -> set[str]:
    """Module names imported by ``python -m specify_cli --help`` (``-X importtime``)."""
    argv = [sys.executable, "-X", "importtime", *cli_argv("--help", module=_HELP_MODULE)[1:]]
    proc = subprocess.run(argv, cwd=REPO_ROOT, env=_env(), capture_output=True, text=True, check=False, timeout=120)
    assert proc.returncode == 0, proc.stderr[-2000:]
    return {line.rsplit("|", 1)[1].strip() for line in proc.stderr.splitlines() if line.startswith("import time:") and "|" in line}


@pytest.mark.xfail(reason="full --help shave tracked in #5999", strict=False)
def test_help_does_not_import_next_runtime_stack() -> None:
    # Whole-app acceptance for #5999: other modules still pull these chains.
    imported = _imported_modules_on_help()
    assert "specify_cli.cli.commands.next_cmd" in imported
    leaked = sorted(n for n in imported if any(n == f or n.startswith(f + ".") for f in FORBIDDEN_ON_HELP))
    assert not leaked, f"--help eagerly imports: {leaked}"
