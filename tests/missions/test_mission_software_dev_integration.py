"""Integration tests for the built-in software-dev mission YAML.

Verifies:
- Loading the real mission.yaml from disk
- The retired mission-DSL v1 compat keys are absent from the shipped catalog
- The v0 configuration keys are intact

The mission-DSL v1 runtime (schema validator, state machine, transition
graph) was retired in mission dead-port-disposition-01M1TZVN; the
``states:``/``transitions:`` blocks were deleted from the built-in packs at
the same time, so the structure/graph/reachability tests went with them. The
DRIFT-1 follow-up (#3961) stripped the remaining compat-ignored blocks
(``mission:``/``initial:``/``guards:``/``inputs:``/``outputs:``) from the
shipped catalogs, so the guards/inputs/outputs/mission-block pins went with
them — replaced here by the retirement assertion below, matching
``MISSION_COMPAT_IGNORED_FIELDS`` in ``src/specify_cli/mission.py`` and the
widened ratchet in ``tests/architectural/test_no_retired_subsystems.py``.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from charter.offering.missions.repository import MissionTemplateRepository

import pytest

pytestmark = pytest.mark.fast

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

MISSIONS_ROOT = MissionTemplateRepository.default_missions_root()
MISSION_YAML_PATH = MISSIONS_ROOT / "software-dev" / "mission.yaml"


@pytest.fixture()
def software_dev_config() -> dict:
    """Load the real software-dev mission.yaml."""
    with open(MISSION_YAML_PATH) as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------------------
# Presence
# ---------------------------------------------------------------------------


class TestMissionYamlPresence:
    """The built-in software-dev mission.yaml ships with the pack."""

    def test_file_exists(self) -> None:
        assert MISSION_YAML_PATH.exists(), f"Missing: {MISSION_YAML_PATH}"


# ---------------------------------------------------------------------------
# Retired mission-DSL v1 blocks
# ---------------------------------------------------------------------------

RETIRED_DSL_KEYS = frozenset(
    {"mission", "initial", "states", "transitions", "guards", "inputs", "outputs"}
)


class TestRetiredDslBlocks:
    """The shipped catalog carries no mission-DSL v1 residue.

    The v1 blocks were compat-ignored at load (``MISSION_COMPAT_IGNORED_FIELDS``)
    even before their removal, so nothing could consume them; the shipped
    catalog is configuration only. This is the per-catalog pin matching the
    tree-wide ratchet in ``tests/architectural/test_no_retired_subsystems.py``.
    """

    def test_retired_keys_absent(self, software_dev_config: dict) -> None:
        present = RETIRED_DSL_KEYS & set(software_dev_config)
        assert not present, (
            f"shipped software-dev mission.yaml must not carry retired "
            f"mission-DSL v1 keys: {sorted(present)}"
        )

    def test_mission_identity_is_top_level(self, software_dev_config: dict) -> None:
        assert software_dev_config["name"] == "Software Dev Kitty"
        assert software_dev_config["version"] == "1.0.0"
        assert "software" in software_dev_config["description"].lower()


# ---------------------------------------------------------------------------
# v0 configuration keys
# ---------------------------------------------------------------------------


class TestV0BackwardCompatibility:
    """The v0 configuration keys are the whole shipped file post-retirement."""

    def test_v0_name_preserved(self, software_dev_config: dict) -> None:
        assert software_dev_config["name"] == "Software Dev Kitty"

    def test_v0_workflow_preserved(self, software_dev_config: dict) -> None:
        assert "workflow" in software_dev_config
        phases = software_dev_config["workflow"]["phases"]
        assert frozenset(p["name"] for p in phases) == frozenset(
            {"research", "design", "implement", "test", "review"}
        )

    def test_v0_artifacts_preserved(self, software_dev_config: dict) -> None:
        assert "artifacts" in software_dev_config
        assert "spec.md" in software_dev_config["artifacts"]["required"]

    def test_v0_domain_preserved(self, software_dev_config: dict) -> None:
        assert software_dev_config["domain"] == "software"

    def test_v0_commands_preserved(self, software_dev_config: dict) -> None:
        assert "commands" in software_dev_config
        assert "specify" in software_dev_config["commands"]
        assert "implement" in software_dev_config["commands"]

    def test_v0_agent_context_preserved(self, software_dev_config: dict) -> None:
        assert "agent_context" in software_dev_config
        assert "TDD" in software_dev_config["agent_context"]
