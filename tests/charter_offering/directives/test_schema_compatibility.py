"""Compatibility tests for directive schema/model enrichment fields."""

from __future__ import annotations

from pathlib import Path

import pytest
from ruamel.yaml import YAML

from charter.offering.directives.models import Directive
from charter.offering.directives.repository import DirectiveRepository
from charter.offering.directives.validation import validate_directive


pytestmark = [pytest.mark.doctrine, pytest.mark.fast]

REPO_ROOT = Path(__file__).resolve().parents[3]
BUILT_IN_DIRECTIVES_DIR = REPO_ROOT / "src" / "charter" / "offering" / "directives" / "built-in"


def _load_yaml(path: Path) -> dict:
    yaml = YAML(typ="safe")
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.load(handle)
    assert isinstance(data, dict), f"{path}: expected mapping root"
    return data


class TestDirectiveSchemaCompatibility:
    @pytest.mark.parametrize(
        "directive_path",
        sorted(BUILT_IN_DIRECTIVES_DIR.glob("*.directive.yaml")),
        ids=lambda p: p.name,
    )
    def test_existing_built_in_directives_still_validate(self, directive_path: Path) -> None:
        """Backward compatibility: all shipped directives remain valid."""
        data = _load_yaml(directive_path)
        errors = validate_directive(data)
        assert errors == []

    def test_minimal_required_fields_validate_and_parse(self) -> None:
        """A minimal directive with only required fields remains valid."""
        minimal = {
            "schema_version": "1.0",
            "id": "DIRECTIVE_TEST_MINIMAL",
            "title": "Minimal Test Directive",
            "intent": "Validate minimal compatibility.",
            "enforcement": "required",
        }

        assert validate_directive(minimal) == []
        parsed = Directive.model_validate(minimal)
        assert parsed.scope is None
        assert parsed.procedures == []
        assert parsed.references == []
        assert parsed.integrity_rules == []
        assert parsed.validation_criteria == []
        assert parsed.explicit_allowances == []

    def test_enriched_directive_fields_validate_and_parse(self) -> None:
        """Enriched format with all optional fields must validate and parse."""
        enriched = {
            "schema_version": "1.0",
            "id": "DIRECTIVE_TEST_ENRICHED",
            "title": "Enriched Test Directive",
            "intent": "Validate enriched compatibility.",
            "enforcement": "advisory",
            "scope": "Applies to all directive model tests.",
            "procedures": [
                "Write schema compatibility tests",
                "Run directive test suite",
            ],
            "references": [
                # Exercises the optional curated edge metadata (``when``/``reason``)
                # carried symmetrically with the DRG edge the extractor mints
                # (#3009 residual, mission kind-complete-cascade-orphan-wiring
                # -01M0FQCD): a defensible relationship can live in frontmatter.
                {
                    "type": "toolguide",
                    "id": "git-agent-commit-signing",
                    "when": "signing an agent commit",
                    "reason": "the toolguide documents the signing workflow",
                },
            ],
            "integrity_rules": [
                "Existing minimal directives must remain valid.",
            ],
            "validation_criteria": [
                "Schema validation passes for minimal and enriched directives.",
            ],
            "explicit_allowances": [
                "Documented exceptions may expand scope when explicitly justified.",
            ],
        }

        assert validate_directive(enriched) == []
        parsed = Directive.model_validate(enriched)
        assert parsed.scope == enriched["scope"]
        assert parsed.procedures == enriched["procedures"]
        assert [ref.model_dump() for ref in parsed.references] == enriched["references"]
        assert parsed.integrity_rules == enriched["integrity_rules"]
        assert parsed.validation_criteria == enriched["validation_criteria"]
        assert parsed.explicit_allowances == enriched["explicit_allowances"]

    def test_partial_enrichment_still_validates(self) -> None:
        """A directive may include only some optional enrichment fields."""
        partially_enriched = {
            "schema_version": "1.0",
            "id": "DIRECTIVE_TEST_PARTIAL",
            "title": "Partially Enriched Directive",
            "intent": "Validate partial enrichment support.",
            "enforcement": "required",
            "scope": "Applies to partial enrichment tests.",
            "procedures": ["Run selected checks"],
        }

        assert validate_directive(partially_enriched) == []
        parsed = Directive.model_validate(partially_enriched)
        assert parsed.scope == "Applies to partial enrichment tests."
        assert parsed.procedures == ["Run selected checks"]
        assert parsed.integrity_rules == []
        assert parsed.validation_criteria == []
        assert parsed.explicit_allowances == []

    def test_lenient_adherence_requires_allowances(self) -> None:
        invalid = {
            "schema_version": "1.0",
            "id": "DIRECTIVE_TEST_LENIENT",
            "title": "Lenient Directive",
            "intent": "Validate lenient-adherence allowance requirements.",
            "enforcement": "lenient-adherence",
        }

        errors = validate_directive(invalid)
        assert any("explicit_allowances" in error for error in errors)

    def test_lenient_adherence_with_allowances_validates_and_parses(self) -> None:
        valid = {
            "schema_version": "1.0",
            "id": "DIRECTIVE_TEST_LENIENT_VALID",
            "title": "Lenient Directive",
            "intent": "Validate lenient-adherence support.",
            "enforcement": "lenient-adherence",
            "explicit_allowances": [
                "Allow proportional preparatory cleanup when it stabilizes the baseline."
            ],
        }

        assert validate_directive(valid) == []
        parsed = Directive.model_validate(valid)
        assert parsed.enforcement.value == "lenient-adherence"
        assert parsed.explicit_allowances == valid["explicit_allowances"]

    def test_invalid_enrichment_field_type_fails(self) -> None:
        """Invalid types in enrichment fields are rejected."""
        invalid = {
            "schema_version": "1.0",
            "id": "DIRECTIVE_TEST_INVALID",
            "title": "Invalid Enrichment Directive",
            "intent": "Validate invalid type rejection.",
            "enforcement": "required",
            "procedures": "this should be a list, not a string",
        }

        errors = validate_directive(invalid)
        assert any("procedures" in error for error in errors)

    def test_repository_save_and_reload_preserves_enrichment(self, tmp_path: Path) -> None:
        """Roundtrip through repository save/load preserves optional fields."""
        directive_data = {
            "schema_version": "1.0",
            "id": "DIRECTIVE_TEST_ROUNDTRIP",
            "title": "Roundtrip Directive",
            "intent": "Validate repository roundtrip.",
            "enforcement": "required",
            "scope": "Applies to repository tests.",
            "procedures": ["Save directive", "Reload directive"],
            "references": [
                {"type": "toolguide", "id": "git-agent-commit-signing"},
            ],
            "integrity_rules": ["No enrichment fields are lost."],
            "validation_criteria": ["Loaded directive matches saved values."],
            "explicit_allowances": [
                "Allow bounded preparatory cleanup when it reduces validation noise."
            ],
        }
        directive = Directive.model_validate(directive_data)

        project_dir = tmp_path / "project"
        empty_built_in = tmp_path / "empty-shipped"
        empty_built_in.mkdir()

        repo = DirectiveRepository(built_in_dir=empty_built_in, project_dir=project_dir)
        path = repo.save(directive)
        assert path.exists()

        reloaded_repo = DirectiveRepository(built_in_dir=empty_built_in, project_dir=project_dir)
        reloaded = reloaded_repo.get("DIRECTIVE_TEST_ROUNDTRIP")
        assert reloaded is not None
        assert reloaded.scope == directive.scope
        assert reloaded.procedures == directive.procedures
        assert reloaded.references == directive.references
        assert reloaded.integrity_rules == directive.integrity_rules
        assert reloaded.validation_criteria == directive.validation_criteria
        assert reloaded.explicit_allowances == directive.explicit_allowances
