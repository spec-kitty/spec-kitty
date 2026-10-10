"""Model tests for ``requirement-kinds.yaml`` declarations (#5956 seam)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from charter.offering.missions.requirement_kinds import (
    RequirementKind,
    RequirementKindDeclaration,
    default_requirement_kinds,
)

pytestmark = [pytest.mark.fast, pytest.mark.doctrine]

_KIND = {"prefix": "DR", "label": "Data requirement", "glossary_term": "data requirement", "must_map_to_wp": True}


@pytest.mark.regression
def test_valid_declaration_accepted_and_frozen() -> None:
    decl = RequirementKindDeclaration.model_validate({"schema_version": "1", "mission_type": "research", "kinds": [_KIND]})
    assert decl.kinds[0].prefix == "DR"
    with pytest.raises(ValidationError):
        decl.mission_type = "other"  # type: ignore[misc]  # frozen-model assertion


@pytest.mark.regression
def test_unknown_field_rejected_on_kind_and_declaration() -> None:
    with pytest.raises(ValidationError):
        RequirementKind.model_validate({**_KIND, "extra": 1})
    with pytest.raises(ValidationError):
        RequirementKindDeclaration.model_validate({"mission_type": "r", "kinds": [_KIND], "extra": 1})


def test_empty_kinds_rejected() -> None:
    with pytest.raises(ValidationError):
        RequirementKindDeclaration.model_validate({"mission_type": "r", "kinds": []})


def test_default_set_matches_grammar_prefixes() -> None:
    decl = default_requirement_kinds("software-dev")
    assert [k.prefix for k in decl.kinds] == ["FR", "NFR", "SC", "C"]
    assert decl.mission_type == "software-dev"
