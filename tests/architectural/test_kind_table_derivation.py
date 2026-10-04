"""Kind-table derivation guard (mission pack-skills-kind-01M43419, WP01 / IC-01).

``REQUIRED_KIND_FIELDS`` (specify_cli), ``_REQUIRED_KIND_FIELDS`` (charter) and
``_SINGULAR_TO_PER_KIND_FIELD`` (charter DRG activation filter) used to be
hand-maintained lockstep copies. They are now derived from ``ArtifactKind``
facts; this module pins that each constant equals its derivation AND matches
the model fields it must mirror, so adding a kind needs no lockstep edit.
"""

from __future__ import annotations

import dataclasses

import pytest
from pydantic import BaseModel

from charter.activation import drg_activation, org_pack_discovery
from charter.activation.pack_context import PackContext
from charter.activation.schemas import DoctrineSelectionConfig
from charter.offering.artifact_kinds import CHARTER_ACTIVATABLE_KINDS, ArtifactKind
from specify_cli.doctrine.org_charter import REQUIRED_KIND_FIELDS, OrgCharterPolicy

pytestmark = pytest.mark.architectural

#: Snapshot of the hand-written tables as they stood before the derivation
#: refactor (membership only; order is asserted separately below).
_LEGACY_REQUIRED = frozenset(
    {
        "directives",
        "tactics",
        "paradigms",
        "styleguides",
        "toolguides",
        "procedures",
        "agent_profiles",
        "mission_step_contracts",
        "glossary_packs",
        "assets",
    }
)
#: Kinds added after the refactor snapshot (membership deltas, reviewed one by one).
#: ``skills`` (pack-skills-kind-01M43419 WP02): org-requirable, NOT selection-overlayable
#: and without a ``selected_skills`` charter field.
_ADDED_AFTER_SNAPSHOT_REQUIRED = frozenset({"skills"})
_LEGACY_OVERLAYABLE = frozenset(
    {
        "directives",
        "tactics",
        "paradigms",
        "styleguides",
        "toolguides",
        "procedures",
        "agent_profiles",
        "mission_step_contracts",
    }
)
_LEGACY_PER_KIND_FIELD = {
    "directive": "activated_directives",
    "tactic": "activated_tactics",
    "styleguide": "activated_styleguides",
    "toolguide": "activated_toolguides",
    "paradigm": "activated_paradigms",
    "procedure": "activated_procedures",
    "agent_profile": "activated_agent_profiles",
    "mission_step_contract": "activated_mission_step_contracts",
    "glossary_pack": "activated_glossary_packs",
    "anti_pattern": "activated_anti_patterns",
}


def _model_fields(model: type[BaseModel], prefix: str) -> frozenset[str]:
    return frozenset(name.removeprefix(prefix) for name in model.model_fields if name.startswith(prefix))


def test_snapshot_of_pre_refactor_tables() -> None:
    assert frozenset(REQUIRED_KIND_FIELDS) == _LEGACY_REQUIRED | _ADDED_AFTER_SNAPSHOT_REQUIRED
    assert len(REQUIRED_KIND_FIELDS) == len(_LEGACY_REQUIRED | _ADDED_AFTER_SNAPSHOT_REQUIRED)
    assert frozenset(org_pack_discovery._REQUIRED_KIND_FIELDS) == _LEGACY_OVERLAYABLE
    assert len(org_pack_discovery._REQUIRED_KIND_FIELDS) == len(_LEGACY_OVERLAYABLE)
    assert dict(drg_activation._SINGULAR_TO_PER_KIND_FIELD) == {**_LEGACY_PER_KIND_FIELD, "skill": "activated_skills"}


#: Accepted order after the derivation (ArtifactKind declaration order). The
#: legacy literal listed ``paradigms`` before ``styleguides``; deriving moves it
#: after ``toolguides``. That order is user-visible in the org-required promotion
#: messages (org_charter.py promotions loop and the interview pre-selection
#: notes), so the change is pinned here as a deliberate, reviewed decision.
_ACCEPTED_REQUIRED_ORDER = (
    "directives",
    "tactics",
    "styleguides",
    "toolguides",
    "paradigms",
    "procedures",
    "agent_profiles",
    "mission_step_contracts",
    "assets",
    "glossary_packs",
    "skills",
)


def test_required_order_is_the_accepted_snapshot() -> None:
    assert tuple(REQUIRED_KIND_FIELDS) == _ACCEPTED_REQUIRED_ORDER
    assert tuple(org_pack_discovery._REQUIRED_KIND_FIELDS) == tuple(k for k in _ACCEPTED_REQUIRED_ORDER if k in _LEGACY_OVERLAYABLE)


def test_overlayable_is_subset_of_requirable() -> None:
    assert set(org_pack_discovery._REQUIRED_KIND_FIELDS) <= set(REQUIRED_KIND_FIELDS)
    assert {k for k in ArtifactKind if k.selection_overlayable} <= {k for k in ArtifactKind if k.org_requirable}


def test_requirable_matches_org_charter_policy_required_fields() -> None:
    assert frozenset(REQUIRED_KIND_FIELDS) == _model_fields(OrgCharterPolicy, "required_")


def test_overlayable_is_the_selected_fields_minus_the_non_overlaid_kinds() -> None:
    """``DoctrineSelectionConfig`` carries 10 ``selected_*`` fields; only 8 take an org overlay.

    ``glossary_packs`` and ``assets`` have a ``selected_*`` field but are not
    unioned from org ``required_*`` lists by ``_load_doctrine_selection``.
    """
    overlayable = frozenset(org_pack_discovery._REQUIRED_KIND_FIELDS)
    selected = _model_fields(DoctrineSelectionConfig, "selected_")
    assert overlayable <= selected
    assert selected - overlayable == {"glossary_packs", "assets"}
    # ``skills`` is org-requirable but has no ``selected_skills`` field and is
    # not overlayable (pack-skills-kind-01M43419 WP02, ADR 2026-09-27-1).
    assert selected | _ADDED_AFTER_SNAPSHOT_REQUIRED == frozenset(REQUIRED_KIND_FIELDS)
    assert "skills" not in overlayable
    assert not ArtifactKind.SKILL.selection_overlayable
    assert ArtifactKind.SKILL.org_requirable


def test_derived_order_is_artifact_kind_declaration_order() -> None:
    declaration = [k.plural for k in ArtifactKind]
    for table in (REQUIRED_KIND_FIELDS, org_pack_discovery._REQUIRED_KIND_FIELDS):
        assert list(table) == [p for p in declaration if p in table]


def test_constants_equal_their_derivation_in_enum_order() -> None:
    expected_required = tuple(k.plural for k in ArtifactKind if k.org_requirable)
    expected_overlayable = tuple(k.plural for k in ArtifactKind if k.selection_overlayable)
    expected_per_kind = {k.value: f"activated_{k.plural}" for k in ArtifactKind if k in CHARTER_ACTIVATABLE_KINDS}
    assert tuple(REQUIRED_KIND_FIELDS) == expected_required
    assert tuple(org_pack_discovery._REQUIRED_KIND_FIELDS) == expected_overlayable
    assert dict(drg_activation._SINGULAR_TO_PER_KIND_FIELD) == expected_per_kind


def test_per_kind_field_values_are_real_pack_context_attributes() -> None:
    attrs = {f.name for f in dataclasses.fields(PackContext)}
    for field_name in drg_activation._SINGULAR_TO_PER_KIND_FIELD.values():
        assert field_name in attrs, field_name
