"""Fixtures shared by the ``spec-kitty`` command suites in this directory."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.specify_cli.cli.commands._implement_fixtures import activated_repo


@pytest.fixture()
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A seeded repository the ``implement`` command is pointed at (see ``activated_repo``).

    A module that defines its own ``repo`` fixture keeps it: the closer definition wins.
    """
    return activated_repo(tmp_path, monkeypatch)
