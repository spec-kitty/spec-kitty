"""Every module split out of ``consolidation/reconciliation.py`` imports cleanly when it is the FIRST of the family to load.

The split modules look names up in each other (and, for the temporary forward references, in the facade). A
module-level import cycle only shows when the cycle is entered from the right module, so a fresh interpreter
loads the package once, then for each module in turn drops every ``reconciliation*`` module from ``sys.modules``,
imports that module first and the facade second. A bogus module name is the control: the harness must report it.
"""

from __future__ import annotations

import functools
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.fast

_REPO_ROOT = Path(__file__).resolve().parents[2]
_PACKAGE = "specify_cli.consolidation"
# One entry per module split out of reconciliation.py; each work package of the split appends its modules here.
SPLIT_MODULES: tuple[str, ...] = (
    "reconciliation_kernel",
    "reconciliation_claim_types",
    "reconciliation_rendering",
    "reconciliation_closed_world",
    "reconciliation_bound",
    "reconciliation_verifier",
)
_BOGUS = "reconciliation_this_module_does_not_exist"
_DRIVER = """
import importlib, sys
prefix = "specify_cli.consolidation.reconciliation"
import specify_cli.consolidation
for dotted in sys.argv[1:]:
    for key in [k for k in sys.modules if k == prefix or k.startswith(prefix + "_")]:
        del sys.modules[key]
    try:
        importlib.import_module(dotted)
        importlib.import_module(prefix)
        print("OK", dotted)
    except Exception as exc:
        print("FAIL", dotted, type(exc).__name__, exc)
"""


@functools.cache
def _entry_first_results() -> dict[str, str]:
    modules = [f"{_PACKAGE}.{name}" for name in (*SPLIT_MODULES, _BOGUS)]
    run = subprocess.run([sys.executable, "-c", _DRIVER, *modules], capture_output=True, text=True, check=False, cwd=_REPO_ROOT)
    assert run.returncode == 0, run.stderr[-2000:]
    return {line.split()[1].rsplit(".", 1)[1]: line for line in run.stdout.splitlines() if line.startswith(("OK ", "FAIL "))}


@pytest.mark.parametrize("module", SPLIT_MODULES)
def test_split_module_imports_first_in_a_fresh_interpreter(module: str) -> None:
    assert _entry_first_results()[module].startswith("OK "), _entry_first_results()[module]


def test_entry_first_harness_reports_a_broken_module() -> None:
    assert _entry_first_results()[_BOGUS].startswith("FAIL "), _entry_first_results()[_BOGUS]
