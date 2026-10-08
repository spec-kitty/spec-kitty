"""Tests for the ``CharterYaml`` pydantic model (WP01 / T001).

Contract: ``kitty-specs/consolidate-charter-bundle-01KXSYB9/contracts/
charter-yaml-schema.md``. Pins the structured shape of the git-tracked,
authorable ``charter.yaml``.

⚠ paula BLOCKER-1 (data-model.md): activation keys are FLAT AT THE ROOT,
NOT nested under an ``activation:`` mapping — ``test_rejects_nested_
activation_mapping`` is the structural regression guard for that.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from charter.activation.activations import ActivationEntry
from charter.activation.schemas import (
    CharterCatalog,
    CharterCatalogReference,
    CharterYaml,
    CharterYamlMetadata,
    Directive,
    DirectivesConfig,
    GovernanceConfig,
)


pytestmark = [pytest.mark.unit]


def _catalog() -> CharterCatalog:
    return CharterCatalog(
        mission="software-dev",
        template_set="software-dev-default",
        languages=["python"],
        references=[
            CharterCatalogReference(
                id="PARADIGM:atomic-design",
                kind="paradigm",
                title="Atomic Design",
                summary="Compose interfaces from a five-level hierarchy.",
                source_path="src/charter/offering/paradigms/built-in/atomic-design.paradigm.yaml",
                local_path="_LIBRARY/paradigm-atomic-design.md",
            )
        ],
    )


def _governance() -> GovernanceConfig:
    return GovernanceConfig(
        activations=[
            ActivationEntry(
                activation_context={"mission_type": "software-dev"},
                charter_pack_id="very-serious-developers",
                artifact_id="caveman-comments",
            )
        ]
    )


def _directives() -> DirectivesConfig:
    return DirectivesConfig(
        directives=[Directive(id="DIRECTIVE_001", title="Architectural Integrity Standard")]
    )


class TestCharterYamlRoundTrip:
    def test_round_trips_governance_directives_catalog(self) -> None:
        governance = _governance()
        directives = _directives()
        catalog = _catalog()

        charter = CharterYaml(governance=governance, directives=directives, catalog=catalog)

        assert charter.governance == governance
        assert charter.directives == directives
        assert charter.catalog == catalog

    def test_governance_and_directives_deserialize_from_dumped_dict(self) -> None:
        """G1: governance/directives deserialize into the existing
        GovernanceConfig/DirectivesConfig models unchanged, round-tripped
        through a plain dict (as if read back from YAML)."""
        original = CharterYaml(governance=_governance(), directives=_directives(), catalog=_catalog())
        dumped = original.model_dump(mode="json")

        rebuilt = CharterYaml.model_validate(dumped)

        assert rebuilt.governance == original.governance
        assert rebuilt.directives == original.directives
        assert rebuilt.catalog == original.catalog

    def test_catalog_shape_mirrors_references_yaml_body(self) -> None:
        """G2: catalog carries mission/template_set/languages/references —
        the same keys as the retired references.yaml body."""
        catalog = _catalog()
        dumped = catalog.model_dump(mode="json")

        assert set(dumped.keys()) == {"mission", "template_set", "languages", "references"}
        assert dumped["references"][0]["id"] == "PARADIGM:atomic-design"


class TestActivationIsFlatAtRoot:
    def test_rejects_nested_activation_mapping(self) -> None:
        """paula BLOCKER-1: an ``activation:`` key nested under CharterYaml
        is not a declared field — extra="forbid" rejects it outright."""
        with pytest.raises(ValidationError):
            CharterYaml(
                governance=_governance(),
                directives=_directives(),
                catalog=_catalog(),
                activation={"activated_directives": ["001-x"]},  # type: ignore[call-arg]
            )

    @pytest.mark.parametrize(
        "field_name",
        [
            "activated_kinds",
            "mission_type_activations",
            "activated_directives",
            "activated_tactics",
            "activated_styleguides",
            "activated_toolguides",
            "activated_paradigms",
            "activated_procedures",
            "activated_agent_profiles",
            "activated_mission_step_contracts",
        ],
    )
    def test_activation_field_is_flat_root_attribute(self, field_name: str) -> None:
        charter = CharterYaml(
            governance=_governance(),
            directives=_directives(),
            catalog=_catalog(),
            **{field_name: ["some-id"]},
        )
        assert getattr(charter, field_name) == ["some-id"]

    def test_activation_field_defaults_to_none_absent_key_fallback(self) -> None:
        """G3: an absent key resolves the default-pack fallback (three-state:
        None is distinct from an explicit empty list)."""
        charter = CharterYaml(governance=_governance(), directives=_directives(), catalog=_catalog())
        assert charter.activated_directives is None
        assert charter.activated_kinds is None

    def test_activation_field_accepts_explicit_empty_list_fail_closed(self) -> None:
        """G3: an explicit empty list stays fail-closed — distinct from
        the absent-key (None) fallback case."""
        charter = CharterYaml(
            governance=_governance(),
            directives=_directives(),
            catalog=_catalog(),
            activated_directives=[],
        )
        assert charter.activated_directives == []
        assert charter.activated_directives is not None


class TestCharterYamlMetadata:
    def test_metadata_has_no_charter_hash_field(self) -> None:
        """G4 / Landmine 2: metadata MUST NOT carry a self-referential
        charter_hash — a hash of charter.yaml cannot live inside charter.yaml."""
        assert "charter_hash" not in CharterYamlMetadata.model_fields

    def test_metadata_carries_bundle_schema_version_2(self) -> None:
        metadata = CharterYamlMetadata()
        assert metadata.bundle_schema_version == 2

    def test_metadata_rejects_charter_hash_kwarg(self) -> None:
        with pytest.raises(ValidationError):
            CharterYamlMetadata(charter_hash="sha256:deadbeef")  # type: ignore[call-arg]


class TestCharterYamlOverridesAndSchemaVersion:
    def test_schema_version_defaults_to_2_0_0(self) -> None:
        charter = CharterYaml(governance=_governance(), directives=_directives(), catalog=_catalog())
        assert charter.schema_version == "2.0.0"

    def test_schema_version_regex_enforced(self) -> None:
        with pytest.raises(ValidationError):
            CharterYaml(
                schema_version="not-semver",
                governance=_governance(),
                directives=_directives(),
                catalog=_catalog(),
            )

    def test_overrides_defaults_to_empty_mapping(self) -> None:
        charter = CharterYaml(governance=_governance(), directives=_directives(), catalog=_catalog())
        assert charter.overrides == {}

    def test_overrides_accepts_forward_compatible_mapping(self) -> None:
        charter = CharterYaml(
            governance=_governance(),
            directives=_directives(),
            catalog=_catalog(),
            overrides={"some-future-key": {"nested": True}},
        )
        assert charter.overrides == {"some-future-key": {"nested": True}}

    def test_charter_yaml_is_frozen(self) -> None:
        charter = CharterYaml(governance=_governance(), directives=_directives(), catalog=_catalog())
        with pytest.raises(ValidationError):
            charter.schema_version = "9.9.9"  # type: ignore[misc]
