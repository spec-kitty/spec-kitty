"""Unit tests for GlossaryTerm / GlossaryPack models (T006, FR-005, C-004).

T006 is RED-FIRST: authored before ``charter.offering.glossary_packs.models`` exists so
the initial run fails on the import, proving the round-trip assertions are
exercised against real model behavior once T007 lands the implementation.
"""

import pytest
from pydantic import ValidationError

from charter.offering.glossary_packs.models import GlossaryPack, GlossaryTerm

pytestmark = [pytest.mark.fast, pytest.mark.doctrine]


class TestGlossaryTerm:
    def test_round_trip_every_field(self, full_term_data: dict) -> None:
        """Every field the seed carries survives a load unchanged."""
        term = GlossaryTerm.model_validate(full_term_data)

        assert term.surface == full_term_data["surface"]
        assert term.definition == full_term_data["definition"]
        assert term.confidence == full_term_data["confidence"]
        assert term.status == full_term_data["status"]
        assert term.see_also == full_term_data["see_also"]
        assert term.introduced_in_mission == full_term_data["introduced_in_mission"]
        assert term.synonyms_to_avoid == full_term_data["synonyms_to_avoid"]
        assert term.aliases == full_term_data["aliases"]
        assert term.banned_synonyms == full_term_data["banned_synonyms"]

    def test_confidence_is_float(self, full_term_data: dict) -> None:
        term = GlossaryTerm.model_validate(full_term_data)
        assert isinstance(term.confidence, float)
        assert not isinstance(term.confidence, bool)

    def test_optional_fields_default_to_none(self, minimal_term_data: dict) -> None:
        """Optional-list fields default to None, not [] (matches runtime TermSense)."""
        term = GlossaryTerm.model_validate(minimal_term_data)

        assert term.see_also is None
        assert term.introduced_in_mission is None
        assert term.synonyms_to_avoid is None
        assert term.aliases is None
        assert term.banned_synonyms is None

    def test_frozen_model(self, minimal_term_data: dict) -> None:
        term = GlossaryTerm.model_validate(minimal_term_data)
        with pytest.raises(ValidationError):
            term.status = "retired"  # type: ignore[misc]

    def test_missing_required_field_raises(self) -> None:
        with pytest.raises(ValidationError):
            GlossaryTerm.model_validate({"surface": "x", "definition": "y"})


class TestGlossaryPack:
    def test_minimal_construction(self, sample_pack_data: dict) -> None:
        pack = GlossaryPack.model_validate(sample_pack_data)

        assert pack.id == "spec-kitty-core"
        assert pack.provenance == "built-in"
        assert pack.description == sample_pack_data["description"]
        assert len(pack.terms) == 2
        assert all(isinstance(term, GlossaryTerm) for term in pack.terms)

    def test_description_optional(self, sample_pack_data: dict) -> None:
        del sample_pack_data["description"]
        pack = GlossaryPack.model_validate(sample_pack_data)
        assert pack.description is None

    def test_terms_must_be_non_empty(self, sample_pack_data: dict) -> None:
        sample_pack_data["terms"] = []
        with pytest.raises(ValidationError):
            GlossaryPack.model_validate(sample_pack_data)

    def test_duplicate_surface_within_pack_raises(
        self, sample_pack_data: dict, minimal_term_data: dict
    ) -> None:
        """A pack with two terms sharing the same surface is invalid as a whole."""
        duplicate = dict(minimal_term_data)
        sample_pack_data["terms"] = [minimal_term_data, duplicate]

        with pytest.raises(ValidationError, match="duplicate"):
            GlossaryPack.model_validate(sample_pack_data)

    def test_frozen_model(self, sample_pack_data: dict) -> None:
        pack = GlossaryPack.model_validate(sample_pack_data)
        with pytest.raises(ValidationError):
            pack.description = "changed"  # type: ignore[misc]
