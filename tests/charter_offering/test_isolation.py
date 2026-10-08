"""Verify doctrine can be imported without specify_cli at module load time."""
from __future__ import annotations
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = [pytest.mark.doctrine, pytest.mark.integration]

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_doctrine_primitives_do_not_import_specify_cli():
    """charter.offering.missions.primitives must import without specify_cli on PYTHONPATH."""
    src_root = REPO_ROOT / "src"
    # Only doctrine on PYTHONPATH — specify_cli deliberately absent
    pythonpath = str(src_root)
    result = subprocess.run(
        [sys.executable, "-c", "import charter.offering.missions.primitives; print('OK')"],
        env={**os.environ, "PYTHONPATH": pythonpath},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"charter.offering.missions.primitives pulled in specify_cli at import time.\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    assert "OK" in result.stdout
