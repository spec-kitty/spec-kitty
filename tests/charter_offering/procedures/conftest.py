"""Shared fixtures for procedure tests."""

from pathlib import Path

import pytest


@pytest.fixture
def sample_procedure_data() -> dict:
    """Minimal valid procedure data."""
    return {
        "schema_version": "1.0",
        "id": "curation-interview",
        "name": "Doctrine Curation Interview",
        "purpose": "Walk through proposed doctrine artifacts and accept or reject each one.",
        "entry_condition": "At least one artifact exists in _proposed/ directory.",
        "exit_condition": "All proposed artifacts have been accepted, revised, or dropped.",
        "steps": [
            {
                "title": "Present artifact for review",
                "description": "Display the artifact summary and ask reviewer for a verdict.",
                "actor": "system",
            },
            {
                "title": "Record verdict",
                "description": "Persist the accept/revise/drop decision with rationale.",
                "actor": "human",
            },
            {
                "title": "Promote accepted artifacts",
                "description": "Move accepted artifacts from _proposed/ to shipped/.",
                "actor": "system",
            },
        ],
    }


@pytest.fixture
def enriched_procedure_data() -> dict:
    """Procedure with branching and cross-references.

    Post-WP02: step-level ``tactic_refs`` is removed; ``extra="forbid"``
    rejects it at the model layer. Cross-artifact relationships live in
    ``src/charter/offering/graph.yaml``.
    """
    return {
        "schema_version": "1.0",
        "id": "mission-merge-workflow",
        "name": "Feature Merge Workflow",
        "purpose": "Merge completed work packages into the target branch.",
        "entry_condition": "All work packages in done lane with passing tests.",
        "exit_condition": "Mission branch merged and worktrees cleaned up.",
        "steps": [
            {
                "title": "Run preflight checks",
                "actor": "system",
                "on_failure": "Abort merge and report errors.",
            },
            {
                "title": "Merge work packages in dependency order",
                "actor": "agent",
            },
            {
                "title": "Clean up worktrees",
                "actor": "system",
            },
        ],
        "references": [
            {"type": "directive", "id": "DIRECTIVE_001"},
            {"type": "template", "id": "risk-identification-assessment-template"},
        ],
    }


@pytest.fixture
def tmp_procedure_dir(tmp_path: Path, sample_procedure_data: dict) -> Path:
    """Temp directory with a sample procedure YAML file."""
    from ruamel.yaml import YAML

    procedure_dir = tmp_path / "procedures"
    procedure_dir.mkdir()

    yaml = YAML()
    yaml.default_flow_style = False
    filepath = procedure_dir / "curation-interview.procedure.yaml"
    with filepath.open("w") as f:
        yaml.dump(sample_procedure_data, f)

    return procedure_dir
