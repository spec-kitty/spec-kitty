"""Kind-table derivation guard (mission pack-skills-kind-01M43419, WP01 / IC-01).

``REQUIRED_KIND_FIELDS`` (specify_cli), ``_REQUIRED_KIND_FIELDS`` (charter) and
``_SINGULAR_TO_PER_KIND_FIELD`` (charter DRG activation filter) used to be
hand-maintained lockstep copies. They are now derived from ``ArtifactKind``
facts; this module pins the user-visible order of the derived tables (the one place
an ``ArtifactKind`` reorder would show), that they match the model fields they must
mirror, and that every per-kind field is a real ``PackContext`` attribute, so adding a
kind needs no lockstep edit.
"""

from __future__ import annotations

import dataclasses

import pytest
from pydantic import BaseModel

from charter.activation import drg_activation, org_pack_discovery
from charter.activation.pack_context import PackContext
from charter.activation.schemas import DoctrineSelectionConfig
from charter.offering.artifact_kinds import ArtifactKind
from specify_cli.doctrine.org_charter import REQUIRED_KIND_FIELDS, OrgCharterPolicy

pytestmark = pytest.mark.architectural

#: ``skills`` (pack-skills-kind-01M43419 WP02): org-requirable, NOT selection-overlayable
#: and without a ``selected_skills`` charter field.
_NOT_OVERLAID = frozenset({"skills"})


def _model_fields(model: type[BaseModel], prefix: str) -> frozenset[str]:
    return frozenset(name.removeprefix(prefix) for name in model.model_fields if name.startswith(prefix))


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
_ACCEPTED_OVERLAYABLE_ORDER = (
    "directives",
    "tactics",
    "styleguides",
    "toolguides",
    "paradigms",
    "procedures",
    "agent_profiles",
    "mission_step_contracts",
)


def test_required_order_is_the_accepted_snapshot() -> None:
    """The literal pin: ``ArtifactKind`` declaration order is user-visible, and this is the only guard of the enum's own order."""
    assert tuple(REQUIRED_KIND_FIELDS) == _ACCEPTED_REQUIRED_ORDER
    assert tuple(org_pack_discovery._REQUIRED_KIND_FIELDS) == _ACCEPTED_OVERLAYABLE_ORDER


def test_requirable_matches_org_charter_policy_required_fields() -> None:
    assert frozenset(REQUIRED_KIND_FIELDS) == _model_fields(OrgCharterPolicy, "required_")


def test_overlayable_is_the_selected_fields_minus_the_non_overlaid_kinds() -> None:
    """``DoctrineSelectionConfig`` has ``selected_*`` fields that not every kind's org overlay fills.

    ``glossary_packs`` and ``assets`` have a ``selected_*`` field but are not
    unioned from org ``required_*`` lists by ``_load_doctrine_selection``.
    """
    overlayable = frozenset(org_pack_discovery._REQUIRED_KIND_FIELDS)
    selected = _model_fields(DoctrineSelectionConfig, "selected_")
    assert overlayable <= selected
    assert selected - overlayable == {"glossary_packs", "assets"}
    # ``skills`` is org-requirable but has no ``selected_skills`` field and is
    # not overlayable (pack-skills-kind-01M43419 WP02, ADR 2026-09-27-1).
    assert selected | _NOT_OVERLAID == frozenset(REQUIRED_KIND_FIELDS)
    assert "skills" not in overlayable
    assert not ArtifactKind.SKILL.selection_overlayable
    assert ArtifactKind.SKILL.org_requirable


#: The eleven charter-activatable kinds and the ``PackContext`` field holding each one's activated ids,
#: written out by hand (the ten that were hand-listed before the table was derived, plus ``skill``): the
#: derived table must neither lose a kind nor invent one.
_PER_KIND_FIELD = {
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
    "skill": "activated_skills",
}


def test_per_kind_field_values_are_real_pack_context_attributes() -> None:
    assert dict(drg_activation._SINGULAR_TO_PER_KIND_FIELD) == _PER_KIND_FIELD
    attrs = {f.name for f in dataclasses.fields(PackContext)}
    for field_name in drg_activation._SINGULAR_TO_PER_KIND_FIELD.values():
        assert field_name in attrs, field_name
