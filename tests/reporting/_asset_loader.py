"""Shared loader for the debrief scripts, which are internal-pack assets.

Their file names are hyphenated, so they are loaded by path rather than imported
as a package.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

DEBRIEF_ASSET_DIR = Path(__file__).resolve().parents[2] / "packs" / "internal" / "assets" / "debrief"


def load_asset(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module
