"""Tests for charter.offering.shared.schema_utils.SchemaUtilities.

Verifies that the shared schema loader correctly loads all shipped schemas
and returns valid dicts usable by jsonschema validators.

All tests are marked ``@pytest.mark.fast`` — no subprocess calls.
"""

from __future__ import annotations

import pytest

from charter.offering.shared.schema_utils import SchemaUtilities


# All artifact type names that must have a corresponding schema.

pytestmark = [pytest.mark.doctrine]

_SCHEMA_NAMES = [
    "directive",
    "tactic",
    "styleguide",
    "toolguide",
    "paradigm",
]


@pytest.mark.fast
@pytest.mark.parametrize("name", _SCHEMA_NAMES)
def test_load_schema_returns_dict(name: str) -> None:
    """load_schema returns a non-empty dict for every shipped artifact type."""
    schema = SchemaUtilities.load_schema(name)
    assert isinstance(schema, dict)
    assert schema, f"Schema '{name}' loaded an empty dict"


@pytest.mark.fast
@pytest.mark.parametrize("name", _SCHEMA_NAMES)
def test_load_schema_has_type_field(name: str) -> None:
    """Every shipped schema declares a JSON Schema ``type`` or ``$schema`` field."""
    schema = SchemaUtilities.load_schema(name)
    has_marker = "$schema" in schema or "type" in schema or "properties" in schema
    assert has_marker, f"Schema '{name}' missing expected JSON Schema fields"


@pytest.mark.fast
def test_load_schema_is_cached() -> None:
    """Repeated calls for the same name return the identical object (LRU cache)."""
    first = SchemaUtilities.load_schema("directive")
    second = SchemaUtilities.load_schema("directive")
    assert first is second, "load_schema should return the cached object on repeat calls"


@pytest.mark.fast
def test_load_schema_different_names_differ() -> None:
    """Schemas for different artifact types are distinct objects."""
    directive_schema = SchemaUtilities.load_schema("directive")
    tactic_schema = SchemaUtilities.load_schema("tactic")
    assert directive_schema is not tactic_schema


@pytest.mark.fast
def test_load_schema_missing_name_raises() -> None:
    """Loading a non-existent schema name raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        SchemaUtilities.load_schema("does_not_exist_xyz")


@pytest.mark.fast
def test_load_schema_directive_has_required_id() -> None:
    """Directive schema requires the ``id`` field."""
    schema = SchemaUtilities.load_schema("directive")
    required = schema.get("required", [])
    assert "id" in required, "directive schema must require 'id'"


@pytest.mark.fast
def test_load_schema_tactic_has_steps() -> None:
    """Tactic schema defines a ``steps`` property."""
    schema = SchemaUtilities.load_schema("tactic")
    properties = schema.get("properties", {})
    assert "steps" in properties, "tactic schema must define a 'steps' property"
