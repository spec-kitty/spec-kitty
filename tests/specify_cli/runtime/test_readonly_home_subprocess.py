"""Issue #6473: a real ``chmod 0o555`` home must not stop the CLI before it runs.

The in-process twins live in ``test_readonly_home_startup.py``; this one spawns
an interpreter, so it is an ``integration`` test (excluded from the fast tier).
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = [pytest.mark.integration]

_WARNING = "could not be written or read"


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX directory permissions")
@pytest.mark.skipif(hasattr(os, "geteuid") and os.geteuid() == 0, reason="chmod does not bind uid 0")
def test_subcommand_help_warns_once_on_stderr_with_read_only_home(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir(mode=0o555)
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    env = {k: v for k, v in os.environ.items() if not k.startswith(("SPEC_KITTY_HOME", "XDG_"))}
    env["HOME"] = str(home)
    try:
        result = subprocess.run(
            [sys.executable, "-m", "specify_cli", "agent", "--help"],
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
    assert result.returncode == 0, result.stdout + result.stderr
    stderr = " ".join(result.stderr.split())  # the log handler wraps lines
    assert stderr.count(_WARNING) == 1, result.stderr
    assert _WARNING not in " ".join(result.stdout.split())
