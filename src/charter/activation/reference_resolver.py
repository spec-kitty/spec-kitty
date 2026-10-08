"""Thin charter-facing wrapper around the DRG transitive reference resolver."""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from charter.activation._drg_helpers import load_validated_graph
from charter.activation.catalog import resolve_offering_root
from charter.activation.drg_activation import filter_graph_by_activation
from charter.offering.drg.loader import load_built_in_graph
from charter.offering.drg.models import DRGGraph, Relation
from charter.offering.drg.query import ResolveTransitiveRefsResult, resolve_transitive_refs
from charter.offering.drg.validator import assert_valid

if TYPE_CHECKING:
    from charter.activation.pack_context import PackContext

__all__ = [
    "resolve_references_transitively",
]


def resolve_references_transitively(
    directive_ids: list[str],
    doctrine_service: object,
    *,
    graph: DRGGraph | None = None,
    repo_root: Path | None = None,
    pack_context: PackContext | None = None,
) -> ResolveTransitiveRefsResult:
    """Resolve transitive doctrine artifacts reachable from *directive_ids*.

    This preserves the public charter helper contract while delegating the
    actual traversal to ``charter.offering.drg.query.resolve_transitive_refs``.

    Parameters
    ----------
    pack_context:
        When provided, the merged DRG is filtered by activation state
        (FR-032, FR-036, WP08) before transitive resolution. Pass ``None``
        to skip the filter (backward-compatible behaviour).
    """
    _ = doctrine_service

    if not directive_ids:
        return ResolveTransitiveRefsResult()

    resolved_graph = graph
    if resolved_graph is None:
        try:
            if repo_root is not None:
                resolved_graph = load_validated_graph(repo_root)
            else:
                doctrine_root = resolve_offering_root()
                if not doctrine_root.exists():
                    return ResolveTransitiveRefsResult(directives=sorted(directive_ids))
                resolved_graph = load_built_in_graph()
                assert_valid(resolved_graph)
        except FileNotFoundError:
            return ResolveTransitiveRefsResult(directives=sorted(directive_ids))

    if resolved_graph is None:
        return ResolveTransitiveRefsResult(directives=sorted(directive_ids))

    # FR-032, FR-036 (WP08): apply activation filter before transitive resolution.
    if pack_context is not None:
        resolved_graph = filter_graph_by_activation(resolved_graph, pack_context)

    return resolve_transitive_refs(
        resolved_graph,
        start_urns={f"directive:{directive_id}" for directive_id in directive_ids},
        relations={Relation.REQUIRES, Relation.SUGGESTS},
    )
