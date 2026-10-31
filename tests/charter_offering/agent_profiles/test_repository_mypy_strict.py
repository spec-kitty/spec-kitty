"""Lock the mypy --strict invariant on charter.offering.agent_profiles.repository (#4292).

Under the ``charter.*`` ``follow_imports = "skip"`` override in
``pyproject.toml``, every cross-module charter import (``AgentProfile``,
``built_in_dir``, ``profile_channel_reachable``) resolves as ``Any`` when the
file is checked on its own. Returning those values directly from functions
declared ``-> float`` / ``-> Path`` / ``-> frozenset[str]`` raised three
``no-any-return`` errors; each return now goes through an annotated local.
This test makes a regression of that fail at test time.

Environment requirement: this test invokes mypy via ``sys.executable -m
mypy``, which requires the ``lint`` extra to be installed in the test env
(e.g. ``uv run --extra test --extra lint python -m pytest ...``).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = [pytest.mark.integration]

REPO_ROOT = Path(__file__).resolve().parents[3]
TARGET = "src/charter/offering/agent_profiles/repository.py"


@pytest.mark.slow  # mypy invocation is comparatively expensive
def test_agent_profile_repository_is_mypy_strict_clean() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "mypy", "--strict", TARGET],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        "mypy --strict failed on charter/offering/agent_profiles/repository.py.\nstdout:\n" + result.stdout + "\nstderr:\n" + result.stderr
    )
    assert "no-any-return" not in result.stdout, "A no-any-return error resurfaced in agent_profiles/repository.py:\n" + result.stdout
