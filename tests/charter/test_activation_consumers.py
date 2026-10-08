"""T010-T013 (WP03, mission ``drg-relation-parity-activation-gate-01KY48PD``,
#2843).

Five-consumer regression net (NFR-002) for the four ``charter.*`` callers of
``charter.activation.drg_activation.filter_graph_by_activation`` (the executor consumer, T009, is
covered separately in
``tests/specify_cli/mission_step_contracts/test_executor_activation.py``):

- ``reference_resolver.py:67`` (T010)
- ``compiler.py:1037`` closure (T011)
- ``consistency_check.py::_check_drg_cross_kind_refs`` (``:424``) (T012)
- ``context.py:928`` (T013)

Each gets a before/after test asserting a **named observable** (never smoke):

- ``None``-path -> **structural identity**: the consumer's real output when
  fed a genuinely unfiltered path (``pack_context=None``, or -- for the one
  consumer with no such skip branch, T012 -- the raw unfiltered graph
  compared directly at the gate) must equal its output when fed a
  ``PackContext`` whose per-kind activation fields are all ``None``
  (default-allow). Both sides are computed live in the test; no merge-base
  literal is hand-typed.
- populated-path -> **demonstrably RED on merge-base**: the real built-in
  stem ``001-architectural-integrity-standard`` (WP01's characterization
  pair, ``tests/charter/test_drg_activation_gate.py``) resolves to the
  canonical ``directive:DIRECTIVE_001``. On merge-base,
  ``_node_is_activated`` Step 3 compared the node's bare canonical id
  directly against the raw stem -- they never match, so this node was
  silently dropped whenever ``activated_directives`` was populated. Each
  test below asserts the corrected consumer retains/reaches this node; on
  merge-base (dropped node) the same assertion would fail (documented
  per-test below).

Fixtures are built inline against the REAL built-in doctrine corpus (never a
hermetic ``id==stem`` fixture, per NFR-001) and NOT added to
``tests/charter/conftest.py`` (shared with sibling WP01/WP02 lanes) per the
WP's instruction.
"""

from __future__ import annotations

from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest
from ruamel.yaml import YAML

from charter.activation.compiler import _resolve_transitive_reference_graph
from charter.activation.consistency_check import _check_drg_cross_kind_refs
from charter.activation.context import _load_action_governance_bundle
from charter.activation.invocation_context import ProjectContext
from charter.activation.pack_context import _BUILTIN_ARTIFACT_KINDS, PackContext
from charter.activation.reference_resolver import resolve_references_transitively
from charter.offering.drg.models import DRGGraph, DRGNode, NodeKind

pytestmark = [pytest.mark.unit]

# Real built-in stem/canonical pair (verified on disk -- see
# ``tests/charter/test_drg_activation_gate.py`` for the original
# characterization; reused here, not re-derived hermetically, per NFR-001).
_REAL_DIRECTIVE_STEM = "001-architectural-integrity-standard"
_REAL_DIRECTIVE_CANONICAL_ID = "DIRECTIVE_001"
_REAL_DIRECTIVE_CANONICAL_URN = f"directive:{_REAL_DIRECTIVE_CANONICAL_ID}"
# Real built-in edge (verified on disk): DIRECTIVE_001 requires this tactic,
# whose canonical id equals its config stem (no reconciliation gap for
# tactics -- only directives carry the numeric-canonical/stem mismatch WP01
# fixed), so it survives the gate identically before and after the fix.
_REAL_TACTIC_STEM = "paula-patterns-architecture-scout-review"
_REAL_TACTIC_CLI_KIND = "tactic"


def _pack_context(
    *,
    activated_directives: frozenset[str] | None,
    activated_kinds: frozenset[str] = frozenset({"directives"}),
    activated_tactics: frozenset[str] | None = None,
    activated_mission_types: frozenset[str] = frozenset(),
    repo_root: Path,
) -> PackContext:
    return PackContext(
        activated_kinds=activated_kinds,
        activated_mission_types=activated_mission_types,
        pack_roots=(),
        org_pack_names=(),
        repo_root=repo_root,
        activated_directives=activated_directives,
        activated_tactics=activated_tactics,
    )


