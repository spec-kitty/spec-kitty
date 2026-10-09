"""The derived charter-activatable kind vocabulary authority (WP03 / T016).

FR-004/FR-005/C-003: one derived authority for the plural↔singular kind
vocabulary — 11 kinds including ``anti_pattern`` (distinct from the 9-token
``CHARTER_KIND_TOKENS`` and from ``_NON_AUGMENTATION_ELIGIBLE_KINDS``).
"""

from __future__ import annotations

import pytest

from charter.offering.artifact_kinds import (
    CHARTER_ACTIVATABLE_KINDS,
    CHARTER_ACTIVATABLE_PLURAL_TO_SINGULAR,
    CHARTER_ACTIVATABLE_SINGULAR_TO_PLURAL,
    CHARTER_KIND_TOKENS,
    ArtifactKind,
)

pytestmark = [pytest.mark.fast, pytest.mark.doctrine]


def test_exactly_eleven_activatable_kinds() -> None:
    # Pin the exact member set, not a bare count: adding, removing, or renaming
    # an activatable kind must force a content edit here, never pass silently at
    # an unchanged cardinality (golden-count contract, #2076).
    assert set(CHARTER_ACTIVATABLE_KINDS) == {
        ArtifactKind.AGENT_PROFILE,
        ArtifactKind.ANTI_PATTERN,
        ArtifactKind.DIRECTIVE,
        ArtifactKind.GLOSSARY_PACK,
        ArtifactKind.MISSION_STEP_CONTRACT,
        ArtifactKind.PARADIGM,
        ArtifactKind.PROCEDURE,
        ArtifactKind.SKILL,
        ArtifactKind.STYLEGUIDE,
        ArtifactKind.TACTIC,
        ArtifactKind.TOOLGUIDE,
    }


def test_anti_pattern_kept_template_and_asset_excluded() -> None:
    """C-003/FR-005: keep anti_pattern; only template + asset resolve specially."""
    assert ArtifactKind.ANTI_PATTERN in CHARTER_ACTIVATABLE_KINDS
    assert ArtifactKind.TEMPLATE not in CHARTER_ACTIVATABLE_KINDS
    assert ArtifactKind.ASSET not in CHARTER_ACTIVATABLE_KINDS
    assert set(ArtifactKind) - CHARTER_ACTIVATABLE_KINDS == {
        ArtifactKind.TEMPLATE,
        ArtifactKind.ASSET,
    }


def test_distinct_from_charter_kind_tokens() -> None:
    """The 10-kind set is NOT the 9-token CHARTER_KIND_TOKENS derivation.

    CHARTER_KIND_TOKENS drops ``anti_pattern`` (via _NON_AUGMENTATION_ELIGIBLE_
    KINDS) and adds the special ``mission-type`` token — a different set.
    """
    assert "anti-pattern" not in CHARTER_KIND_TOKENS
    activatable_tokens = {k.operator_token for k in CHARTER_ACTIVATABLE_KINDS}
    assert "anti-pattern" in activatable_tokens


def test_singular_to_plural_round_trips() -> None:
    for singular, plural in CHARTER_ACTIVATABLE_SINGULAR_TO_PLURAL.items():
        assert CHARTER_ACTIVATABLE_PLURAL_TO_SINGULAR[plural] == singular


def test_maps_cover_exactly_the_activatable_kinds() -> None:
    assert set(CHARTER_ACTIVATABLE_SINGULAR_TO_PLURAL) == {k.value for k in CHARTER_ACTIVATABLE_KINDS}
    assert set(CHARTER_ACTIVATABLE_SINGULAR_TO_PLURAL.values()) == {k.plural for k in CHARTER_ACTIVATABLE_KINDS}


def test_glossary_pack_and_anti_pattern_present() -> None:
    """The two kinds the drifted charter copies were missing are present."""
    assert CHARTER_ACTIVATABLE_SINGULAR_TO_PLURAL["glossary_pack"] == "glossary_packs"
    assert CHARTER_ACTIVATABLE_SINGULAR_TO_PLURAL["anti_pattern"] == "anti_patterns"
