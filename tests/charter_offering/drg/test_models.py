"""Tests for WP01 (T001-T006): tension-vocabulary Relation/NodeKind foundation.

Covers:
- ``Relation.IN_TENSION_WITH`` / ``RECONCILES_TENSION`` / ``REJECTS`` string values.
- ``RELATION_DESCRIPTIONS`` registry: exactly the three new relations, non-empty text.
- ``NodeKind.ANTI_PATTERN`` + ``DRGNode.tags`` construct and round-trip.
- ``DRGNode`` URN-prefix validation still rejects a mismatched anti_pattern URN.
"""

from __future__ import annotations

import json

import pydantic
import pytest

from charter.offering.drg.models import RELATION_DESCRIPTIONS, DRGNode, NodeKind, Relation

pytestmark = [pytest.mark.fast, pytest.mark.doctrine]


# ---------------------------------------------------------------------------
# T001 -- new Relation members
# ---------------------------------------------------------------------------


def test_in_tension_with_value() -> None:
    assert Relation.IN_TENSION_WITH.value == "in_tension_with"
    assert Relation.IN_TENSION_WITH == "in_tension_with"


def test_reconciles_tension_value() -> None:
    assert Relation.RECONCILES_TENSION.value == "reconciles_tension"
    assert Relation.RECONCILES_TENSION == "reconciles_tension"


def test_rejects_value() -> None:
    assert Relation.REJECTS.value == "rejects"
    assert Relation.REJECTS == "rejects"


def test_new_relations_are_members_of_relation_enum() -> None:
    """Sanity: the three new members are actually part of the Relation StrEnum."""
    names = {member.name for member in Relation}
    assert {"IN_TENSION_WITH", "RECONCILES_TENSION", "REJECTS"} <= names


# ---------------------------------------------------------------------------
# T002 -- RELATION_DESCRIPTIONS registry
# ---------------------------------------------------------------------------


def test_relation_descriptions_covers_every_relation_member() -> None:
    """Completeness gate (FR-007, mission
    ``drg-relation-parity-activation-gate-01KY48PD``): every ``Relation``
    member must carry a description -- not just the three tension-vocabulary
    relations this gate originally pinned to."""
    assert set(RELATION_DESCRIPTIONS) == set(Relation)


@pytest.mark.parametrize("relation", list(Relation))
def test_relation_description_is_non_empty_string(relation: Relation) -> None:
    description = RELATION_DESCRIPTIONS[relation]
    assert isinstance(description, str)
    assert description.strip() != ""
    # Guard against a placeholder slipping through (test_relation_doc_parity.py
    # mirrors this text verbatim into docs/architecture/doctrine-relationships.md;
    # a stub here would ship as the canonical doc content).
    assert len(description) > 40


def test_relation_descriptions_are_distinct() -> None:
    """Each of the 15 descriptions must be meaningfully different prose --
    no two relations may share the same placeholder text (this is the
    mechanical distinctness floor behind ``applies`` != ``scope``, AC3)."""
    descriptions = list(RELATION_DESCRIPTIONS.values())
    assert len(set(descriptions)) == len(descriptions)


# ---------------------------------------------------------------------------
# T003 -- NodeKind.ANTI_PATTERN
# ---------------------------------------------------------------------------


def test_node_kind_anti_pattern_value() -> None:
    assert NodeKind.ANTI_PATTERN.value == "anti_pattern"
    assert NodeKind.ANTI_PATTERN == "anti_pattern"


def test_drg_node_anti_pattern_urn_validates() -> None:
    """A `anti_pattern:<id>` URN validates against NodeKind.ANTI_PATTERN without
    any change to `_validate_urn` -- it is generic over `kind.value`."""
    node = DRGNode(urn="anti_pattern:example", kind=NodeKind.ANTI_PATTERN)
    assert node.urn == "anti_pattern:example"
    assert node.kind is NodeKind.ANTI_PATTERN


# ---------------------------------------------------------------------------
# T004 -- DRGNode.tags
# ---------------------------------------------------------------------------


def test_drg_node_tags_default_is_empty_list() -> None:
    node = DRGNode(urn="directive:example", kind=NodeKind.DIRECTIVE)
    assert node.tags == []


def test_drg_node_anti_pattern_with_tags_constructs() -> None:
    node = DRGNode(
        urn="anti_pattern:example",
        kind=NodeKind.ANTI_PATTERN,
        tags=["smell"],
    )
    assert node.tags == ["smell"]


def test_drg_node_tags_round_trip_through_dict() -> None:
    node = DRGNode(urn="anti_pattern:example", kind=NodeKind.ANTI_PATTERN, tags=["smell"])
    dumped = node.model_dump()
    reloaded = DRGNode(**dumped)
    assert reloaded.tags == ["smell"]
    assert reloaded == node


def test_drg_node_tags_round_trip_through_json() -> None:
    """Explicit JSON round-trip -- proves `tags` is not silently dropped on
    load the way Pydantic v2's `extra="ignore"` default would drop an
    un-modelled key (this is exactly the gap T004 closes)."""
    node = DRGNode(urn="anti_pattern:example", kind=NodeKind.ANTI_PATTERN, tags=["smell"])
    serialized = node.model_dump_json()
    reloaded = DRGNode.model_validate(json.loads(serialized))
    assert reloaded.tags == ["smell"]
    assert reloaded == node


# ---------------------------------------------------------------------------
# T003/T004 -- URN prefix mismatch still raises for the new kind
# ---------------------------------------------------------------------------


def test_drg_node_anti_pattern_mismatched_prefix_rejected() -> None:
    """A `directive:` URN with `kind=NodeKind.ANTI_PATTERN` must still raise
    the existing prefix-mismatch ValueError -- adding a new NodeKind member
    does not weaken the existing URN-prefix validator."""
    with pytest.raises(pydantic.ValidationError, match="does not match kind"):
        DRGNode(kind=NodeKind.ANTI_PATTERN, urn="directive:example")
