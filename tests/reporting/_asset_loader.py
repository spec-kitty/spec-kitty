"""Shared loader for the debrief scripts, which are internal-pack assets.

Each script is found the way ``spec-kitty charter pack asset path <id>`` finds it: through the
``path:`` of its ``*.asset.yaml`` sidecar, relative to ``packs/internal/assets/``. A wrong
``path:`` in a sidecar therefore fails the tests that load the script. The file names are
hyphenated, so the script is loaded by path rather than imported as a package.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

from ruamel.yaml import YAML

ASSETS_ROOT = Path(__file__).resolve().parents[2] / "packs" / "internal" / "assets"


def asset_path(asset_id: str) -> Path:
    """Return the file the sidecar registering *asset_id* points at, and require it to exist."""
    yaml = YAML(typ="safe")
    for sidecar in sorted(ASSETS_ROOT.rglob("*.asset.yaml")):
        record = yaml.load(sidecar.read_text(encoding="utf-8"))
        if record["id"] == asset_id:
            resolved = ASSETS_ROOT / record["path"]
            assert resolved.is_file(), f"{sidecar.name}: path {record['path']!r} is not a file under assets/"
            return resolved
    raise AssertionError(f"no asset sidecar registers id {asset_id!r}")


def load_asset(name: str, asset_id: str) -> ModuleType:
    """Execute the script registered as *asset_id* as module *name* without registering it in ``sys.modules``."""
    spec = importlib.util.spec_from_file_location(name, asset_path(asset_id))
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
