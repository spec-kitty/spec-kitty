"""Unit tests for the canonical ArtifactKind enum."""

from __future__ import annotations

import pytest

from charter.offering.artifact_kinds import (
    CHARTER_KIND_TOKENS,
    LAYERED_REPOSITORY_KIND_PLURALS,
    PROJECT_KIND_DIRS,
    ArtifactKind,
    _HAS_LAYERED_REPOSITORY_KINDS,
    _NON_AUGMENTATION_ELIGIBLE_KINDS,
    _SINGULAR_PROJECT_DIR_KINDS,
)

pytestmark = pytest.mark.fast


class TestArtifactKindValues:
    def test_all_expected_members_present(self) -> None:
        expected = {
            "directive",
            "tactic",
            "styleguide",
            "toolguide",
            "paradigm",
            "procedure",
            "agent_profile",
            "mission_step_contract",
            "template",
            "asset",
            "glossary_pack",
            "anti_pattern",
            "skill",
        }
        assert {m.value for m in ArtifactKind} == expected

    def test_string_coercions(self) -> None:
        assert ArtifactKind("directive") is ArtifactKind.DIRECTIVE
        assert ArtifactKind("agent_profile") is ArtifactKind.AGENT_PROFILE


class TestPluralProperty:
    @pytest.mark.parametrize(
        ("kind", "expected_plural"),
        [
            (ArtifactKind.DIRECTIVE, "directives"),
            (ArtifactKind.TACTIC, "tactics"),
            (ArtifactKind.STYLEGUIDE, "styleguides"),
            (ArtifactKind.TOOLGUIDE, "toolguides"),
            (ArtifactKind.PARADIGM, "paradigms"),
            (ArtifactKind.PROCEDURE, "procedures"),
            (ArtifactKind.AGENT_PROFILE, "agent_profiles"),
            (ArtifactKind.TEMPLATE, "templates"),
            (ArtifactKind.ASSET, "assets"),
        ],
    )
    def test_plural(self, kind: ArtifactKind, expected_plural: str) -> None:
        assert kind.plural == expected_plural

    def test_plurals_are_unique(self) -> None:
        plurals = [kind.plural for kind in ArtifactKind]
        assert len(plurals) == len(set(plurals))


class TestGlobPatternProperty:
    @pytest.mark.parametrize(
        ("kind", "expected_pattern"),
        [
            (ArtifactKind.DIRECTIVE, "*.directive.yaml"),
            (ArtifactKind.TACTIC, "*.tactic.yaml"),
            (ArtifactKind.STYLEGUIDE, "*.styleguide.yaml"),
            (ArtifactKind.TOOLGUIDE, "*.toolguide.yaml"),
            (ArtifactKind.PARADIGM, "*.paradigm.yaml"),
            (ArtifactKind.PROCEDURE, "*.procedure.yaml"),
            (ArtifactKind.AGENT_PROFILE, "*.agent.yaml"),
            (ArtifactKind.TEMPLATE, ""),
            (ArtifactKind.ASSET, "*.asset.yaml"),
        ],
    )
    def test_glob_pattern(self, kind: ArtifactKind, expected_pattern: str) -> None:
        assert kind.glob_pattern == expected_pattern

    def test_only_template_has_empty_pattern(self) -> None:
        empty = [k for k in ArtifactKind if not k.glob_pattern]
        assert empty == [ArtifactKind.TEMPLATE]


class TestFromPlural:
    @pytest.mark.parametrize(
        ("plural", "expected"),
        [
            ("directives", ArtifactKind.DIRECTIVE),
            ("tactics", ArtifactKind.TACTIC),
            ("agent_profiles", ArtifactKind.AGENT_PROFILE),
            ("templates", ArtifactKind.TEMPLATE),
            ("assets", ArtifactKind.ASSET),
        ],
    )
    def test_from_plural(self, plural: str, expected: ArtifactKind) -> None:
        assert ArtifactKind.from_plural(plural) is expected

    def test_from_plural_unknown_raises(self) -> None:
        with pytest.raises(KeyError):
            ArtifactKind.from_plural("unknown_type")

    def test_plural_mapping_covers_all_kinds(self) -> None:
        """Regression for the private kind -> plural mapping that the
        deleted charter transitive-reference module used to maintain.

        That module was deleted in WP03 of the
        ``excise-doctrine-curation-and-inline-references-01KP54J6`` mission;
        the shape it enforced (``<singular> -> <plural>`` for every
        :class:`ArtifactKind`) is now a pure enum invariant and is asserted
        directly.
        """
        for kind in ArtifactKind:
            # Round-trip: plural -> ArtifactKind.from_plural(plural) -> plural
            assert ArtifactKind.from_plural(kind.plural) is kind
            assert kind.value != kind.plural  # singular and plural differ


