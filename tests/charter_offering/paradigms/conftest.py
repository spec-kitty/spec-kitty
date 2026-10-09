"""Shared fixtures for paradigm tests."""

from pathlib import Path

import pytest


@pytest.fixture
def sample_paradigm_data() -> dict:
    """Minimal valid paradigm data."""
    return {
        "schema_version": "1.0",
        "id": "test-first",
        "name": "Test-First Doctrine",
        "summary": "Prefer acceptance-first and red-green-refactor loops.",
    }


@pytest.fixture
def enriched_paradigm_data() -> dict:
    """Another valid paradigm fixture with different values."""
    return {
        "schema_version": "1.0",
        "id": "delivery-first",
        "name": "Delivery-First Doctrine",
        "summary": "Bias toward small, frequent, verifiable delivery increments.",
    }


@pytest.fixture
def tmp_paradigm_dir(tmp_path: Path, sample_paradigm_data: dict) -> Path:
    """Temp directory with a sample paradigm YAML file."""
    from ruamel.yaml import YAML

    paradigm_dir = tmp_path / "paradigms"
    paradigm_dir.mkdir()

    yaml = YAML()
    yaml.default_flow_style = False
    filepath = paradigm_dir / "test-first.paradigm.yaml"
    with filepath.open("w") as f:
        yaml.dump(sample_paradigm_data, f)

    return paradigm_dir

