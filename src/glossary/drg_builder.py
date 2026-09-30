"""Glossary DRG layer builder.

Builds a :class:`DRGGraph` layer whose nodes represent active glossary terms
and whose edges link every DRG action node to the vocabulary terms it uses.
The produced layer is consumed by the chokepoint (WP02) to resolve
``glossary:<id>`` URNs against doctrine action nodes at runtime.
"""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass
from pathlib import Path

from charter.drg import DRGEdge, DRGGraph, DRGNode, NodeKind, Relation
from kernel.clock import now_utc_iso

from .models import SenseStatus, TermSense
from .store import GlossaryStore

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# URN derivation
# ---------------------------------------------------------------------------


def glossary_urn(surface_text: str) -> str:
    """Derive a stable glossary:<id> URN from a canonical surface form.

    The first 8 hex digits of the SHA-256 digest of the UTF-8 encoded surface
    text are used as the identifier. The function is pure and collision-free in
    practice for the expected vocabulary sizes (<10 k terms).

    Args:
        surface_text: Canonical (lower-cased, trimmed) surface form.

    Returns:
        A stable URN of the form ``glossary:<8-hex-chars>``.

    Example:
        >>> glossary_urn("lane")
        'glossary:d93244e7'
    """
    hex_id = hashlib.sha256(surface_text.encode()).hexdigest()[:8]  # noqa: TID251 - production raw SHA-256 owner
    return f"glossary:{hex_id}"


# ---------------------------------------------------------------------------
# Lightweight lemmatizer (_normalize)
# ---------------------------------------------------------------------------

# Suffix rules applied left-to-right; the *first* rule that reduces the token
# to >= _MIN_STEM_LEN characters wins. ``es$`` is intentionally absent because
# applying it before ``s$`` would turn "lanes" into "lan" rather than "lane".
_SUFFIX_RULES: list[tuple[str, str]] = [
    (r"ments$", ""),
    (r"ment$", ""),
    (r"tions$", ""),
    (r"tion$", ""),
    (r"ness$", ""),
    (r"ings$", ""),
    (r"ing$", ""),
    (r"ers$", ""),
    (r"ed$", ""),
    (r"er$", ""),
    (r"s$", ""),
]
_MIN_STEM_LEN = 3


def _normalize(token: str) -> str:
    """Lightweight lemmatizer: lowercase + suffix stripping.

    Applies a priority-ordered list of suffix rules. The first rule that
    produces a candidate with at least ``_MIN_STEM_LEN`` characters is
    accepted. If no rule applies the lower-cased, stripped token is returned
    unchanged.

    Args:
        token: Raw surface token (may be mixed case).

    Returns:
        Normalized stem string.

    Examples:
        >>> _normalize("lanes")
        'lane'
        >>> _normalize("missions")
        'mission'
    """
    token = token.lower().strip()
    for pattern, replacement in _SUFFIX_RULES:
        candidate = re.sub(pattern, replacement, token)
        if candidate != token and len(candidate) >= _MIN_STEM_LEN:
            return candidate
    return token


# ---------------------------------------------------------------------------
# GlossaryTermIndex dataclass + builder
# ---------------------------------------------------------------------------


@dataclass
class GlossaryTermIndex:
    """Pre-built lookup index for glossary term resolution.

    Both the canonical surface form and its normalized (lemmatized) alias map
    to the same ``glossary:<id>`` URN. The index is consumed by the chokepoint
    (WP02) to match tokens in step inputs against glossary nodes without
    repeated URN derivation.

    Attributes:
        surface_to_urn: Maps normalized surface -> ``glossary:<id>`` URN.
        surface_to_senses: Maps normalized surface -> list of active
            :class:`~glossary.models.TermSense` objects.
        applicable_scope_set: Frozenset of scope strings that contributed
            senses to the index.
        term_count: Total number of unique URNs in the index.
    """

    surface_to_urn: dict[str, str]
    surface_to_senses: dict[str, list[TermSense]]
    applicable_scope_set: frozenset[str]
    term_count: int


