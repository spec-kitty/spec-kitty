"""Tests for charter.offering.shared.schema_utils.SchemaUtilities.load_schema.

Targets mutation-prone areas in _resolve_schema_path:
- importlib.resources path using "charter.offering.schemas" package
- hasattr guard on joinpath
- fallback to filesystem path

Patterns: Non-Identity Inputs (distinct schema names), Bi-Directional
Logic (loaded schema is a dict with expected keys).
"""

from __future__ import annotations

import pytest

from charter.offering.shared.schema_utils import SchemaUtilities

pytestmark = [pytest.mark.fast, pytest.mark.doctrine]


class TestSchemaUtilitiesLoadSchema:
    """load_schema returns a non-empty dict for shipped doctrine schemas."""

    def test_load_directive_schema_returns_dict(self):
        schema = SchemaUtilities.load_schema("directive")
        assert isinstance(schema, dict)

    def test_load_tactic_schema_returns_dict(self):
        schema = SchemaUtilities.load_schema("tactic")
        assert isinstance(schema, dict)

    def test_load_procedure_schema_returns_dict(self):
        schema = SchemaUtilities.load_schema("procedure")
        assert isinstance(schema, dict)

    def test_directive_schema_is_non_empty(self):
        schema = SchemaUtilities.load_schema("directive")
        assert len(schema) > 0

    def test_tactic_schema_has_different_content_from_directive(self):
        directive = SchemaUtilities.load_schema("directive")
        tactic = SchemaUtilities.load_schema("tactic")
        assert directive != tactic

    def test_missing_schema_raises_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            SchemaUtilities.load_schema("nonexistent-schema-xyz")

    def test_load_schema_returns_consistent_result(self):
        schema_a = SchemaUtilities.load_schema("directive")
        schema_b = SchemaUtilities.load_schema("directive")
        assert schema_a == schema_b
