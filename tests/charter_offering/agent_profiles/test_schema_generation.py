"""Regression tests for generated agent-profile JSON schema parity."""

from pathlib import Path

import jsonschema
import pytest
from ruamel.yaml import YAML

from scripts.generate_schemas import generate_schema

pytestmark = [pytest.mark.fast, pytest.mark.doctrine]

BUILT_IN_DIR = (
    Path(__file__).parent.parent.parent.parent
    / "packs"
    / "built-in"
    / "agent_profiles"
)


def test_generated_agent_profile_schema_retires_relationship_fields() -> None:
    """Schema must drop the retired augmentation/lineage fields (WP06 FR-028).

    ``overrides``/``enhances``/``specializes_from`` are no longer profile fields —
    lineage and augmentation are authored as DRG edges. Scoping fields such as
    ``applies_to_languages`` remain.
    """
    schema = generate_schema("agent-profile")
    properties = schema["properties"]

    assert "overrides" not in properties
    assert "enhances" not in properties
    assert "specializes_from" not in properties
    assert "applies_to_languages" in properties
    assert schema["anyOf"] == [{"required": ["role"]}, {"required": ["roles"]}]


def test_generated_agent_profile_schema_validates_shipped_scoped_profile() -> None:
    """Freshly generated schema must accept built-in profiles, not only committed YAML."""
    yaml = YAML(typ="safe")
    with (BUILT_IN_DIR / "python-pedro.agent.yaml").open() as f:
        profile = yaml.load(f)

    validator = jsonschema.Draft202012Validator(generate_schema("agent-profile"))
    errors = sorted(validator.iter_errors(profile), key=lambda error: list(error.path))

    assert errors == []


@pytest.mark.parametrize("field_name", ["overrides", "enhances"])
def test_generated_agent_profile_schema_rejects_retired_augmentation_fields(field_name: str) -> None:
    """Generated schema must REJECT the retired override/enhance fields (WP06 FR-028).

    These augmentation intents are now authored as DRG edges, not profile fields;
    the schema sets ``additionalProperties: false`` so a profile that still declares
    them fails validation.
    """
    profile = {
        "profile-id": "org-python-pedro",
        "name": "Org Python Pedro",
        "roles": ["implementer"],
        "purpose": "Validate augmentation intent fields.",
        "specialization": {"primary-focus": "Python implementation"},
        field_name: "python-pedro",
    }

    validator = jsonschema.Draft202012Validator(generate_schema("agent-profile"))
    errors = sorted(validator.iter_errors(profile), key=lambda error: list(error.path))

    assert errors, f"schema must reject retired field {field_name!r}"
