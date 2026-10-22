"""Single home of the corrupt-migrations-pyc startup heal test (#5015).

``tests/specify_cli/cli/test_bytecode_heal_startup.py`` (out of matrix) and its always-on lift
``tests/architectural/test_lifted_cli_bytecode_heal_startup.py`` both import these, so the per-PR gate runs
exactly what the source suite runs and the two cannot drift apart.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

_REPO_SRC = Path(__file__).resolve().parents[2] / "src"


_REPO_PACKS = Path(__file__).resolve().parents[2] / "packs"


_MIGRATIONS_CACHE = Path("specify_cli") / "upgrade" / "migrations" / "__pycache__"


def _cli_env(copy_src: Path, home: Path) -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "PYTHONPATH": str(copy_src),
            # The copied src/ tree has no packs/ sibling; point the kernel's
            # single packs-root resolver at the real (read-only) repo packs.
            "SPEC_KITTY_PACKS_ROOT": str(_REPO_PACKS),
            "HOME": str(home),
            "XDG_CONFIG_HOME": str(home / ".config"),
            "XDG_CACHE_HOME": str(home / ".cache"),
            "SPEC_KITTY_NO_UPGRADE_CHECK": "1",
        }
    )
    return env


def test_corrupt_migrations_pyc_does_not_crash_startup(tmp_path: Path) -> None:
    copy_src = tmp_path / "src"
    shutil.copytree(_REPO_SRC, copy_src, ignore=shutil.ignore_patterns("__pycache__"))
    home = tmp_path / "home"
    home.mkdir()
    env = _cli_env(copy_src, home)

    # 1. Compile the copy's base.pyc (the file an interrupted install leaves
    #    truncated), via a minimal import of the real module.
    warm = subprocess.run(
        [sys.executable, "-c", "import specify_cli.upgrade.migrations.base"],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        timeout=180,
    )
    assert warm.returncode == 0, warm.stderr

    # 2. Corrupt it exactly like an interrupted install: truncated body,
    #    intact header — the flavor the import machinery trusts and then dies
    #    on (a fully-zeroed file self-heals via the magic-number check).
    pycs = list((copy_src / _MIGRATIONS_CACHE).glob("base.*.pyc"))
    assert len(pycs) == 1, f"expected exactly one base.*.pyc, found {pycs}"
    data = pycs[0].read_bytes()
    pycs[0].write_bytes(data[:20] + b"\x00" * 42)

    # 3. The next CLI invocation self-heals (purge + recompile + retry) instead
    #    of crashing, and tells the operator what was repaired.
    result = subprocess.run(
        [sys.executable, "-m", "specify_cli", "--version"],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        timeout=180,
    )
    assert result.returncode == 0, result.stderr
    assert "version" in result.stdout.lower()
    assert "repaired" in result.stderr.lower()