def _single_directive_graph() -> DRGGraph:
    """A hermetic graph carrying only the real ``DIRECTIVE_001`` node.

    Used as a ``graph=`` override for consumers that accept one directly
    (T010); the node's URN is the real canonical id so the gate's
    filesystem-backed stem resolution (which reads the real doctrine corpus
    regardless of which graph the node lives in) recognizes it.
    """
    return DRGGraph.model_construct(
        schema_version="1.0",
        generated_at="2026-07-22T00:00:00Z",
        generated_by="test",
        nodes=[DRGNode(urn=_REAL_DIRECTIVE_CANONICAL_URN, kind=NodeKind.DIRECTIVE)],
        edges=[],
    )


# ---------------------------------------------------------------------------
# T010 -- charter/reference_resolver.py:67
# ---------------------------------------------------------------------------
# Observable: ``ResolveTransitiveRefsResult.directives`` (bare canonical ids)
# from ``resolve_references_transitively``.


def test_reference_resolver_none_path_matches_no_filter_at_all(tmp_path: Path) -> None:
    graph = _single_directive_graph()

    unfiltered = resolve_references_transitively(
        [_REAL_DIRECTIVE_CANONICAL_ID], doctrine_service=None, graph=graph, pack_context=None
    )
    default_allow_ctx = _pack_context(activated_directives=None, repo_root=tmp_path)
    default_allow = resolve_references_transitively(
        [_REAL_DIRECTIVE_CANONICAL_ID],
        doctrine_service=None,
        graph=graph,
        pack_context=default_allow_ctx,
    )

    assert unfiltered.directives == default_allow.directives == [_REAL_DIRECTIVE_CANONICAL_ID]


def test_reference_resolver_populated_stem_retains_directive_node() -> None:
    """RED on merge-base: seeding ``resolve_transitive_refs`` with
    ``directive:DIRECTIVE_001`` only reaches the ``directives`` bucket if the
    node survives ``filter_graph_by_activation`` first (reference_resolver.py
    :67). On merge-base the populated stem drops the node entirely -- the
    seed URN would resolve to no graph node and land in ``unresolved``
    instead of ``directives``. After WP01 the stem resolves to the canonical
    URN and the node (and this assertion) survives."""
    graph = _single_directive_graph()
    ctx = _pack_context(
        activated_directives=frozenset({_REAL_DIRECTIVE_STEM}), repo_root=Path("/nonexistent")
    )

    result = resolve_references_transitively(
        [_REAL_DIRECTIVE_CANONICAL_ID], doctrine_service=None, graph=graph, pack_context=ctx
    )

    assert result.directives == [_REAL_DIRECTIVE_CANONICAL_ID]
    assert result.unresolved == []


# ---------------------------------------------------------------------------
# T011 -- charter/compiler.py:1037 closure (``_resolve_transitive_reference_graph``)
# ---------------------------------------------------------------------------
# Observable: the closure-filtered ``ResolveTransitiveRefsResult.directives``
# -- distinct from the compiler's surviving ``:88`` references.yaml
# projection, which this WP does not touch.


def test_compiler_closure_none_path_matches_no_filter_at_all(tmp_path: Path) -> None:
    from charter.activation.catalog import resolve_offering_root

    offering_root = resolve_offering_root()

    unfiltered = _resolve_transitive_reference_graph(
        offering_root=offering_root,
        directives=[_REAL_DIRECTIVE_CANONICAL_ID],
        repo_root=tmp_path,
        pack_context=None,
    )
    # Full built-in kind set: the real DIRECTIVE_001 closure spans several
    # kinds (tactics, procedures, ...); restricting ``activated_kinds`` here
    # would cut the closure short via the KIND-level gate (a different gate
    # step than the one under test) and produce a false mismatch unrelated
    # to the per-ID stem/canonical fix.
    default_allow_ctx = _pack_context(
        activated_directives=None, activated_kinds=_BUILTIN_ARTIFACT_KINDS, repo_root=tmp_path
    )
    default_allow = _resolve_transitive_reference_graph(
        offering_root=offering_root,
        directives=[_REAL_DIRECTIVE_CANONICAL_ID],
        repo_root=tmp_path,
        pack_context=default_allow_ctx,
    )

    assert _REAL_DIRECTIVE_CANONICAL_ID in unfiltered.directives
    assert unfiltered.directives == default_allow.directives


