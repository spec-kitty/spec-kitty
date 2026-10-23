"""Seed a test project's ``.kittify/missions/`` with the canonical mission templates (#5280).

The fixtures used to ``copytree`` ``src/specify_cli/missions`` wholesale. Its
``documentation``/``research`` ``templates/`` are frozen, migration-only forks
(``tests/runtime/test_frozen_migration_template_sources.py``), so a test project
seeded from them would carry stale templates. This helper keeps the same tree
shape (every live ``mission.yaml``) but takes those two ``templates/`` trees from
the packs copy (``get_package_asset_root()``).

Kept out of ``tests/conftest.py`` for the reason ``fixture_pollution`` gives: that
module's top-level definitions are frozen by an architectural gate.
"""

from __future__ import annotations

import shutil
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
LIVE_MISSIONS = REPO_ROOT / "src" / "specify_cli" / "missions"
#: Mission types whose ``templates/`` under :data:`LIVE_MISSIONS` are frozen forks.
FROZEN_TEMPLATE_TYPES: tuple[str, ...] = ("documentation", "research")


def _skip_frozen_templates(directory: str, names: list[str]) -> set[str]:
    if Path(directory).resolve().parent == LIVE_MISSIONS and Path(directory).name in FROZEN_TEMPLATE_TYPES:
        return {"templates"} & set(names)
    return set()


def copy_builtin_missions(dest: Path) -> None:
    """Copy the built-in missions to *dest*, with the packs copies of the frozen templates."""
    # Lazy: this module is imported by ``tests/conftest.py`` before the worker
    # home isolation is in place, so it must not import ``specify_cli`` eagerly.
    from specify_cli.runtime.home import get_package_asset_root  # noqa: PLC0415

    shutil.copytree(LIVE_MISSIONS, dest, ignore=_skip_frozen_templates)
    for mission_type in FROZEN_TEMPLATE_TYPES:
        shutil.copytree(get_package_asset_root() / mission_type / "templates", dest / mission_type / "templates")
