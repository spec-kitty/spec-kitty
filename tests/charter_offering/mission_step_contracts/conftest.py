"""Shared fixtures for MissionStepContract tests."""

from pathlib import Path

import pytest
from ruamel.yaml import YAML


@pytest.fixture
def minimal_step_contract_data() -> dict:
    """Minimal valid step contract with one step."""
    return {
        "schema_version": "1.0",
        "id": "test-implement",
        "action": "implement",
        "mission": "software-dev",
        "steps": [
            {"id": "bootstrap", "description": "Load charter context"},
        ],
    }


@pytest.fixture
def full_step_contract_data() -> dict:
    """Step contract with all optional fields populated."""
    return {
        "schema_version": "1.0",
        "id": "implement",
        "action": "implement",
        "mission": "software-dev",
        "steps": [
            {
                "id": "bootstrap",
                "description": "Load charter context for this action",
                "command": "spec-kitty charter context --action implement --json",
                "inputs": [
                    {
                        "flag": "--profile",
                        "source": "wp.agent_profile",
                        "optional": True,
                    },
                    {
                        "flag": "--tool",
                        "source": "env.agent_tool",
                        "optional": True,
                    },
                ],
            },
            {
                "id": "workspace",
                "description": "Create or enter the work package workspace",
                "delegates_to": {
                    "kind": "paradigm",
                    "candidates": [
                        "execution-lanes",
                        "shared-branch-ci",
                        "git-flow",
                        "trunk-based",
                    ],
                },
                "guidance": "Execution lanes own worktrees.",
            },
            {
                "id": "execute",
                "description": "Implement the work package according to the prompt file",
                "delegates_to": {
                    "kind": "tactic",
                    "candidates": [
                        "tdd-red-green-refactor",
                        "acceptance-test-first",
                    ],
                },
            },
            {
                "id": "quality_gate",
                "description": "Run tests and type checks",
                "delegates_to": {
                    "kind": "directive",
                    "candidates": ["030-test-and-typecheck-quality-gate"],
                },
            },
            {
                "id": "commit",
                "description": "Commit changes with co-author attribution",
                "delegates_to": {
                    "kind": "directive",
                    "candidates": ["029-agent-commit-signing-policy"],
                },
                "guidance": "Use conventional commit format. Include WP ID in commit scope.",
            },
            {
                "id": "status_transition",
                "description": "Move WP to for_review",
                "command": "spec-kitty agent tasks move-task {wp_id} --to for_review",
            },
        ],
    }


@pytest.fixture
def tmp_contract_dir(tmp_path: Path, minimal_step_contract_data: dict) -> Path:
    """Temp directory with a sample step contract YAML file."""
    contract_dir = tmp_path / "contracts"
    contract_dir.mkdir()

    yaml = YAML()
    yaml.default_flow_style = False
    filepath = contract_dir / "test-implement.step-contract.yaml"
    with filepath.open("w") as f:
        yaml.dump(minimal_step_contract_data, f)

    return contract_dir
