"""Tests for shipped doctrine structure templates."""

from __future__ import annotations

from pathlib import Path
import pytest

from tests.charter_offering.conftest import OFFERING_SOURCE_ROOT

pytestmark = [pytest.mark.fast, pytest.mark.doctrine]

STRUCTURE_DIR = OFFERING_SOURCE_ROOT / "templates" / "structure"


def test_structure_templates_exist() -> None:
    assert (STRUCTURE_DIR / "REPO_MAP.md").exists()
    assert (STRUCTURE_DIR / "SURFACES.md").exists()


def test_structure_templates_have_placeholders() -> None:
    repo_map = (STRUCTURE_DIR / "REPO_MAP.md").read_text(encoding="utf-8")
    surfaces = (STRUCTURE_DIR / "SURFACES.md").read_text(encoding="utf-8")

    assert "{{DATE}}" in repo_map
    assert "{{TREE_SNIPPET}}" in repo_map
    assert "{{DATE}}" in surfaces
    assert "{{CLI_ENTRYPOINTS}}" in surfaces
