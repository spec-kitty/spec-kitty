"""Real-git helpers shared by tests that drive an on-disk repository."""

from __future__ import annotations

import subprocess
from pathlib import Path


def git_out(repo: Path, *args: str) -> str:
    """Run ``git -C repo <args>`` and return its stripped stdout; raise on failure."""
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout.strip()