class TestPydanticIntegration:
    """Verify ArtifactKind works as a Pydantic field type."""

    def test_directive_reference_deserializes(self) -> None:
        from charter.offering.directives.models import DirectiveReference

        ref = DirectiveReference.model_validate({"type": "tactic", "id": "some-tactic"})
        assert ref.type is ArtifactKind.TACTIC

    def test_tactic_reference_deserializes(self) -> None:
        from charter.offering.tactics.models import TacticReference

        ref = TacticReference.model_validate({"name": "foo", "type": "styleguide", "id": "sg-01", "when": "always"})
        assert ref.type is ArtifactKind.STYLEGUIDE

    def test_procedure_reference_deserializes(self) -> None:
        from charter.offering.procedures.models import ProcedureReference

        ref = ProcedureReference.model_validate({"type": "paradigm", "id": "p-01"})
        assert ref.type is ArtifactKind.PARADIGM

    def test_invalid_type_raises(self) -> None:
        from pydantic import ValidationError
        from charter.offering.directives.models import DirectiveReference

        with pytest.raises(ValidationError):
            DirectiveReference.model_validate({"type": "unknown_type", "id": "x"})


class TestProjectKindDirs:
    """T012: the single canonical project-tier directory authority.

    :data:`PROJECT_KIND_DIRS` is the one place the project-overlay directory
    name for each :class:`ArtifactKind` is declared. The scaffolder
    (``doctrine new``), :class:`~charter.offering.service.CharterOfferingService` (WP04), and
    the charter resolvers all import it; none re-declares the mapping. It must
    be **total** (fail-closed) so a new kind cannot silently miss an entry.
    """

    def test_authority_is_total_over_every_artifact_kind(self) -> None:
        assert set(PROJECT_KIND_DIRS) == set(ArtifactKind)

    def test_runtime_managed_kinds_use_singular_overlay_dir(self) -> None:
        for kind in _SINGULAR_PROJECT_DIR_KINDS:
            assert PROJECT_KIND_DIRS[kind] == kind.value
        assert frozenset(
            {
                ArtifactKind.DIRECTIVE,
                ArtifactKind.TACTIC,
                ArtifactKind.STYLEGUIDE,
                ArtifactKind.PROCEDURE,
            }
        ) == _SINGULAR_PROJECT_DIR_KINDS

    def test_every_other_kind_uses_its_plural_overlay_dir(self) -> None:
        for kind in ArtifactKind:
            if kind not in _SINGULAR_PROJECT_DIR_KINDS:
                assert PROJECT_KIND_DIRS[kind] == kind.plural

    def test_asset_project_dir_is_the_plural_assets(self) -> None:
        # Pins the T018 scaffold/resolver rendezvous: ``charter new --kind
        # asset`` writes under this directory, and CharterOfferingService (WP04) reads
        # the same authority for the project tier.
        assert PROJECT_KIND_DIRS[ArtifactKind.ASSET] == "assets"