def test_compiler_closure_populated_stem_retains_directive_node(tmp_path: Path) -> None:
    """RED on merge-base: the compiler's transitive closure walks the merged
    built-in+project DRG (real corpus -- ``DIRECTIVE_001`` genuinely exists
    there) through the same gate. On merge-base the populated stem drops the
    node before the closure walk starts, so the seeded id never reaches the
    ``directives`` bucket. After WP01 it does."""
    from charter.activation.catalog import resolve_offering_root

    ctx = _pack_context(
        activated_directives=frozenset({_REAL_DIRECTIVE_STEM}), repo_root=tmp_path
    )

    result = _resolve_transitive_reference_graph(
        offering_root=resolve_offering_root(),
        directives=[_REAL_DIRECTIVE_CANONICAL_ID],
        repo_root=tmp_path,
        pack_context=ctx,
    )

    assert _REAL_DIRECTIVE_CANONICAL_ID in result.directives


# ---------------------------------------------------------------------------
# T012 -- charter/consistency_check.py::_check_drg_cross_kind_refs (:424)
# ---------------------------------------------------------------------------
# Observable: ``missing_from_doctrine`` -- the KIND-level cross-ref gap
# report. The check only inspects an edge if BOTH its endpoints survive
# ``filter_graph_by_activation`` first, so a directive node the gate silently
# drops means its outgoing edges are never inspected -- a legitimate
# "target kind explicitly empty" finding goes unreported (a false negative).
# Real built-in edge used: ``directive:DIRECTIVE_001 --requires-->
# tactic:paula-patterns-architecture-scout-review``. The tactic's canonical
# id equals its config stem (no reconciliation gap for tactics), so it is
# populated identically in every case below and never confounds the
# directive-side assertion under test.


def test_cross_kind_refs_none_path_matches_no_filter_at_all(tmp_path: Path) -> None:
    """Structural identity at the gate: with every per-kind field ``None``
    (default-allow), ``filter_graph_by_activation`` must be a no-op, so the
    check's report is unaffected by having gone through the gate at all."""
    from charter.activation._drg_helpers import load_validated_graph
    from charter.activation.drg_activation import filter_graph_by_activation

    full_drg = load_validated_graph(tmp_path)
    # Full kind set the gate itself recognizes (``_SINGULAR_TO_PLURAL``'s
    # range) -- a superset of ``_BUILTIN_ARTIFACT_KINDS`` (which omits
    # ``anti_patterns``, a real kind present in the built-in corpus).
    # Restricting ``activated_kinds`` to anything narrower would drop
    # unrelated nodes/edges via the KIND-level gate, producing a false
    # mismatch unrelated to the per-ID stem/canonical fix under test.
    from charter.activation.drg_activation import _SINGULAR_TO_PLURAL

    # ``mission_step_contract`` nodes gate on ``activated_mission_types`` (a
    # SEPARATE axis from ``activated_kinds`` — see ``filter_graph_by_activation``
    # docstring), so a genuine default-allow must also activate every mission
    # type owning an MSC node in the corpus, else those nodes drop and this
    # no-op assertion falsely fails. Derived from the graph so new built-in
    # mission types stay covered automatically.
    _MSC_PREFIX = "mission_step_contract:"
    all_mission_types = frozenset(
        n.urn[len(_MSC_PREFIX):].split("/", 1)[0]
        for n in full_drg.nodes
        if n.urn.startswith(_MSC_PREFIX)
    )
    default_allow_ctx = _pack_context(
        activated_directives=None,
        activated_tactics=None,
        activated_kinds=frozenset(_SINGULAR_TO_PLURAL.values()),
        activated_mission_types=all_mission_types,
        repo_root=tmp_path,
    )
    activated_drg = filter_graph_by_activation(full_drg, default_allow_ctx)
    assert {n.urn for n in activated_drg.nodes} == {n.urn for n in full_drg.nodes}
    assert {(e.source, e.target) for e in activated_drg.edges} == {
        (e.source, e.target) for e in full_drg.edges
    }

    ctx = ProjectContext(repo_root=tmp_path, pack_context=default_allow_ctx)
    missing_from_doctrine: list[str] = []
    suggestions: list[str] = []
    _check_drg_cross_kind_refs(
        ctx,
        {"directive": None, "tactic": None},
        missing_from_doctrine,
        suggestions,
    )

    assert missing_from_doctrine == []


