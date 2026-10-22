"""Issue #6473: a real ``chmod 0o555`` home must not stop the CLI before it runs.

The in-process twins live in ``test_readonly_home_startup.py``; this one spawns
an interpreter, so it is an ``integration`` test (excluded from the fast tier).

``--version`` and the root ``--help`` exit before the startup assets are
prepared; they are controls. ``agent --help`` and the ``--json`` command
go through the root callback.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = [pytest.mark.integration]


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX directory permissions")
@pytest.mark.skipif(hasattr(os, "geteuid") and os.geteuid() == 0, reason="chmod does not bind uid 0")
class TestReadOnlyHomeSubprocess:
    @pytest.mark.parametrize(
        ("args", "expect_exit"),
        [
            (["--version"], 0),
            (["--help"], 0),
            (["agent", "--help"], 0),
            (["agent", "tasks", "status", "--json"], 1),  # the command's own "not in a project" result
        ],
    )
    def test_command_runs(self, args: list[str], expect_exit: int, tmp_path: Path) -> None:
        home = tmp_path / "home"
        home.mkdir(mode=0o555)
        cwd = tmp_path / "cwd"
        cwd.mkdir()
        env = {k: v for k, v in os.environ.items() if not k.startswith(("SPEC_KITTY_HOME", "XDG_"))}
        env["HOME"] = str(home)
        try:
            result = subprocess.run(
                [sys.executable, "-m", "specify_cli", *args],
                cwd=cwd,
                env=env,
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
        finally:
            home.chmod(0o755)

        assert "Traceback" not in result.stderr, result.stderr
        assert result.returncode == expect_exit, result.stdout + result.stderr
        if args[-1] == "--json":
            assert json.loads(result.stdout)["error"]["code"] == "status_failed"
