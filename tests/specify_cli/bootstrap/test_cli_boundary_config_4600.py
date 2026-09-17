"""#4600 Instance 1: real startup survives unreadable optional config pointers."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

import pytest

pytestmark = [pytest.mark.regression, pytest.mark.git_repo]


@pytest.mark.parametrize("args", [("--version",), ("doctor",)])
def test_issue_4600_startup_survives_non_utf8_config(tmp_path: Path, args: tuple[str, ...]) -> None:
    """FR-001/C-009: exercise startup before any module import in a fresh process."""
    project = tmp_path / "project"
    project.mkdir()
    subprocess.run(["git", "init", "--quiet", str(project)], check=True)
    config = project / ".kittify" / "config.yaml"
    config.parent.mkdir()
    config.write_text("{}\n", encoding="utf-8")
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[3] / "src")
    env["SPEC_KITTY_NO_UPGRADE_CHECK"] = "1"
    command = [sys.executable, "-m", "specify_cli", *args]
    healthy = subprocess.run(command, cwd=project, env=env, capture_output=True, text=True, timeout=90)
    assert "Traceback" not in healthy.stdout + healthy.stderr
    if args == ("--version",):
        assert healthy.returncode == 0, healthy.stderr
    config.write_bytes(b"\xd0\xd0\xd0bad\xff")
    damaged = subprocess.run(command, cwd=project, env=env, capture_output=True, text=True, timeout=90)
    assert "Traceback" not in damaged.stdout + damaged.stderr
    assert damaged.returncode == healthy.returncode
    assert damaged.stdout == healthy.stdout
