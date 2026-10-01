"""Historical -> canonical module relocations for archived contract examples (C-006).

Archived contract examples under ``kitty-specs/*/contracts/*.md`` are immutable
snapshots (C-006): once a mission's contracts are written, the mission's own
files are never edited to track a later module rename. When the codebase moves
a module referenced by a ``# pydantic_model:`` frontmatter line, the archived
contract keeps naming the historical dotted path forever.

This module is the test-side authority that bridges that gap. It knows about
four historical -> canonical relocations that the round-trip gate
(``test_example_round_trip.py``) needs in order to import the real, current
model for an archived, historically-named reference:

* ``specify_cli.next._internal_runtime`` -> ``runtime.next._internal_runtime``
* ``doctrine.drg`` -> ``charter.offering.drg``
* ``charter.schemas`` -> ``charter.activation.schemas``
* ``charter.scope`` -> ``charter.activation.scope``

Nothing here mutates or reads the archived contracts themselves; it only
rewrites the module portion of a dotted import path before ``importlib``
resolves it.
"""

from __future__ import annotations

import importlib
from collections.abc import Mapping
from types import ModuleType
from typing import Final

HISTORICAL_TO_CANONICAL: Final[Mapping[str, str]] = {
    "specify_cli.next._internal_runtime": "runtime.next._internal_runtime",
    "doctrine.drg": "charter.offering.drg",
    "charter.schemas": "charter.activation.schemas",
    "charter.scope": "charter.activation.scope",
}


def canonical_module_name(historical: str) -> str | None:
    """Rewrite ``historical`` to its canonical dotted path, or return ``None``.

    Matching is whole-dotted-segment only: ``historical`` must equal a
    relocation key exactly, or start with ``"<key>."`` — so
    ``charter.scope`` matches the ``charter.scope`` row but ``charter.scoped``
    does not. When more than one row could match, the longest key wins: the
    lookup order is derived from :data:`HISTORICAL_TO_CANONICAL` itself
    (sorted by dotted-segment count, descending) on every call, so a test
    that swaps the map in gets the production ordering for free. No caching
    is needed; the map is tiny.
    """
    for key in sorted(HISTORICAL_TO_CANONICAL, key=lambda k: k.count("."), reverse=True):
        if historical == key or historical.startswith(f"{key}."):
            canonical = HISTORICAL_TO_CANONICAL[key]
            return canonical + historical[len(key) :]
    return None


def import_contract_module(dotted: str) -> ModuleType:
    """Import ``dotted``, falling back to its canonical relocation on failure.

    Tries the historical name first (still correct for any module that never
    moved). On ``ImportError``, consults :data:`HISTORICAL_TO_CANONICAL` for a
    matching relocation row and retries under the canonical name. Raises
    ``ImportError`` naming both the historical and canonical module when
    neither imports, or naming just the historical module when no relocation
    row matches at all.
    """
    try:
        return importlib.import_module(dotted)
    except ImportError as exc:
        canonical = canonical_module_name(dotted)
        if canonical is None:
            raise ImportError(f"``{dotted}`` is not importable and no relocation row matches in ``tests/contract/_module_relocations.py``: {exc}") from exc
        try:
            return importlib.import_module(canonical)
        except ImportError as canonical_exc:
            raise ImportError(f"neither ``{dotted}`` nor canonical ``{canonical}`` is importable: {canonical_exc}") from canonical_exc
