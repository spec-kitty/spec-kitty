"""Kind-registration + derived-machinery guards for ``glossary_pack``.

WP01 registers ``GLOSSARY_PACK`` as a first-order, charter-activatable doctrine
:class:`ArtifactKind`. The token-normalisation, charter-token, and YAML
activation-key machinery are all *derived* from the enum + the canonical
exclusion set; adding the member must light them up **for free** with no
special-casing (FR-002, FR-010, C-001).

If any assertion in :class:`TestDerivedMachineryFree` fails, the enum wiring in
``artifact_kinds.py`` is incomplete — fix the enum/maps, do NOT special-case the
downstream derivation.
"""

from __future__ import annotations

import pytest

from charter.activation.pack_manager import YAML_KEY_MAP
from charter.offering.artifact_kinds import (
    CHARTER_KIND_TOKENS,
    ArtifactKind,
    _NON_AUGMENTATION_ELIGIBLE_KINDS,
)

pytestmark = pytest.mark.fast


class TestDerivedMachineryFree:
    """FR-010: token/classification/activation-key derive with no special-casing."""

    def test_from_operator_token_resolves_hyphenated(self) -> None:
        assert (
            ArtifactKind.from_operator_token("glossary-pack")
            is ArtifactKind.GLOSSARY_PACK
        )

    def test_from_operator_token_resolves_underscored(self) -> None:
        assert (
            ArtifactKind.from_operator_token("glossary_pack")
            is ArtifactKind.GLOSSARY_PACK
        )

    def test_token_in_charter_kind_tokens(self) -> None:
        assert "glossary-pack" in CHARTER_KIND_TOKENS

    def test_yaml_activation_key_derives(self) -> None:
        assert YAML_KEY_MAP["glossary-pack"] == "activated_glossary_packs"


class TestGlossaryPackClassification:
    """FR-002 / C-001: activatable, not in the exclusion set, plural mapped."""

    def test_not_in_non_augmentation_eligible_kinds(self) -> None:
        assert ArtifactKind.GLOSSARY_PACK not in _NON_AUGMENTATION_ELIGIBLE_KINDS

    def test_plural_mapping(self) -> None:
        assert ArtifactKind.GLOSSARY_PACK.plural == "glossary_packs"

    def test_operator_token_is_hyphenated(self) -> None:
        assert ArtifactKind.GLOSSARY_PACK.operator_token == "glossary-pack"

    def test_glob_pattern(self) -> None:
        assert ArtifactKind.GLOSSARY_PACK.glob_pattern == "*.glossary-pack.yaml"