def test_cross_kind_refs_populated_stem_surfaces_kind_gap(tmp_path: Path) -> None:
    """RED on merge-base: with ``activated_directives`` populated by the real
    stem, DIRECTIVE_001 (and, on merge-base, every other directive node too)
    is dropped -- so the real ``requires`` edge from DIRECTIVE_001 to the
    tactic is dropped alongside it, and this KIND-level check never inspects
    it, so it never flags ``tactic/<all>`` as missing even though the tactic
    activation set is explicitly empty. After WP01 the stem resolves,
    DIRECTIVE_001 (and its edge) survives, and the check correctly flags the
    gap -- proving the fix reaches this consumer's report."""
    ctx = ProjectContext(
        repo_root=tmp_path,
        pack_context=_pack_context(
            activated_directives=frozenset({_REAL_DIRECTIVE_STEM}),
            activated_tactics=frozenset({_REAL_TACTIC_STEM}),
            activated_kinds=frozenset({"directives", "tactics"}),
            repo_root=tmp_path,
        ),
    )
    # The reporting-level activation dict (independent parameter, matching
    # production's separately-loaded raw config lists) marks tactics as
    # explicitly empty -- the "target kind gap" condition -- while the
    # PackContext above keeps the real tactic node alive in the graph (its
    # id resolves identically pre/post WP01) so only the DIRECTIVE_001
    # retention decides whether the edge is inspected at all.
    activated_by_kind = {
        "directive": frozenset({_REAL_DIRECTIVE_STEM}),
        "tactic": frozenset(),
    }
    missing_from_doctrine: list[str] = []
    suggestions: list[str] = []

    _check_drg_cross_kind_refs(ctx, activated_by_kind, missing_from_doctrine, suggestions)

    assert f"{_REAL_TACTIC_CLI_KIND}/<all>" in missing_from_doctrine


# ---------------------------------------------------------------------------
# T013 -- charter/context.py:928 (``_load_action_governance_bundle``)
# ---------------------------------------------------------------------------
# Observable: ``_ActionGovernanceBundle.directive_ids`` -- the resolved
# context's activated directive set.

_ACTION_GRAPH_WITH_DIRECTIVE_001 = {
    "schema_version": "1.0",
    "generated_at": "2026-07-22T00:00:00Z",
    "generated_by": "test",
    "nodes": [
        {"urn": "action:software-dev/implement", "kind": "action", "label": "implement"},
        {
            "urn": _REAL_DIRECTIVE_CANONICAL_URN,
            "kind": "directive",
            "label": "Architectural Integrity Standard",
        },
    ],
    "edges": [
        {
            "source": "action:software-dev/implement",
            "target": _REAL_DIRECTIVE_CANONICAL_URN,
            "relation": "scope",
        }
    ],
}


def _action_graph() -> DRGGraph:
    yaml = YAML(typ="safe")
    buf = StringIO()
    yaml.dump(_ACTION_GRAPH_WITH_DIRECTIVE_001, buf)
    buf.seek(0)
    return DRGGraph.model_validate(yaml.load(buf))


def test_context_bundle_none_path_matches_no_filter_at_all(tmp_path: Path) -> None:
    graph = _action_graph()

    with patch("charter.activation._drg_helpers.load_validated_graph", return_value=graph):
        unfiltered = _load_action_governance_bundle(
            repo_root=tmp_path,
            action="implement",
            effective_depth=2,
            mission_type="software-dev",
            pack_context=None,
        )
        default_allow_ctx = _pack_context(activated_directives=None, repo_root=tmp_path)
        default_allow = _load_action_governance_bundle(
            repo_root=tmp_path,
            action="implement",
            effective_depth=2,
            mission_type="software-dev",
            pack_context=default_allow_ctx,
        )

    assert unfiltered.directive_ids == default_allow.directive_ids == [_REAL_DIRECTIVE_CANONICAL_ID]


def test_context_bundle_populated_stem_retains_directive_node(tmp_path: Path) -> None:
    """RED on merge-base: the action is scoped directly to DIRECTIVE_001 in
    the (already-filtered) graph resolved at context.py:928. On merge-base
    the populated stem drops the node before ``resolve_context`` walks the
    ``scope`` edge, so ``directive_ids`` would be empty. After WP01 the stem
    resolves and the directive is retained."""
    graph = _action_graph()
    ctx = _pack_context(
        activated_directives=frozenset({_REAL_DIRECTIVE_STEM}), repo_root=tmp_path
    )

    with patch("charter.activation._drg_helpers.load_validated_graph", return_value=graph):
        bundle = _load_action_governance_bundle(
            repo_root=tmp_path,
            action="implement",
            effective_depth=2,
            mission_type="software-dev",
            pack_context=ctx,
        )

    assert bundle.directive_ids == [_REAL_DIRECTIVE_CANONICAL_ID]
