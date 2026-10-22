"""#4124 regression — a corrupt ``.pyc`` in ``upgrade/migrations`` must not crash CLI startup.

Field symptom (Windows training machine, 2026-09-09): an interrupted
``uv tool install`` left a truncated ``base.cpython-*.pyc``; every
``spec-kitty`` command — including ``dashboard`` — died at app assembly with
``AttributeError: 'bytes' object has no attribute 'co_filename'`` /
``ValueError: bad marshal data`` before any command ran, because
``cli/commands/upgrade.py`` imports ``specify_cli.upgrade.runner`` ->
``upgrade.migrations.base`` at module level.

The regression runs against an isolated copy of ``src/`` (PYTHONPATH-first,
so it shadows the editable install) so the shared checkout's ``__pycache__``
is never corrupted for parallel workers.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

# The tests and helpers shared with this suite's always-on lift live once, in
# ``tests/architectural/_lifted_cli_bytecode_heal_startup.py`` (#5015); importing a test is what makes pytest collect it here.
from tests.architectural._lifted_cli_bytecode_heal_startup import (
    _REPO_SRC,
    _MIGRATIONS_CACHE,
    _cli_env,
)
from tests.architectural._lifted_cli_bytecode_heal_startup import (
    test_corrupt_migrations_pyc_does_not_crash_startup as test_corrupt_migrations_pyc_does_not_crash_startup,
)

pytestmark = [pytest.mark.integration, pytest.mark.non_sandbox, pytest.mark.regression]

# A module only ``auto_discover_migrations`` imports (never pulled in by app
# assembly), so corrupting its cache isolates the discovery walk itself.
_DISCOVERY_ONLY_MODULE = "m_0_10_0_python_only"


def _run(copy_src: Path, home: Path, code: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=cwd,
        env=_cli_env(copy_src, home),
        text=True,
        capture_output=True,
        timeout=180,
    )


def _expected_migration_count(copy_src: Path) -> int:
    """One registered migration per ``m_*.py`` module is discovery's contract."""
    return len(list((copy_src / "specify_cli" / "upgrade" / "migrations").glob("m_*.py")))


def _corrupt_discovery_only_module_pyc(copy_src: Path) -> tuple[Path, bytes]:
    """Warm then truncate the ``.pyc`` of a module only discovery imports."""
    pycs = list((copy_src / _MIGRATIONS_CACHE).glob(f"{_DISCOVERY_ONLY_MODULE}.*.pyc"))
    assert len(pycs) == 1, f"expected exactly one {_DISCOVERY_ONLY_MODULE}.*.pyc, found {pycs}"
    data = pycs[0].read_bytes()
    pycs[0].write_bytes(data[:20] + b"\x00" * 42)
    return pycs[0], pycs[0].read_bytes()


def test_corrupt_discovery_only_pyc_heals_through_planner_seam(tmp_path: Path) -> None:
    """A corrupt ``.pyc`` in a module only ``auto_discover_migrations`` imports heals.

    Discovery launders every per-module import failure into one fresh
    ``MigrationDiscoveryError``; pre-#4124-fix that wrapper carried no
    ``__cause__``, so the heal wired into ``_ensure_registry_loaded`` could
    never fire for 112 of the 113 modules discovery imports — the registry
    degraded loudly instead of loading. This drives the REAL discovery walk
    (no stand-in): the seam must purge, retry, and load every migration.
    """
    copy_src = tmp_path / "src"
    shutil.copytree(_REPO_SRC, copy_src, ignore=shutil.ignore_patterns("__pycache__"))
    home = tmp_path / "home"
    home.mkdir()

    warm = _run(
        copy_src,
        home,
        f"import specify_cli.upgrade.migrations.{_DISCOVERY_ONLY_MODULE}",
        tmp_path,
    )
    assert warm.returncode == 0, warm.stderr
    pyc, corrupt_bytes = _corrupt_discovery_only_module_pyc(copy_src)

    result = _run(
        copy_src,
        home,
        "import logging, sys\n"
        "logging.basicConfig(level=logging.WARNING, format='%(message)s', stream=sys.stderr)\n"
        "from specify_cli.compat import planner\n"
        "planner._ensure_registry_loaded()\n"
        "from specify_cli.upgrade.registry import MigrationRegistry\n"
        "print('REGISTERED:', len(MigrationRegistry._migrations))\n",
        tmp_path,
    )

    assert result.returncode == 0, result.stderr
    assert "upgrade migrations unavailable" not in result.stderr  # healed, not degraded
    assert "repaired" in result.stderr
    expected = _expected_migration_count(copy_src)
    assert f"REGISTERED: {expected}" in result.stdout
    assert pyc.read_bytes() != corrupt_bytes  # the corrupt cache was recompiled


def test_corrupt_discovery_only_pyc_heals_through_upgrade_seam(tmp_path: Path) -> None:
    """The ``spec-kitty upgrade`` load seam heals the same corrupt-``.pyc`` discovery failure.

    Same shape as the planner test, but through
    ``_load_upgrade_system_with_heal``: the heal must fire through the
    laundered ``MigrationDiscoveryError``, print what was repaired, and
    return a fully loaded upgrade system.
    """
    copy_src = tmp_path / "src"
    shutil.copytree(_REPO_SRC, copy_src, ignore=shutil.ignore_patterns("__pycache__"))
    home = tmp_path / "home"
    home.mkdir()

    warm = _run(
        copy_src,
        home,
        f"import specify_cli.upgrade.migrations.{_DISCOVERY_ONLY_MODULE}",
        tmp_path,
    )
    assert warm.returncode == 0, warm.stderr
    pyc, corrupt_bytes = _corrupt_discovery_only_module_pyc(copy_src)

    result = _run(
        copy_src,
        home,
        "from specify_cli.cli.commands.upgrade import _load_upgrade_system_with_heal\n"
        "_load_upgrade_system_with_heal()\n"
        "from specify_cli.upgrade.registry import MigrationRegistry\n"
        "print('REGISTERED:', len(MigrationRegistry._migrations))\n",
        tmp_path,
    )

    assert result.returncode == 0, result.stderr
    assert "Repaired" in result.stdout  # the operator is told what was repaired
    expected = _expected_migration_count(copy_src)
    assert f"REGISTERED: {expected}" in result.stdout
    assert pyc.read_bytes() != corrupt_bytes
