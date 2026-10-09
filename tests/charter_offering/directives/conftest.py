"""Shared fixtures for directive tests."""

from pathlib import Path

import pytest


@pytest.fixture
def sample_directive_data() -> dict:
    """Minimal valid directive data."""
    return {
        "schema_version": "1.0",
        "id": "DIRECTIVE_999",
        "title": "Test Directive",
        "intent": "A test directive for unit tests.",
        "enforcement": "required",
    }


@pytest.fixture
def enriched_directive_data() -> dict:
    """Enriched directive data with all optional fields."""
    return {
        "schema_version": "1.0",
        "id": "DIRECTIVE_998",
        "title": "Enriched Test Directive",
        "intent": "A fully enriched directive for testing all fields.",
        "enforcement": "advisory",
        # Post-WP02: inline `tactic_refs` has been excised; cross-artifact
        # relationships live in src/charter/offering/graph.yaml and `extra="forbid"`
        # now rejects the field on the Directive model.
        "scope": "Applies to all test scenarios.",
        "procedures": [
            "Write acceptance test first",
            "Run test suite",
        ],
        "references": [
            {"type": "toolguide", "id": "git-agent-commit-signing"},
        ],
        "integrity_rules": [
            "Tests must pass before merge",
        ],
        "validation_criteria": [
            "Coverage above 90%",
        ],
        "explicit_allowances": [
            "Documented exceptions may expand scope when they reduce implementation risk.",
        ],
    }


@pytest.fixture
def tmp_directive_dir(tmp_path: Path, sample_directive_data: dict) -> Path:
    """Temp directory with a sample directive YAML file."""
    from ruamel.yaml import YAML

    directive_dir = tmp_path / "directives"
    directive_dir.mkdir()

    yaml = YAML()
    yaml.default_flow_style = False
    filepath = directive_dir / "999-test-directive.directive.yaml"
    with filepath.open("w") as f:
        yaml.dump(sample_directive_data, f)

    return directive_dir
