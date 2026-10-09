"""Unit tests for Styleguide models and StyleguideScope enum."""

import pytest
from pydantic import ValidationError

from charter.offering.styleguides.models import AntiPattern, Styleguide, StyleguideScope
pytestmark = [pytest.mark.fast, pytest.mark.doctrine]



class TestStyleguideScope:
    def test_values(self) -> None:
        assert StyleguideScope.CODE == "code"
        assert StyleguideScope.DOCS == "docs"
        assert StyleguideScope.ARCHITECTURE == "architecture"
        assert StyleguideScope.TESTING == "testing"
        assert StyleguideScope.OPERATIONS == "operations"
        assert StyleguideScope.GLOSSARY == "glossary"


class TestAntiPattern:
    def test_construction(self) -> None:
        ap = AntiPattern(
            name="Bad Pattern",
            description="Something bad.",
            bad_example="Don't do this.",
            good_example="Do this instead.",
        )
        assert ap.name == "Bad Pattern"
        assert ap.bad_example == "Don't do this."

    def test_missing_field_raises(self) -> None:
        with pytest.raises(ValidationError):
            AntiPattern(name="Bad", description="x", bad_example="y")  # type: ignore[call-arg]

    def test_frozen(self) -> None:
        ap = AntiPattern(
            name="X", description="x", bad_example="b", good_example="g"
        )
        with pytest.raises(ValidationError):
            ap.name = "changed"  # type: ignore[misc]


class TestStyleguide:
    def test_minimal_construction(self, sample_styleguide_data: dict) -> None:
        sg = Styleguide.model_validate(sample_styleguide_data)
        assert sg.id == "test-style"
        assert sg.scope == StyleguideScope.CODE
        assert set(sg.principles) == {"Write clear code"}
        assert sg.anti_patterns == []
        assert sg.quality_test is None
        assert sg.references == []

    def test_enriched_construction(self, enriched_styleguide_data: dict) -> None:
        sg = Styleguide.model_validate(enriched_styleguide_data)
        assert sg.scope == StyleguideScope.TESTING
        assert set(sg.principles) == {"Test first", "Test often"}
        assert {ap.name for ap in sg.anti_patterns} == {"Test After"}
        assert sg.anti_patterns[0].name == "Test After"
        assert sg.quality_test is not None
        assert set(sg.references) == {"docs/testing.md"}

    def test_structural_lint_config_defaults_to_none(
        self, sample_styleguide_data: dict[str, object]
    ) -> None:
        sg = Styleguide.model_validate(sample_styleguide_data)
        assert sg.structural_lint_config is None

    def test_structural_lint_config_round_trips(
        self, sample_styleguide_data: dict[str, object]
    ) -> None:
        data = {
            **sample_styleguide_data,
            "structural_lint_config": {
                "curated_complete_sections": ["architecture"],
                "point_in_time_allowlist": ["adr/**", "plans/research/**"],
                "point_in_time_markers": [
                    {"frontmatter_field": "doc_status", "frontmatter_value": "closeout"}
                ],
            },
        }
        sg = Styleguide.model_validate(data)
        assert sg.structural_lint_config == {
            "curated_complete_sections": ["architecture"],
            "point_in_time_allowlist": ["adr/**", "plans/research/**"],
            "point_in_time_markers": [
                {"frontmatter_field": "doc_status", "frontmatter_value": "closeout"}
            ],
        }

    def test_frozen_model(self, sample_styleguide_data: dict) -> None:
        sg = Styleguide.model_validate(sample_styleguide_data)
        with pytest.raises(ValidationError):
            sg.title = "changed"  # type: ignore[misc]

    def test_empty_principles_raises(self) -> None:
        with pytest.raises(ValidationError):
            Styleguide.model_validate(
                {
                    "schema_version": "1.0",
                    "id": "bad",
                    "title": "Bad",
                    "scope": "code",
                    "principles": [],
                }
            )

    def test_missing_principles_raises(self) -> None:
        with pytest.raises(ValidationError):
            Styleguide.model_validate(
                {
                    "schema_version": "1.0",
                    "id": "bad",
                    "title": "Bad",
                    "scope": "code",
                }
            )

    def test_invalid_scope_raises(self) -> None:
        with pytest.raises(ValidationError):
            Styleguide.model_validate(
                {
                    "schema_version": "1.0",
                    "id": "bad",
                    "title": "Bad",
                    "scope": "invalid_scope",
                    "principles": ["x"],
                }
            )
