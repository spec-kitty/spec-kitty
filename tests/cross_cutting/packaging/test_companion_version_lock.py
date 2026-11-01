"""The companion's three-place version lock and its uv workspace wiring (#6904, WP04).

ADR 2026-10-29-1, Amendment 2026-10-31: the ``spec-kitty-services`` version, the
``spec-kitty-cli`` version and the ``services`` extra pin are one value, and the
companion is the only uv workspace member and the only ``[tool.uv.sources]`` entry.
Reads TOML only.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

import pytest

pytestmark = pytest.mark.fast

_REPO = Path(__file__).resolve().parents[3]
_COMPANION_DIR = "packages/spec-kitty-services"
_COMPANION = "spec-kitty-services"


def _toml(path: Path) -> dict[str, Any]:
    return tomllib.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def root() -> dict[str, Any]:
    return _toml(_REPO / "pyproject.toml")


def test_the_companion_version_equals_the_cli_version(root: dict[str, Any]) -> None:
    companion = _toml(_REPO / _COMPANION_DIR / "pyproject.toml")
    assert companion["project"]["name"] == _COMPANION
    assert companion["project"]["version"] == root["project"]["version"]


def test_the_services_extra_pins_exactly_the_cli_version(root: dict[str, Any]) -> None:
    assert root["project"]["optional-dependencies"]["services"] == [f"{_COMPANION}=={root['project']['version']}"]


def test_the_cli_sdist_excludes_the_companion_tree(root: dict[str, Any]) -> None:
    assert "packages/**" in root["tool"]["hatch"]["build"]["targets"]["sdist"]["exclude"]


def test_the_lockfile_resolves_the_companion_from_the_workspace(root: dict[str, Any]) -> None:
    packages = {package["name"]: package for package in _toml(_REPO / "uv.lock")["package"]}
    companion = packages[_COMPANION]
    assert companion["version"] == root["project"]["version"]
    assert companion["source"] == {"editable": _COMPANION_DIR}
