"""Layout verification tests for packs/built-in/missions/mission-steps/.

Verifies:
- Each built-in mission type has a mission-steps/<type>/ directory.
- Each step directory contains step.yaml and prompt.md.
- Each step.yaml is valid YAML with required FR-011 fields.
- The step.yaml ``id`` field matches the directory name.
- No old command-templates/ directories exist under src/specify_cli/missions/.

These are filesystem-level contract tests; they do not import charter.offering runtime
code so they run even before the unified MissionStep Pydantic model lands.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

pytestmark = [pytest.mark.fast, pytest.mark.doctrine, pytest.mark.corpus]

# ---------------------------------------------------------------------------
# Locate the source root relative to this test file.
# Tests live at tests/charter_offering/missions/ → walk up 3 levels to reach src/
# ---------------------------------------------------------------------------

_TESTS_DIR = Path(__file__).parent          # tests/charter_offering/missions/
_REPO_ROOT = Path(__file__).parents[3]      # worktree root (file → missions → doctrine → tests → root)
_SRC_DIR = _REPO_ROOT / "src"
# Mission doctrine-consumer-surface-missions-extraction-01KZ6G6H (FR-005)
# relocated mission-steps/ from src/charter/offering/missions/mission-steps to
# packs/built-in/missions/mission-steps.
_MISSION_STEPS_ROOT = _REPO_ROOT / "packs" / "built-in" / "missions" / "mission-steps"
_SPECIFY_CLI_MISSIONS = _SRC_DIR / "specify_cli" / "missions"

# Built-in mission types that must have a mission-steps directory.
# software-dev is the only type that has command-templates to migrate.
# documentation, research, and plan do not carry command-templates, so
# their mission-steps directories are not required by WP02. Only software-dev
# is asserted here.
BUILT_IN_MISSION_TYPES_WITH_STEPS = ("software-dev",)

# The FR-011 required fields for every step.yaml.
REQUIRED_STEP_YAML_FIELDS = {"id", "display_name", "step_type", "prompt_template"}

# Valid values for step_type per FR-011.
VALID_STEP_TYPES = {"agent", "human_in_loop", "integration"}

# Expected software-dev steps (derived from old command-templates/ stems).
EXPECTED_SOFTWARE_DEV_STEPS = frozenset({
    "accept",
    "analyze",
    "charter",
    "implement",
    "plan",
    "research",
    "review",
    "specify",
    "tasks",
    "tasks-finalize",
    "tasks-outline",
    "tasks-packages",
})


class TestMissionStepsRootExists:
    """The mission-steps/ directory exists under packs/built-in/missions/."""

    def test_mission_steps_root_exists(self) -> None:
        assert _MISSION_STEPS_ROOT.is_dir(), (
            f"Expected mission-steps root at {_MISSION_STEPS_ROOT} — directory missing"
        )


class TestBuiltInMissionTypeDirsExist:
    """Each built-in mission type with steps has a subdirectory."""

    @pytest.mark.parametrize("mission_type", BUILT_IN_MISSION_TYPES_WITH_STEPS)
    def test_mission_type_dir_exists(self, mission_type: str) -> None:
        mission_dir = _MISSION_STEPS_ROOT / mission_type
        assert mission_dir.is_dir(), (
            f"Expected mission-steps directory for '{mission_type}' at {mission_dir}"
        )


class TestSoftwareDevStepDirectories:
    """All expected software-dev step directories exist."""

    @pytest.fixture(scope="class")
    def software_dev_dir(self) -> Path:
        return _MISSION_STEPS_ROOT / "software-dev"

    @pytest.mark.parametrize("step_id", sorted(EXPECTED_SOFTWARE_DEV_STEPS))
    def test_step_directory_exists(self, software_dev_dir: Path, step_id: str) -> None:
        step_dir = software_dev_dir / step_id
        assert step_dir.is_dir(), (
            f"Expected step directory '{step_id}' at {step_dir}"
        )

    @pytest.mark.parametrize("step_id", sorted(EXPECTED_SOFTWARE_DEV_STEPS))
    def test_step_has_prompt_md(self, software_dev_dir: Path, step_id: str) -> None:
        prompt = software_dev_dir / step_id / "prompt.md"
        assert prompt.is_file(), (
            f"Expected prompt.md for step '{step_id}' at {prompt}"
        )

    @pytest.mark.parametrize("step_id", sorted(EXPECTED_SOFTWARE_DEV_STEPS))
    def test_step_has_step_yaml(self, software_dev_dir: Path, step_id: str) -> None:
        step_yaml = software_dev_dir / step_id / "step.yaml"
        assert step_yaml.is_file(), (
            f"Expected step.yaml for step '{step_id}' at {step_yaml}"
        )


class TestStepYamlValidity:
    """Each step.yaml is parseable YAML with required FR-011 fields."""

    @pytest.fixture(scope="class")
    def software_dev_dir(self) -> Path:
        return _MISSION_STEPS_ROOT / "software-dev"

    def _load_step_yaml(self, step_dir: Path) -> dict:
        step_yaml = step_dir / "step.yaml"
        assert step_yaml.is_file(), f"step.yaml missing at {step_yaml}"
        text = step_yaml.read_text(encoding="utf-8")
        data = yaml.safe_load(text)
        assert isinstance(data, dict), f"step.yaml at {step_yaml} must be a YAML mapping, got {type(data)}"
        return data

    @pytest.mark.parametrize("step_id", sorted(EXPECTED_SOFTWARE_DEV_STEPS))
    def test_step_yaml_has_required_fields(self, software_dev_dir: Path, step_id: str) -> None:
        data = self._load_step_yaml(software_dev_dir / step_id)
        missing = REQUIRED_STEP_YAML_FIELDS - data.keys()
        assert not missing, (
            f"step.yaml for '{step_id}' is missing required fields: {sorted(missing)}"
        )

    @pytest.mark.parametrize("step_id", sorted(EXPECTED_SOFTWARE_DEV_STEPS))
    def test_step_yaml_id_matches_directory_name(self, software_dev_dir: Path, step_id: str) -> None:
        data = self._load_step_yaml(software_dev_dir / step_id)
        assert data["id"] == step_id, (
            f"step.yaml 'id' field is '{data['id']}' but directory name is '{step_id}'"
        )

    @pytest.mark.parametrize("step_id", sorted(EXPECTED_SOFTWARE_DEV_STEPS))
    def test_step_yaml_step_type_is_valid(self, software_dev_dir: Path, step_id: str) -> None:
        data = self._load_step_yaml(software_dev_dir / step_id)
        step_type = data.get("step_type")
        assert step_type in VALID_STEP_TYPES, (
            f"step.yaml for '{step_id}' has invalid step_type '{step_type}'; "
            f"must be one of {sorted(VALID_STEP_TYPES)}"
        )

    @pytest.mark.parametrize("step_id", sorted(EXPECTED_SOFTWARE_DEV_STEPS))
    def test_step_yaml_prompt_template_is_string(self, software_dev_dir: Path, step_id: str) -> None:
        data = self._load_step_yaml(software_dev_dir / step_id)
        prompt_template = data.get("prompt_template")
        assert isinstance(prompt_template, str) and prompt_template, (
            f"step.yaml for '{step_id}' must have a non-empty string 'prompt_template'"
        )

    @pytest.mark.parametrize("step_id", sorted(EXPECTED_SOFTWARE_DEV_STEPS))
    def test_step_yaml_prompt_template_file_exists(
        self, software_dev_dir: Path, step_id: str
    ) -> None:
        data = self._load_step_yaml(software_dev_dir / step_id)
        prompt_template = data["prompt_template"]
        prompt_path = software_dev_dir / step_id / prompt_template
        assert prompt_path.is_file(), (
            f"step.yaml for '{step_id}' references prompt_template '{prompt_template}' "
            f"but no file found at {prompt_path}"
        )

    @pytest.mark.parametrize("step_id", sorted(EXPECTED_SOFTWARE_DEV_STEPS))
    def test_step_yaml_depends_on_is_list(self, software_dev_dir: Path, step_id: str) -> None:
        data = self._load_step_yaml(software_dev_dir / step_id)
        depends_on = data.get("depends_on", [])
        assert isinstance(depends_on, list), (
            f"step.yaml for '{step_id}' 'depends_on' must be a list, got {type(depends_on)}"
        )

    @pytest.mark.parametrize("step_id", sorted(EXPECTED_SOFTWARE_DEV_STEPS))
    def test_step_yaml_delegates_to_is_list(self, software_dev_dir: Path, step_id: str) -> None:
        data = self._load_step_yaml(software_dev_dir / step_id)
        delegates_to = data.get("delegates_to", [])
        assert isinstance(delegates_to, list), (
            f"step.yaml for '{step_id}' 'delegates_to' must be a list, got {type(delegates_to)}"
        )


class TestNoOldCommandTemplateDirectories:
    """No old command-templates/ directories remain under src/specify_cli/missions/."""

    def test_no_command_templates_dirs_remain(self) -> None:
        if not _SPECIFY_CLI_MISSIONS.is_dir():
            pytest.skip("src/specify_cli/missions/ does not exist")
        remaining = list(_SPECIFY_CLI_MISSIONS.rglob("command-templates"))
        assert not remaining, (
            f"Old command-templates/ directories still exist (should have been deleted): "
            f"{[str(p) for p in remaining]}"
        )


class TestSoftwareDevStepCount:
    """The software-dev mission-steps directory has the expected number of steps."""

    def test_software_dev_step_count(self) -> None:
        software_dev_dir = _MISSION_STEPS_ROOT / "software-dev"
        if not software_dev_dir.is_dir():
            pytest.skip("software-dev mission-steps directory not found")
        actual_steps = {
            d.name
            for d in software_dev_dir.iterdir()
            if d.is_dir()
        }
        assert actual_steps == EXPECTED_SOFTWARE_DEV_STEPS, (
            f"software-dev steps mismatch.\n"
            f"  Expected: {sorted(EXPECTED_SOFTWARE_DEV_STEPS)}\n"
            f"  Actual:   {sorted(actual_steps)}\n"
            f"  Extra:    {sorted(actual_steps - EXPECTED_SOFTWARE_DEV_STEPS)}\n"
            f"  Missing:  {sorted(EXPECTED_SOFTWARE_DEV_STEPS - actual_steps)}"
        )
