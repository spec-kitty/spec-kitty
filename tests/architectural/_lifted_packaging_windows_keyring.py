"""Single home of the no-keyring dependency pin (#5015).

Both ``tests/packaging/test_windows_no_keyring.py`` (out of matrix) and its always-on lift
``tests/architectural/test_lifted_packaging_windows_keyring.py`` import these tests, so the per-PR gate
runs exactly what the source suite runs and the two cannot drift apart.
"""

from __future__ import annotations

import tomllib
from pathlib import Path


def test_keyring_not_declared_in_project_dependencies() -> None:
    pyproject = Path(__file__).resolve().parents[2] / "pyproject.toml"
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    dependencies = data["project"]["dependencies"]
    assert all(not dep.startswith("keyring") for dep in dependencies), (
        "CLI auth should use only the encrypted file store under ~/.spec-kitty/auth/, so pyproject.toml must not declare keyring."
    )
