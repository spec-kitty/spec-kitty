"""Opt-in CLI → SaaS → managed relay contract; no live services.

Set SPEC_KITTY_CHAIN_SAAS to a SaaS checkout, SPEC_KITTY_CHAIN_PYTHON to
an interpreter with all three projects installed, and DATABASE_URL to a
throwaway PostgreSQL server. The child creates/drops its own test database.
"""

from __future__ import annotations

import os
from pathlib import Path
import subprocess

import pytest

pytestmark = pytest.mark.integration


def test_real_lease_revocation_chain(tmp_path: Path) -> None:
    saas = os.environ.get("SPEC_KITTY_CHAIN_SAAS")
    python = os.environ.get("SPEC_KITTY_CHAIN_PYTHON")
    if not saas or not python:
        pytest.skip("set SPEC_KITTY_CHAIN_SAAS and SPEC_KITTY_CHAIN_PYTHON for the cross-repo contract")
    env = dict(os.environ)
    env.update(SPEC_KITTY_HOME=str(tmp_path / "home"), SPEC_KITTY_ENABLE_SAAS_SYNC="0")
    result = subprocess.run(
        [python, str(Path(__file__).with_name("lease_revocation_chain_runner.py")), str(tmp_path)],
        cwd=saas,
        env=env,
        capture_output=True,
        text=True,
        timeout=600,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "lease revocation chain passed" in result.stdout
