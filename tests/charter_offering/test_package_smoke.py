"""Smoke checks covering module entrypoint and doctrine importability."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
import pytest
pytestmark = [pytest.mark.doctrine, pytest.mark.non_sandbox, pytest.mark.integration, pytest.mark.corpus]
REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ENV = {**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")}


def test_python_m_specify_cli_help_runs() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "specify_cli", "--help"],
        capture_output=True,
        text=True,
        check=False,
        env=SOURCE_ENV,
    )
    assert result.returncode == 0, result.stderr
    assert "spec-kitty" in result.stdout.lower() or "usage" in result.stdout.lower()


def test_doctrine_import_and_profile_repo_smoke() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from charter.offering.agent_profiles import AgentProfileRepository; "
                "repo = AgentProfileRepository(project_dir=None); "
                "assert repo.get('implementer-ivan') is not None"
            ),
        ],
        capture_output=True,
        text=True,
        check=False,
        env=SOURCE_ENV,
    )
    assert result.returncode == 0, result.stderr