def build_index(
    store: GlossaryStore,
    applicable_scopes: list[str],
) -> GlossaryTermIndex:
    """Build a :class:`GlossaryTermIndex` from the in-memory store.

    Only ``ACTIVE`` senses whose scope is in *applicable_scopes* are
    indexed. For each active sense both the canonical surface form and its
    ``_normalize``-d alias are mapped to the same ``glossary:<id>`` URN.
    Collision warnings are emitted when two distinct canonical surfaces hash
    to the same URN (extremely unlikely with 8-hex-char SHA-256 prefixes).

    Args:
        store: Populated :class:`~glossary.store.GlossaryStore`.
        applicable_scopes: Scope strings (``GlossaryScope.value``) to
            include in the index; senses in other scopes are skipped.

    Returns:
        A fully populated :class:`GlossaryTermIndex`.
    """
    scope_set = frozenset(applicable_scopes)
    surface_to_urn: dict[str, str] = {}
    surface_to_senses: dict[str, list[TermSense]] = {}
    urn_to_canonical: dict[str, str] = {}  # for collision detection

    # GlossaryStore._cache is the internal dict[scope_str, dict[surface, list[TermSense]]].
    # GlossaryStore has no event-log loader, so the only way to populate the
    # store is via add_sense(). We access _cache directly
    # here because no public iteration API exists yet. When GlossaryStore gains a
    # public iterator, replace this access. See RISK-2 in the mission-094 review.
    for scope_key, surfaces in store._cache.items():
        if scope_key not in scope_set:
            continue
        for _surface_text, senses in surfaces.items():
            for sense in senses:
                if sense.status is not SenseStatus.ACTIVE:
                    continue

                canonical = sense.surface.surface_text
                urn = glossary_urn(canonical)

                # Collision detection (extremely unlikely in practice)
                if urn in urn_to_canonical and urn_to_canonical[urn] != canonical:
                    logger.warning(
                        "glossary URN collision: %r and %r both map to %s",
                        urn_to_canonical[urn],
                        canonical,
                        urn,
                    )
                urn_to_canonical[urn] = canonical

                # Map canonical surface → URN and senses
                if canonical not in surface_to_urn:
                    surface_to_urn[canonical] = urn
                if canonical not in surface_to_senses:
                    surface_to_senses[canonical] = []
                surface_to_senses[canonical].append(sense)

                # Map normalized (lemmatized) alias → same URN and senses
                normalized = _normalize(canonical)
                if normalized != canonical:
                    if normalized not in surface_to_urn:
                        surface_to_urn[normalized] = urn
                    if normalized not in surface_to_senses:
                        surface_to_senses[normalized] = []
                    surface_to_senses[normalized].append(sense)

    # term_count = number of distinct URNs (= number of distinct canonical surfaces)
    term_count = len(urn_to_canonical)

    return GlossaryTermIndex(
        surface_to_urn=surface_to_urn,
        surface_to_senses=surface_to_senses,
        applicable_scope_set=scope_set,
        term_count=term_count,
    )


# ---------------------------------------------------------------------------
# DRG layer builder
# ---------------------------------------------------------------------------


def build_glossary_drg_layer(
    store: GlossaryStore,
    applicable_scopes: list[str],
    repo_root: Path,
) -> DRGGraph:
    """Build the glossary DRG layer from the active glossary store.

    Mints one :class:`~charter.offering.drg.models.DRGNode` of kind
    ``NodeKind.GLOSSARY`` per unique active sense surface in
    *applicable_scopes*, then adds a
    ``Relation.VOCABULARY`` :class:`~charter.offering.drg.models.DRGEdge` for every
    (action URN, glossary URN) pair found in the built-in + project DRG graph.

    Args:
        store: Populated :class:`~glossary.store.GlossaryStore`.
        applicable_scopes: Scope strings to include.
        repo_root: Project root used to locate the optional project DRG
            overlay at ``<repo_root>/.kittify/doctrine/graph.yaml``.

    Returns:
        A :class:`DRGGraph` with ``generated_by="glossary-drg-builder-v1"``.
    """
    from charter.activation._drg_helpers import load_validated_graph

    index = build_index(store, applicable_scopes)

    # 1. Mint one GLOSSARY node per unique canonical surface.
    # See the _cache access comment in build_index() above re: RISK-2.
    nodes: list[DRGNode] = []
    seen_urns: set[str] = set()
    for scope_key, surfaces in store._cache.items():
        if scope_key not in index.applicable_scope_set:
            continue
        for _surface_text, senses in surfaces.items():
            for sense in senses:
                if sense.status is not SenseStatus.ACTIVE:
                    continue
                canonical = sense.surface.surface_text
                urn = glossary_urn(canonical)
                if urn not in seen_urns:
                    nodes.append(
                        DRGNode(
                            urn=urn,
                            kind=NodeKind.GLOSSARY,
                            label=canonical,
                        )
                    )
                    seen_urns.add(urn)

    # 2. Load built-in action URNs
    merged_graph = load_validated_graph(repo_root)
    action_urns = [n.urn for n in merged_graph.nodes if n.kind == NodeKind.ACTION]

    # 3. Build VOCABULARY edges: every action → every glossary term
    edges: list[DRGEdge] = []
    glossary_urns = list(seen_urns)
    for action_urn in action_urns:
        for g_urn in glossary_urns:
            edges.append(
                DRGEdge(
                    source=action_urn,
                    target=g_urn,
                    relation=Relation.VOCABULARY,
                )
            )

    return DRGGraph(
        schema_version="1.0",
        generated_at=now_utc_iso(),
        generated_by="glossary-drg-builder-v1",
        nodes=nodes,
        edges=edges,
    )


__all__ = [
    "GlossaryTermIndex",
    # build_glossary_drg_layer, glossary_urn: demoted — no cross-module src/
    # from-import callers (WP01 harden-dead-symbol-gate-01KW0RJR).
    "build_index",
]
