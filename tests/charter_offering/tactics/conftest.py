"""Shared fixtures for tactic tests."""

from pathlib import Path

import pytest


@pytest.fixture
def sample_tactic_data() -> dict:
    """Minimal valid tactic data."""
    return {
        "schema_version": "1.0",
        "id": "test-tactic",
        "name": "Test Tactic",
        "steps": [
            {"title": "Step One"},
        ],
    }


@pytest.fixture
def enriched_tactic_data() -> dict:
    """Tactic data with all optional fields populated."""
    return {
        "schema_version": "1.0",
        "id": "enriched-tactic",
        "name": "Enriched Tactic",
        "purpose": "A fully enriched tactic for testing.",
        "steps": [
            {
                "title": "Step One",
                "description": "First step description.",
                "examples": ["Example A", "Example B"],
                "references": [
                    {
                        "name": "Test Directive",
                        "type": "directive",
                        "id": "DIRECTIVE_001",
                        "when": "Before starting",
                    }
                ],
            },
            {
                "title": "Step Two",
                "description": "Second step description.",
            },
        ],
        "references": [
            {
                "name": "Root Reference",
                "type": "styleguide",
                "id": "python-style",
                "when": "Always",
            }
        ],
    }


@pytest.fixture
def tmp_tactic_dir(tmp_path: Path, sample_tactic_data: dict) -> Path:
    """Temp directory with a sample tactic YAML file."""
    from ruamel.yaml import YAML

    tactic_dir = tmp_path / "tactics"
    tactic_dir.mkdir()

    yaml = YAML()
    yaml.default_flow_style = False
    filepath = tactic_dir / "test-tactic.tactic.yaml"
    with filepath.open("w") as f:
        yaml.dump(sample_tactic_data, f)

    return tactic_dir
