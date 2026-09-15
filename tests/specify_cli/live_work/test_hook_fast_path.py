"""Fast-entry-point regression guard for ``spec-kitty live-work hook`` (#4353).

The hook is registered on the harness's PreToolUse/PostToolUse events, which
run synchronously around every tool call, so its process startup must not pay
the full command-registry import: the squad measured ~12 s wall against the
hook's own documented 4 s budget, all of it registry/init/charter imports
armed *before* ``bound_stdout(HOOK_BUDGET_S)`` could ever run. The fix gives
the hook the ``next`` command's fast-path posture — ``register_commands``
registers only the live-work group, ``_build_app`` skips the init
registration, and ``main_callback`` skips the global runtime bootstrap and
the startup project gates (the schema gate may ``SystemExit``, breaking the
hook's own always-exit-0 contract).

These tests verify the wiring (not wall-clock, which is machine-dependent):
the fast path must not import the heavy sibling command modules, the
startup-gate module, or the charter resolution chain.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = [pytest.mark.integration]

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SRC = _REPO_ROOT / "src"

# Modules that must stay unimported on the hook fast path: one representative
# sibling command module per heavy registration cluster, the schema gate's
# import chain, and the charter resolution chain cli.helpers used to pull at
# module scope.
_HEAVY_MODULES = (
    "specify_cli.cli.commands.merge",
    "specify_cli.cli.commands.init",
    "specify_cli.cli.commands.upgrade",
    "specify_cli.migration.gate",
    "charter.resolution",
)


def _spawn(argv: list[str], script: str) -> str:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(_SRC)
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
        cwd=_REPO_ROOT,
    )
    assert result.returncode == 0, f"`{argv}` failed unexpectedly.\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    return result.stderr


def test_live_work_hook_fast_path_registers_only_live_work() -> None:
    """`register_commands` on the hook path imports no sibling command modules."""
    script = (
        "import sys, typer\n"
        "sys.argv = ['spec-kitty', 'live-work', 'hook', 'claude']\n"
        "from specify_cli.cli.commands import register_commands\n"
        "app = typer.Typer()\n"
        "register_commands(app)\n"
        "heavy = [m for m in sys.modules if m in " + repr(_HEAVY_MODULES) + "]\n"
        "assert not heavy, heavy\n"
        "sys.stderr.write('FASTPATH=OK')\n"
    )
    assert "FASTPATH=OK" in _spawn(["live-work", "hook", "claude"], script)


def test_live_work_hook_invocation_skips_startup_bootstrap_modules() -> None:
    """The full app assembly on the hook path imports neither init nor the gates.

    Builds the real app (``_build_app``) with the hook argv and asserts the
    heavy startup imports never happened — the same wiring the ``next``
    footprint guard locks (``tests/specify_cli/next/test_next_import_footprint.py``).
    """
    script = (
        "import sys\n"
        "sys.argv = ['spec-kitty', 'live-work', 'hook', 'claude']\n"
        "from specify_cli import _build_app\n"
        "_build_app()\n"
        "heavy = [m for m in sys.modules if m in " + repr(_HEAVY_MODULES) + "]\n"
        "assert not heavy, heavy\n"
        "sys.stderr.write('ASSEMBLY=OK')\n"
    )
    assert "ASSEMBLY=OK" in _spawn(["live-work", "hook", "claude"], script)


def test_live_work_other_subcommands_still_register_the_full_surface() -> None:
    """Only the hook subcommand takes the fast path: matrix/install/watch and
    plain `live-work --help` still assemble the full command registry."""
    script = (
        "import sys, typer\n"
        "sys.argv = ['spec-kitty', 'live-work', 'matrix']\n"
        "from specify_cli.cli.commands import register_commands\n"
        "app = typer.Typer()\n"
        "register_commands(app)\n"
        "assert any(m == 'specify_cli.cli.commands.merge' for m in sys.modules)\n"
        "sys.stderr.write('FULLPATH=OK')\n"
    )
    assert "FULLPATH=OK" in _spawn(["live-work", "matrix"], script)


def test_live_work_hook_fast_path_predicates() -> None:
    """The argv predicates match exactly the per-tool-call hook invocation."""
    from specify_cli import _is_live_work_hook_invocation
    from specify_cli.cli.commands import _is_live_work_hook_fast_path

    for argv in (
        ["spec-kitty", "live-work", "hook", "claude"],
        ["spec-kitty", "live-work", "hook", "codex", "--verbose"],
        ["spec-kitty", "live-work", "hook"],
    ):
        assert _is_live_work_hook_fast_path(argv), argv
        assert _is_live_work_hook_invocation(argv), argv
    for argv in (
        ["spec-kitty"],
        ["spec-kitty", "live-work"],
        ["spec-kitty", "live-work", "matrix"],
        ["spec-kitty", "live-work", "install", "claude"],
        ["spec-kitty", "live-work", "watch"],
        ["spec-kitty", "next"],
        ["spec-kitty", "--help"],
        ["spec-kitty", "live-work", "--help"],
    ):
        assert not _is_live_work_hook_fast_path(argv), argv
        assert not _is_live_work_hook_invocation(argv), argv
