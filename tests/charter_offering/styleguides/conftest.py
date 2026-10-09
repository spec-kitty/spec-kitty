"""Shared fixtures for styleguide tests."""

from pathlib import Path

import pytest


@pytest.fixture
def sample_styleguide_data() -> dict:
    """Minimal valid styleguide data."""
    return {
        "schema_version": "1.0",
        "id": "test-style",
        "title": "Test Styleguide",
        "scope": "code",
        "principles": ["Write clear code"],
    }


@pytest.fixture
def enriched_styleguide_data() -> dict:
    """Styleguide data with all optional fields populated."""
    return {
        "schema_version": "1.0",
        "id": "enriched-style",
        "title": "Enriched Styleguide",
        "scope": "testing",
        "principles": ["Test first", "Test often"],
        "anti_patterns": [
            {
                "name": "Test After",
                "description": "Writing tests after implementation.",
                "bad_example": "Write code, then write tests.",
                "good_example": "Write test, then write code.",
            }
        ],
        "quality_test": "Can someone new follow this?",
        "references": ["docs/testing.md"],
    }


@pytest.fixture
def tmp_styleguide_dir(tmp_path: Path, sample_styleguide_data: dict) -> Path:
    """Temp directory with a sample styleguide YAML file."""
    from ruamel.yaml import YAML

    styleguide_dir = tmp_path / "styleguides"
    styleguide_dir.mkdir()

    yaml = YAML()
    yaml.default_flow_style = False
    filepath = styleguide_dir / "test-style.styleguide.yaml"
    with filepath.open("w") as f:
        yaml.dump(sample_styleguide_data, f)

    return styleguide_dir
