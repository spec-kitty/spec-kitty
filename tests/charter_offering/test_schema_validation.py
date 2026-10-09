"""Schema validation tests for doctrine governance artifacts."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator  # type: ignore[import-untyped]

pytestmark = [pytest.mark.doctrine, pytest.mark.fast]

SCHEMA_DIR = Path(__file__).resolve().parents[2] / "src" / "charter" / "offering" / "schemas"
FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"

SCHEMA_FILES = {
    "mission": SCHEMA_DIR / "mission.schema.yaml",
    "directive": SCHEMA_DIR / "directive.schema.yaml",
    "tactic": SCHEMA_DIR / "tactic.schema.yaml",
    "import-candidate": SCHEMA_DIR / "import-candidate.schema.yaml",
    "agent-profile": SCHEMA_DIR / "agent-profile.schema.yaml",
    "paradigm": SCHEMA_DIR / "paradigm.schema.yaml",
    "styleguide": SCHEMA_DIR / "styleguide.schema.yaml",
    "toolguide": SCHEMA_DIR / "toolguide.schema.yaml",
    "model-to-task_type": SCHEMA_DIR / "model-to-task_type.schema.yaml",
}


def _load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    assert isinstance(data, dict), f"{path}: expected mapping root"
    return data


def _schema_validator(schema_name: str) -> Draft202012Validator:
    schema_path = SCHEMA_FILES[schema_name]
    schema = _load_yaml(schema_path)
    return Draft202012Validator(schema)


def _error_message(schema_name: str, fixture_path: Path, error) -> str:
    pointer = "/" + "/".join(str(part) for part in error.path) if error.path else "/"
    return f"schema={schema_name} fixture={fixture_path.name} path={pointer} message={error.message}"


@pytest.mark.parametrize("schema_name", sorted(SCHEMA_FILES.keys()))
def test_valid_fixtures_pass(schema_name: str) -> None:
    validator = _schema_validator(schema_name)
    valid_dir = FIXTURE_DIR / schema_name / "valid"
    fixture_paths = sorted(valid_dir.glob("*.yaml"))

    assert fixture_paths, f"No valid fixtures found for {schema_name}"

    for fixture_path in fixture_paths:
        instance = _load_yaml(fixture_path)
        errors = sorted(validator.iter_errors(instance), key=str)
        assert not errors, "\n".join(_error_message(schema_name, fixture_path, error) for error in errors)


@pytest.mark.parametrize("schema_name", sorted(SCHEMA_FILES.keys()))
def test_invalid_fixtures_fail(schema_name: str) -> None:
    validator = _schema_validator(schema_name)
    invalid_dir = FIXTURE_DIR / schema_name / "invalid"
    fixture_paths = sorted(invalid_dir.glob("*.yaml"))

    assert fixture_paths, f"No invalid fixtures found for {schema_name}"

    for fixture_path in fixture_paths:
        instance = _load_yaml(fixture_path)
        errors = sorted(validator.iter_errors(instance), key=str)
        assert errors, f"schema={schema_name} fixture={fixture_path.name} expected validation errors but got none"


class TestRolesArraySchema:
    """Validate schema behaviour for the new 'roles' array property."""

    @pytest.fixture(autouse=True)
    def _validator(self) -> None:
        self.v = _schema_validator("agent-profile")

    def _base(self) -> dict:
        return {
            "profile-id": "test-roles",
            "name": "Test",
            "purpose": "Validation test",
            "specialization": {"primary-focus": "Testing"},
        }

    def test_roles_array_accepted(self) -> None:
        """Profile with roles array passes schema validation."""
        data = {**self._base(), "roles": ["implementer"]}
        errors = list(self.v.iter_errors(data))
        assert not errors, [e.message for e in errors]

    def test_roles_multi_accepted(self) -> None:
        """Profile with multiple roles passes schema validation."""
        data = {**self._base(), "roles": ["implementer", "reviewer"]}
        errors = list(self.v.iter_errors(data))
        assert not errors, [e.message for e in errors]

    def test_roles_empty_array_rejected(self) -> None:
        """roles: [] fails because minItems: 1."""
        data = {**self._base(), "roles": []}
        errors = list(self.v.iter_errors(data))
        assert errors

    def test_legacy_role_scalar_accepted(self) -> None:
        """Legacy scalar role: still accepted for backward compat."""
        data = {**self._base(), "role": "architect"}
        errors = list(self.v.iter_errors(data))
        assert not errors, [e.message for e in errors]

    def test_neither_role_nor_roles_rejected(self) -> None:
        """Profile without role or roles fails the anyOf constraint."""
        data = self._base()  # no role, no roles
        errors = list(self.v.iter_errors(data))
        assert errors


class TestAvatarImageSchema:
    """Validate schema behaviour for the new 'avatar-image' property."""

    @pytest.fixture(autouse=True)
    def _validator(self) -> None:
        self.v = _schema_validator("agent-profile")

    def _base(self) -> dict:
        return {
            "profile-id": "test-avatar",
            "name": "Test",
            "purpose": "Avatar validation",
            "roles": ["designer"],
            "specialization": {"primary-focus": "Design"},
        }

    def test_avatar_image_string_accepted(self) -> None:
        """avatar-image: string passes validation."""
        data = {**self._base(), "avatar-image": "assets/agents/me.png"}
        errors = list(self.v.iter_errors(data))
        assert not errors, [e.message for e in errors]

    def test_avatar_image_url_accepted(self) -> None:
        """avatar-image: URL passes validation."""
        data = {**self._base(), "avatar-image": "https://example.com/avatar.png"}
        errors = list(self.v.iter_errors(data))
        assert not errors, [e.message for e in errors]

    def test_avatar_image_absent_is_fine(self) -> None:
        """avatar-image is optional — its absence is valid."""
        data = self._base()
        errors = list(self.v.iter_errors(data))
        assert not errors, [e.message for e in errors]


def test_mission_schema_has_no_orchestration_state_machine() -> None:
    """The ``MissionOrchestration`` family is gone from ``mission.schema.yaml``.

    Mission dead-port-disposition-01M1TZVN, WP03 rider T014b (decision
    ``01M1W4WZEZZM8DM21JN1ZQY9E6``): the charter ``Mission`` model's
    ``orchestration`` state machine was schema-generation-only dead code whose
    last name-only producer (the packs' mission-DSL v1 blocks) WP01 retired.
    Neither the required key, the property, nor the three definitions may
    come back.
    """
    schema = _load_yaml(SCHEMA_FILES["mission"])
    assert "orchestration" not in schema["required"]
    assert "orchestration" not in schema["properties"]
    retired_definitions = {"mission_orchestration", "mission_state_object", "mission_transition"}
    assert not retired_definitions & set(schema["definitions"])
