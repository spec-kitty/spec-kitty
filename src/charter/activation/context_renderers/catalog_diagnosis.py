"""Catalog-miss diagnosis leaf (WP04 T018, #2532).

Relocated verbatim from ``charter.activation.context`` (single-owner, no-net-growth for
that file). Depends only on :mod:`charter.activation._catalog_miss` — a genuine LEAF in
the ``profile_sections.py`` import-cycle dissolution (research.md Decision 7 /
Decision 12): ``profile_sections.py`` imports these two symbols at top level
instead of function-locally re-entering ``charter.activation.context``.
"""

from __future__ import annotations

import logging
from pathlib import Path

from charter.activation._catalog_miss import (
    CatalogMissDiagnosis,
    classify_catalog_miss,
    classify_scope_filtered_miss,
)

# ``_available_catalog_ids`` de-exported after the context.py re-export shim
# retirement (doctrine-built-in-seam-consolidation WP06): no external ``src/``
# importer remains. It stays a module-internal helper used below.
__all__ = [
    "_diagnose_catalog_miss",
]


_LOGGER = logging.getLogger(__name__)


def _diagnose_catalog_miss(
    missing_id: str,
    repository: object | None,
    *,
    repo_root: Path | None = None,
) -> CatalogMissDiagnosis:
    """Return the best-fit :class:`CatalogMissDiagnosis` for *missing_id*.

    Checks whether the repository recorded *missing_id* as scope-filtered
    (present on disk but excluded by the active language scope) before
    falling back to the fuzzy-match :func:`classify_catalog_miss`.  This
    is the single gate that implements FR-013 end-to-end: any call site
    that previously called ``classify_catalog_miss`` directly now calls
    this helper instead, so scope-filtered misses are never surfaced as
    ``MISSING_ARTIFACT``.

    Active-language context is read directly from the repository's own
    ``_active_languages`` attribute (the value already stored at
    construction time. *repo_root*, when the caller has it, is used
    verbatim for the scope-filtered classification; otherwise the root is
    inferred from the repository's project layer as a fallback.
    """
    scope_filtered: frozenset[str] | set[str] = getattr(
        repository, "scope_filtered_ids", frozenset()
    )
    if isinstance(scope_filtered, (set, frozenset)) and missing_id in scope_filtered:
        active_languages: list[str] | None = getattr(
            repository, "_active_languages", None
        )
        return classify_scope_filtered_miss(missing_id, active_languages, repo_root if repo_root is not None else _repository_repo_root(repository))
    return classify_catalog_miss(missing_id, _available_catalog_ids(repository))


def _repository_repo_root(repository: object | None) -> Path | None:
    """Best-effort project root of *repository*: the nearest ancestor of its project layer holding ``.kittify``.

    ``None`` (built-in vocabulary only) when the repository has no project
    layer or it does not live inside a Spec Kitty project.
    """
    project_dir = getattr(repository, "_project_dir", None)
    if not isinstance(project_dir, Path):
        return None
    return next((parent for parent in (project_dir, *project_dir.parents) if (parent / ".kittify").is_dir()), None)


def _available_catalog_ids(repository: object | None) -> list[str]:
    """Return the IDs the repository carries, for fuzzy-match suggestions.

    Used by the catalog-miss diagnosis path (RISK-3 from the Mission B
    post-merge review).  Defensive against stub repositories used in
    tests that may not implement ``list_all`` / ``all``; returns an
    empty list when no listing API is available.
    """
    if repository is None:
        return []
    for attr in ("list_all", "all"):
        ids = _ids_via_listing_attr(repository, attr)
        if ids:
            return ids
    # Fall back to introspecting the stub's internal ``_items`` dict
    # (used by the test doubles in ``tests/charter/`` so we can suggest
    # close matches without forcing every stub to grow a ``list_all``).
    return _ids_from_items_dict(repository)


def _ids_via_listing_attr(repository: object, attr: str) -> list[str] | None:
    """Return IDs from calling *repository*'s *attr* lister, or ``None``.

    ``None`` means "this lister is absent or unusable" (caller falls
    through to the next attempt); an empty list is a genuine "listed zero
    ids" result and is distinguished by the caller only in that both are
    falsy — matching the original inline ``continue``-on-failure /
    fall-through-on-empty behaviour.
    """
    lister = getattr(repository, attr, None)
    if not callable(lister):
        return None
    try:
        items = lister()
    except Exception as exc:  # noqa: BLE001 — best-effort introspection
        _LOGGER.debug(
            "Catalog listing via %s() raised %r; falling back.",
            attr,
            exc,
        )
        return None
    ids: list[str] = []
    for item in items or []:
        ident = getattr(item, "id", None)
        if isinstance(ident, str) and ident:
            ids.append(ident)
    return ids


def _ids_from_items_dict(repository: object) -> list[str]:
    """Return string keys of the stub repository's internal ``_items`` dict."""
    items = getattr(repository, "_items", None)
    if isinstance(items, dict):
        return [k for k in items if isinstance(k, str)]
    return []
