"""Negative suite for the FR-028 relationship-field hard cutover (WP06).

The ``enhances``/``overrides`` fields on the five content kinds (tactic,
styleguide, paradigm, procedure, agent profile) and the agent-profile
``specializes_from``/``specializes-from`` lineage field were *removed* from the
models. Authoring any of those keys must now raise a clear, fragment-pointing
validation error rather than silently loading or emitting a bare
``extra_forbidden`` message.

Relationships are henceforth authored as DRG edges in the per-kind
``src/charter/offering/<kind>.graph.yaml`` fragments -- an edge lives in the fragment
for its *source* kind. The rejection message must point authors there.
"""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from charter.offering.agent_profiles.profile import AgentProfile, Specialization
from charter.offering.agent_profiles.schema_models import (
    AgentProfileSchema,
    AgentSpecialization,
)
from charter.offering.paradigms.models import Paradigm
from charter.offering.procedures.models import Procedure, ProcedureStep
from charter.offering.styleguides.models import Styleguide
from charter.offering.tactics.models import Tactic, TacticStep

pytestmark = [pytest.mark.fast, pytest.mark.doctrine]


# Each row: (model_class, minimal-valid sample dict). The sample is a valid
# artifact for that kind; each test injects exactly one retired key on top.
CONTENT_KIND_MATRIX: list[Any] = [
    pytest.param(
        Tactic,
        {
            "schema_version": "1.0",
            "id": "test-tactic",
            "name": "Test Tactic",
            "steps": [TacticStep(title="Step One")],
        },
        id="tactic",
    ),
    pytest.param(
        Styleguide,
        {
            "schema_version": "1.0",
            "id": "test-style",
            "title": "Test Styleguide",
            "scope": "code",
            "principles": ["Write clear code"],
        },
        id="styleguide",
    ),
    pytest.param(
        Paradigm,
        {
            "schema_version": "1.0",
            "id": "test-paradigm",
            "name": "Test Paradigm",
            "summary": "A test paradigm.",
        },
        id="paradigm",
    ),
    pytest.param(
        Procedure,
        {
            "schema_version": "1.0",
            "id": "test-procedure",
            "name": "Test Procedure",
            "purpose": "Test relationship-field rejection.",
            "entry_condition": "Test entry.",
            "exit_condition": "Test exit.",
            "steps": [ProcedureStep(title="Step One")],
        },
        id="procedure",
    ),
]


def _assert_actionable(message: str) -> None:
    """The rejection text must guide the author to DRG fragment edges."""
    assert "FR-028" in message
    assert "graph.yaml" in message
    assert "fragment" in message


@pytest.mark.parametrize("model_cls, sample", CONTENT_KIND_MATRIX)
@pytest.mark.parametrize("field", ["enhances", "overrides"])
def test_content_kind_rejects_retired_field(
    model_cls: type, sample: dict[str, Any], field: str
) -> None:
    """Each content kind rejects ``enhances``/``overrides`` with a clear,
    fragment-pointing error (not a bare ``extra_forbidden``)."""
    with pytest.raises(ValidationError) as exc_info:
        model_cls(**{**sample, field: "some-builtin-id"})
    _assert_actionable(str(exc_info.value))


@pytest.mark.parametrize("model_cls, sample", CONTENT_KIND_MATRIX)
def test_content_kind_clean_sample_still_loads(
    model_cls: type, sample: dict[str, Any]
) -> None:
    """The cutover does not break artifacts that never used the fields."""
    instance = model_cls(**sample)
    assert not hasattr(instance, "enhances")
    assert not hasattr(instance, "overrides")


# ---------------------------------------------------------------------------
# Agent profile — domain model (profile.py) and schema model (schema_models.py)
# ---------------------------------------------------------------------------

_AGENT_PROFILE_SAMPLE: dict[str, Any] = {
    "profile_id": "test-profile",
    "name": "Test Profile",
    "purpose": "Validate relationship-field rejection.",
    "specialization": Specialization(primary_focus="Testing"),
    "roles": ["implementer"],
}

_AGENT_SCHEMA_SAMPLE: dict[str, Any] = {
    "profile-id": "test-profile",
    "name": "Test Profile",
    "purpose": "Validate relationship-field rejection.",
    "specialization": AgentSpecialization(primary_focus="Testing"),
    "role": "implementer",
}


@pytest.mark.parametrize(
    "field", ["specializes_from", "specializes-from", "enhances", "overrides"]
)
def test_agent_profile_domain_rejects_retired_field(field: str) -> None:
    """``AgentProfile`` (runtime domain model) rejects lineage/augmentation
    fields with the actionable, fragment-pointing message."""
    with pytest.raises(ValidationError) as exc_info:
        AgentProfile(**{**_AGENT_PROFILE_SAMPLE, field: "implementer-ivan"})
    _assert_actionable(str(exc_info.value))


@pytest.mark.parametrize(
    "field", ["specializes_from", "specializes-from", "enhances", "overrides"]
)
def test_agent_profile_schema_rejects_retired_field(field: str) -> None:
    """``AgentProfileSchema`` (schema-generation model) rejects the same set."""
    with pytest.raises(ValidationError) as exc_info:
        AgentProfileSchema(**{**_AGENT_SCHEMA_SAMPLE, field: "implementer-ivan"})
    _assert_actionable(str(exc_info.value))


def test_agent_profile_clean_sample_still_loads() -> None:
    """A profile without any retired field loads, and the attributes are gone."""
    profile = AgentProfile(**_AGENT_PROFILE_SAMPLE)
    assert not hasattr(profile, "specializes_from")
    assert not hasattr(profile, "enhances")
    assert not hasattr(profile, "overrides")


def test_legacy_field_pack_fixture_is_rejected() -> None:
    """The WP07 negative fixture (field-authored lineage) must be rejected.

    ``tests/charter_offering/fixtures/relationship_packs/legacy-field-pack/profiles/
    legacy-specialist.agent.yaml`` carries the deprecated ``specializes-from:``
    field; loading it as an ``AgentProfile`` must raise the actionable error.
    """
    import yaml

    from pathlib import Path

    fixture = (
        Path(__file__).parent
        / "fixtures"
        / "relationship_packs"
        / "legacy-field-pack"
        / "profiles"
        / "legacy-specialist.agent.yaml"
    )
    data = yaml.safe_load(fixture.read_text(encoding="utf-8"))
    with pytest.raises(ValidationError) as exc_info:
        AgentProfile(**data)
    _assert_actionable(str(exc_info.value))