class TestHasLayeredRepository:
    """T030 (#5824): the ``has_layered_repository`` predicate and its derived tuple.

    The predicate names the kinds that resolve through a layered repository
    (built-in + org + project), the axis the four diagnostic surfaces (org-pack
    collision scan, org dir count, org-layer override lint, API 404 fallback)
    scan. It is exactly the 11 kinds EXCEPT ``TEMPLATE`` (mission-tier, empty
    glob) and ``ANTI_PATTERN`` (a re-kinded graph node, no standalone repo).
    """

    _EXPECTED_LAYERED = frozenset(
        {
            ArtifactKind.DIRECTIVE,
            ArtifactKind.TACTIC,
            ArtifactKind.STYLEGUIDE,
            ArtifactKind.TOOLGUIDE,
            ArtifactKind.PARADIGM,
            ArtifactKind.PROCEDURE,
            ArtifactKind.AGENT_PROFILE,
            ArtifactKind.MISSION_STEP_CONTRACT,
            ArtifactKind.ASSET,
            ArtifactKind.GLOSSARY_PACK,
            ArtifactKind.SKILL,
        }
    )

    def test_backing_frozenset_is_exactly_the_eleven_layered_kinds(self) -> None:
        assert _HAS_LAYERED_REPOSITORY_KINDS == self._EXPECTED_LAYERED
        assert len(_HAS_LAYERED_REPOSITORY_KINDS) == 11

    def test_predicate_matches_the_backing_set(self) -> None:
        assert {k for k in ArtifactKind if k.has_layered_repository} == self._EXPECTED_LAYERED

    def test_excludes_only_template_and_anti_pattern(self) -> None:
        excluded = {k for k in ArtifactKind if not k.has_layered_repository}
        assert excluded == {ArtifactKind.TEMPLATE, ArtifactKind.ANTI_PATTERN}

    def test_covers_the_three_later_additions(self) -> None:
        # The #5824 defect class: surfaces covering only the 8 core kinds skip
        # these three. The layered predicate must include them.
        for kind in (ArtifactKind.ASSET, ArtifactKind.GLOSSARY_PACK, ArtifactKind.SKILL):
            assert kind.has_layered_repository is True

    def test_distinct_from_selection_overlayable(self) -> None:
        overlayable = {k for k in ArtifactKind if k.selection_overlayable}
        assert len(overlayable) == 8
        assert overlayable != _HAS_LAYERED_REPOSITORY_KINDS
        # The three later additions are the exact difference.
        assert self._EXPECTED_LAYERED - overlayable == {
            ArtifactKind.ASSET,
            ArtifactKind.GLOSSARY_PACK,
            ArtifactKind.SKILL,
        }

    def test_distinct_from_has_built_in_content_dir(self) -> None:
        built_in = {k for k in ArtifactKind if k.has_built_in_content_dir}
        assert len(built_in) == 10
        assert built_in != _HAS_LAYERED_REPOSITORY_KINDS
        # Layered adds mission_step_contract (a package-resource kind with a
        # layered repo but no shipped content dir), which content-dir omits.
        assert self._EXPECTED_LAYERED - built_in == {ArtifactKind.MISSION_STEP_CONTRACT}

    def test_coincides_with_org_requirable_today(self) -> None:
        # The docstring's load-bearing claim: membership-identical to
        # org_requirable TODAY, but a distinct fact (different home, different
        # meaning). A future divergence must not be blocked here.
        org_requirable = {k for k in ArtifactKind if k.org_requirable}
        assert org_requirable == _HAS_LAYERED_REPOSITORY_KINDS

    def test_derived_plurals_tuple_is_declaration_ordered(self) -> None:
        assert tuple(
            kind.plural for kind in ArtifactKind if kind.has_layered_repository
        ) == LAYERED_REPOSITORY_KIND_PLURALS
        assert LAYERED_REPOSITORY_KIND_PLURALS == (
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

    def test_plurals_tuple_in_all(self) -> None:
        from charter.offering import artifact_kinds

        assert "LAYERED_REPOSITORY_KIND_PLURALS" in artifact_kinds.__all__


class TestCoreKindRetired:
    """T035 (#5824): ``ArtifactKind.core`` / ``CORE_KIND_PLURALS`` are gone."""

    def test_core_property_removed(self) -> None:
        assert not hasattr(ArtifactKind.DIRECTIVE, "core")

    def test_core_kind_plurals_symbol_removed(self) -> None:
        from charter.offering import artifact_kinds

        assert not hasattr(artifact_kinds, "CORE_KIND_PLURALS")
        assert "CORE_KIND_PLURALS" not in artifact_kinds.__all__
        assert not hasattr(artifact_kinds, "_CORE_KINDS")


class TestNonAugmentationEligibleKinds:
    """T003/T004: the canonical exclusion set and its consumer, CHARTER_KIND_TOKENS."""

    def test_exclusion_set_is_exactly_template_asset_and_anti_pattern(self) -> None:
        assert (
            frozenset({ArtifactKind.TEMPLATE, ArtifactKind.ASSET, ArtifactKind.ANTI_PATTERN})
            == _NON_AUGMENTATION_ELIGIBLE_KINDS
        )

    def test_asset_not_in_charter_kind_tokens(self) -> None:
        assert ArtifactKind.ASSET.operator_token not in CHARTER_KIND_TOKENS
        assert ArtifactKind.ASSET not in CHARTER_KIND_TOKENS

    def test_template_not_in_charter_kind_tokens(self) -> None:
        assert ArtifactKind.TEMPLATE.operator_token not in CHARTER_KIND_TOKENS
        assert ArtifactKind.TEMPLATE not in CHARTER_KIND_TOKENS

    def test_charter_kind_tokens_derived_from_exclusion_set(self) -> None:
        expected_artifact_tokens = {
            member.operator_token
            for member in ArtifactKind
            if member not in _NON_AUGMENTATION_ELIGIBLE_KINDS
        }
        actual_artifact_tokens = {t for t in CHARTER_KIND_TOKENS if t != "mission-type"}
        assert actual_artifact_tokens == expected_artifact_tokens
