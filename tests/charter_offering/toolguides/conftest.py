"""Shared fixtures for toolguide tests."""

from pathlib import Path

import pytest


@pytest.fixture
def sample_toolguide_data() -> dict:
    """Minimal valid toolguide data."""
    return {
        "schema_version": "1.0",
        "id": "test-toolguide",
        "tool": "bash",
        "title": "Test Toolguide",
        "guide_path": "src/charter/offering/toolguides/built-in/POWERSHELL_SYNTAX.md",
        "summary": "A sample toolguide fixture.",
    }


@pytest.fixture
def enriched_toolguide_data() -> dict:
    """Toolguide data with optional fields populated."""
    return {
        "schema_version": "1.0",
        "id": "enriched-toolguide",
        "tool": "git",
        "title": "Enriched Toolguide",
        "guide_path": "src/charter/offering/toolguides/built-in/POWERSHELL_SYNTAX.md",
        "summary": "An enriched fixture.",
        "commands": ["git", "spec-kitty"],
    }


@pytest.fixture
def tmp_toolguide_dir(tmp_path: Path, sample_toolguide_data: dict) -> Path:
    """Temp directory with a sample toolguide YAML file."""
    from ruamel.yaml import YAML

    toolguide_dir = tmp_path / "toolguides"
    toolguide_dir.mkdir()

    yaml = YAML()
    yaml.default_flow_style = False
    filepath = toolguide_dir / "test-toolguide.toolguide.yaml"
    with filepath.open("w") as f:
        yaml.dump(sample_toolguide_data, f)

    return toolguide_dir

