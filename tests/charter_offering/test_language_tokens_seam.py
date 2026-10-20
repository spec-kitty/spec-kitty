"""``LANGUAGE_TOKENS`` is the one language symbol on the offering seam (#6541, FR-007/FR-008).

The seam carries the plain token list only. The catalog records, their family data
and the family expansion helpers stay internal to ``charter.offering.shared``.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.fast

_INTERNAL_CATALOG_NAMES = (
    "LANGUAGES",
    "LanguageSpec",
    "LANGUAGE_FAMILIES",
    "JVM_FAMILY",
    "BUILD_TOOLS",
    "BuildToolSpec",
    "expand_language_families",
    "is_language_family",
    "language_for_extension",
    "languages_for_manifest",
)


def test_language_tokens_importable_from_seam() -> None:
    import charter.offering.api as api
    from charter.offering.api import LANGUAGE_TOKENS

    assert "LANGUAGE_TOKENS" in api.__all__
    assert isinstance(LANGUAGE_TOKENS, tuple)
    assert all(isinstance(token, str) for token in LANGUAGE_TOKENS)


def test_language_tokens_derived_from_catalog_in_order() -> None:
    from charter.offering.api import LANGUAGE_TOKENS
    from charter.offering.shared import language_catalog

    expected = tuple(spec.token for spec in language_catalog.LANGUAGES)
    assert expected == LANGUAGE_TOKENS
    assert {"python", "kotlin", "java"} <= set(LANGUAGE_TOKENS)


@pytest.mark.parametrize("name", _INTERNAL_CATALOG_NAMES)
def test_catalog_internals_are_not_on_the_seam(name: str) -> None:
    import charter.offering.api as api

    assert name not in api.__all__
    assert not hasattr(api, name)


def test_facade_reexports_the_same_object() -> None:
    import charter.languages as facade
    from charter.offering.api import LANGUAGE_TOKENS

    assert facade.LANGUAGE_TOKENS is LANGUAGE_TOKENS
    assert facade.__all__ == ["LANGUAGE_TOKENS"]
