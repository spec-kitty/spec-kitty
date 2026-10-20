"""``LANGUAGE_TOKENS`` is the one language symbol on the offering seam (#6541, FR-007/FR-008).

The seam carries the plain token list only. The catalog records, their family data
and the family expansion helpers stay internal to ``charter.offering.shared``.
"""

from __future__ import annotations

import pytest

from charter.offering.shared import language_catalog

pytestmark = pytest.mark.fast

# Everything the catalog module exports except the one name the seam carries, so a new
# internal (``COMPOUND_PREFIX_GUARD`` was one) is covered without editing this list; plus the
# helpers that are not in the module's ``__all__``.
_INTERNAL_CATALOG_NAMES = sorted((set(language_catalog.__all__) - {"LANGUAGE_TOKENS"}) | {"LanguageSpec", "LANGUAGE_FAMILIES", "JVM_FAMILY", "BuildToolSpec"})


def test_language_tokens_derived_from_catalog_in_order() -> None:
    import charter.offering.api as api
    from charter.offering.api import LANGUAGE_TOKENS

    assert "LANGUAGE_TOKENS" in api.__all__
    assert isinstance(LANGUAGE_TOKENS, tuple)
    expected = tuple(spec.token for spec in language_catalog.LANGUAGES)
    assert expected == LANGUAGE_TOKENS
    assert {"python", "kotlin", "java"} <= set(LANGUAGE_TOKENS)
    # The ``charter.languages`` facade hands out the seam's object, not a copy. This static
    # import is also what keeps the facade reachable for test_src_reachability_guard.
    from charter.languages import LANGUAGE_TOKENS as facade_tokens

    assert facade_tokens is LANGUAGE_TOKENS


@pytest.mark.parametrize("name", _INTERNAL_CATALOG_NAMES)
def test_catalog_internals_are_not_on_the_seam(name: str) -> None:
    import charter.offering.api as api

    assert name not in api.__all__
    assert not hasattr(api, name)


def test_the_seam_takes_exactly_language_tokens_from_the_catalog() -> None:
    """Binding gate for the census row: ``language_catalog`` is PUBLIC module-wide, this pins the symbol."""
    import ast
    import inspect

    import charter.offering.api as api

    taken = {
        alias.name
        for node in ast.walk(ast.parse(inspect.getsource(api)))
        if isinstance(node, ast.ImportFrom) and node.module == language_catalog.__name__
        for alias in node.names
    }
    assert taken == {"LANGUAGE_TOKENS"}
