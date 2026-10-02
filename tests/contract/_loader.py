"""Load a ``contracts/tools`` script by path, without hand-mutating process-global state.

Every contract-tool test module loads its script with ``importlib`` (the tools are
not an importable package). The ``sys.path`` and ``sys.modules`` changes that needs go
through a ``pytest.MonkeyPatch`` the caller owns, so they are undone with it.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest


def load_tool(mp: pytest.MonkeyPatch, script: Path, module_name: str, *, syspath: Path | None = None) -> ModuleType:
    """Execute ``script`` as ``module_name`` and register it in ``sys.modules`` through ``mp``.

    ``syspath`` is prepended to ``sys.path`` (through ``mp``) for scripts that import their sibling
    modules by name. It stays until ``mp`` is undone, so lazy sibling imports still resolve.
    """
    if syspath is not None:
        mp.syspath_prepend(str(syspath))
    spec = importlib.util.spec_from_file_location(module_name, script)
    assert spec is not None and spec.loader is not None, f"cannot load {script}"
    module = importlib.util.module_from_spec(spec)
    mp.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    return module
