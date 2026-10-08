"""Migration discovery survives the modules the charter-pack cutover deletes (#3732, WP10 T052).

``auto_discover_migrations()`` raises ``MigrationDiscoveryError`` on any
``ImportError`` in an ``m_*.py`` module, which blocks every upgrade. Each check
runs in a fresh interpreter whose ``sys.meta_path`` refuses the retired
modules, so a module-level import of one of them is visible.
"""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit]

#: Modules the mission deletes that no migration may import at module level.
#: Later work packages extend this list as they delete modules.
RETIRED_MODULES: tuple[str, ...] = ("specify_cli.charter_pack_registry",)

_HARNESS = textwrap.dedent(
    """
    import importlib.abc
    import json
    import sys

    BLOCKED = tuple(json.loads(sys.argv[1]))
    PLANTED = sys.argv[2]


    class RetiredModuleFinder(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if fullname in BLOCKED:
                raise ModuleNotFoundError(f"No module named {fullname!r}", name=fullname)
            return None


    sys.meta_path.insert(0, RetiredModuleFinder())

    import specify_cli.upgrade.migrations as migrations
    from specify_cli.upgrade.registry import MigrationRegistry

    if PLANTED:
        # Discovery scans the package directory itself; list the planted
        # directory too and let the package import from it.
        import pkgutil

        migrations.__path__.append(PLANTED)
        _iter_modules = pkgutil.iter_modules
        pkgutil.iter_modules = lambda paths=None, prefix="": _iter_modules([*(paths or []), PLANTED], prefix)

    MigrationRegistry.clear()
    try:
        migrations.auto_discover_migrations()
    except migrations.MigrationDiscoveryError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
    else:
        print(json.dumps({"ok": True, "ids": sorted(MigrationRegistry._migrations)}))
    """
)


def _discover(planted_dir: Path | None = None) -> dict[str, object]:
    completed = subprocess.run(
        [sys.executable, "-c", _HARNESS, json.dumps(RETIRED_MODULES), str(planted_dir or "")],
        capture_output=True,
        text=True,
        check=True,
        timeout=300,
    )
    outcome: dict[str, object] = json.loads(completed.stdout.strip().splitlines()[-1])
    return outcome


def test_discovery_succeeds_without_retired_modules() -> None:
    outcome = _discover()

    assert outcome["ok"] is True, outcome
    ids = outcome["ids"]
    assert isinstance(ids, list)
    assert "3.2.0rc35_default_charter_pack" in ids
    assert "normalize_activation_absence" in ids


def test_harness_sees_a_module_level_import_of_a_retired_module(tmp_path: Path) -> None:
    """Planted self-test: a migration importing a blocked module fails discovery."""
    planted = tmp_path / "m_planted_retired_import.py"
    planted.write_text(f"import {RETIRED_MODULES[0]}  # noqa: F401\n", encoding="utf-8")

    outcome = _discover(tmp_path)

    assert outcome["ok"] is False, outcome
    assert "m_planted_retired_import" in str(outcome["error"])
