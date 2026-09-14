"""Activation-gate canonical-URN correctness (WP01, mission
``drg-relation-parity-activation-gate-01KY48PD``, #2843).

The bug (research.md D1): ``_node_is_activated`` Step 3 (``charter/drg.py``)
compares a DRG node's **canonical** id (e.g. ``DIRECTIVE_001``) against
``PackContext.activated_directives``, which holds config **stems** (e.g.
``001-architectural-integrity-standard``). They never match, so any populated
per-kind activation set silently drops every node of that kind.

Covers (see ``contracts/activation-gate-contract.md`` for the full behavioral
table -- these tests are the RED/GREEN attribution proof it requires,
NFR-001):

- ``test_stem_form_activation_survives_the_gate``: RED on merge-base (the
  node is dropped because the stem never equals the canonical id compared at
  ``drg.py:319``); GREEN after the WP01 fix.
- ``test_canonical_form_control_isolates_the_merge_base_defect``: sibling
  GREEN control at merge-base -- an entry that already equals the canonical
  id passes there too, isolating the defect as stem<->canonical mismatch,
  not an incidental populated-list bug. Post-fix its expectation flips (see
  its docstring): C-002 (require-canonical) makes a raw canonical id an
  unsupported ``activated_directives`` entry.
- ``test_non_activated_directive_is_still_excluded``: proves the gate still
  filters (a populated set that does not include the node's canonical id
  drops it).
- ``test_root_divergence_follows_resolve_doctrine_root``: install-layout
  guard (research.md D2) -- the gate must source ``doctrine_root`` from
  ``charter.activation.catalog.resolve_doctrine_root()``, never
  ``pack_context.pack_roots[0]``.
- ``test_resolution_is_batched_once_not_per_node``: proves the stem-to-
  canonical resolution is hoisted once per filter call (O(kinds)), not
  invoked per node (O(nodes)) -- the complexity/perf constraint in the
  contract's "Implementation notes".
- ``test_unresolvable_kind_token_yields_empty_resolution``: direct coverage
  of the defensive ``MissionTypeNotAnArtifactKind`` catch in
  ``_resolve_activated_urns_for_kind`` -- unreachable via the gate's live
  fixed kind domain (mirrors the reference pattern at
  ``consistency_check.py:892-894`` for parity/symmetry), so it is exercised
  directly here rather than left untested.

Fixtures are built inline (real ``PackContext`` instances, real built-in DRG
corpus) per the WP's instruction not to touch the shared
``tests/charter/conftest.py`` (owned by sibling WP02/WP03 lanes).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from charter.activation import drg_activation as drg_module
from charter.activation.catalog import resolve_doctrine_root
from charter.drg import load_built_in_graph
from charter.activation.drg_activation import filter_graph_by_activation
from charter.activation.kind_vocabulary import MissionTypeNotAnArtifactKind
from charter.activation.pack_context import PackContext

pytestmark = [pytest.mark.unit]

# Real built-in artifacts (verified on disk, not a hermetic id==stem fixture --
# NFR-001 requires the real corpus + this repo's real stem/canonical shape).
_REAL_DIRECTIVE_STEM = "001-architectural-integrity-standard"
_REAL_DIRECTIVE_CANONICAL_URN = "directive:DIRECTIVE_001"
_OTHER_REAL_DIRECTIVE_STEM = "003-decision-documentation-requirement"
_OTHER_REAL_DIRECTIVE_CANONICAL_URN = "directive:DIRECTIVE_003"


def _pack_context(
    *,
    activated_directives: frozenset[str] | None,
    pack_roots: tuple[Path, ...] = (),
) -> PackContext:
    """Build a real, hermetic ``PackContext`` inline (no shared fixtures).

    ``pack_roots=()`` by default: the gate must resolve the built-in
    doctrine root via ``resolve_doctrine_root()``, never
    ``pack_context.pack_roots[0]`` (research.md D2), so an empty tuple here
    is itself a mild divergence check -- ``test_root_divergence_...`` below
    makes the same point explicitly with a *populated but wrong* root.
    """
    return PackContext(
        activated_kinds=frozenset({"directives"}),
        activated_mission_types=frozenset(),
        pack_roots=pack_roots,
        org_pack_names=(),
        repo_root=Path("/nonexistent"),
        activated_directives=activated_directives,
    )


def _real_graph_node_urns(pack_context: PackContext) -> frozenset[str]:
    graph = load_built_in_graph()
    filtered = filter_graph_by_activation(graph, pack_context)
    return frozenset(n.urn for n in filtered.nodes)


# ---------------------------------------------------------------------------
# Per-ID gate generalizes to any file-backed kind, not just directives.
# Guards the resolve-in-gate path for ``glossary_pack`` (a NON-directive,
# file-backed first-order kind added upstream by #1418) so a future resolver
# regression can't silently deactivate an explicitly-activated pack.
# ---------------------------------------------------------------------------

#: src/charter/offering/glossary_packs/built-in/spec-kitty-core.glossary-pack.yaml -> id spec-kitty-core
_REAL_GLOSSARY_PACK_STEM = "spec-kitty-core"


def _glossary_pack_survivors(
    activated_glossary_packs: frozenset[str] | None,
) -> set[str]:
    """Filter the built-in graph with ``glossary_packs`` activated to the given
    per-ID set; return the surviving ``glossary_pack:`` node URNs. ``pack_roots=()``
    + ``repo_root=/nonexistent`` force resolution through ``resolve_doctrine_root()``,
    exactly like the directive tests above.
    """
    ctx = PackContext(
        activated_kinds=frozenset({"glossary_packs"}),
        activated_mission_types=frozenset(),
        pack_roots=(),
        org_pack_names=(),
        repo_root=Path("/nonexistent"),
        activated_directives=None,
        activated_glossary_packs=activated_glossary_packs,
    )
    graph = load_built_in_graph()
    return {n.urn for n in filter_graph_by_activation(graph, ctx).nodes if n.urn.startswith("glossary_pack:")}


def test_populated_glossary_pack_activation_resolves_and_survives() -> None:
    """The WP01 resolve-in-gate rewrite must resolve a populated
    ``activated_glossary_packs`` stem to its canonical URN and RETAIN the node —
    proving the fix generalizes beyond directives to every file-backed kind
    (post-rebase integration with upstream #1418).
    """
    # populated-correct -> the pack survives (stem resolves to canonical URN)
    assert "glossary_pack:spec-kitty-core" in _glossary_pack_survivors(frozenset({_REAL_GLOSSARY_PACK_STEM}))


def test_populated_glossary_pack_bogus_stem_is_excluded() -> None:
    """A populated set with only an unresolvable stem excludes the pack node
    (skip-with-report leaves the resolved canonical set empty) — the gate does
    not silently keep an un-activated node."""
    assert _glossary_pack_survivors(frozenset({"does-not-exist"})) == set()


def test_none_glossary_pack_activation_default_allows() -> None:
    """``None`` per-ID set is default-allow: the pack node survives unchanged."""
    assert "glossary_pack:spec-kitty-core" in _glossary_pack_survivors(None)


# ---------------------------------------------------------------------------
# NFR-001 RED/GREEN attribution pair
# ---------------------------------------------------------------------------


def test_stem_form_activation_survives_the_gate() -> None:
    """RED on merge-base: a config-**stem** entry must still admit the node.

    ``.kittify/config.yaml`` (and every real project) populates
    ``activated_directives`` with stems, e.g. ``001-architectural-integrity-
    standard``, never the canonical ``DIRECTIVE_001`` id. On merge-base
    ``_node_is_activated`` compares the stem directly against the node's
    canonical id and never matches -- the node is dropped. After the WP01
    fix the stem resolves to its canonical URN and the node survives.
    """
    ctx = _pack_context(activated_directives=frozenset({_REAL_DIRECTIVE_STEM}))

    surviving = _real_graph_node_urns(ctx)

    assert _REAL_DIRECTIVE_CANONICAL_URN in surviving


def test_legacy_declared_directive_activation_survives_the_gate() -> None:
    """#4185 accepts exact declared directive IDs left by older promotion."""
    ctx = _pack_context(activated_directives=frozenset({"DIRECTIVE_001"}))

    surviving = _real_graph_node_urns(ctx)

    assert _REAL_DIRECTIVE_CANONICAL_URN in surviving


def test_non_activated_directive_is_still_excluded() -> None:
    """The gate still filters: a populated set that omits a node's canonical
    id excludes that node, both before and after the fix."""
    ctx = _pack_context(activated_directives=frozenset({_REAL_DIRECTIVE_STEM}))

    surviving = _real_graph_node_urns(ctx)

    assert _OTHER_REAL_DIRECTIVE_CANONICAL_URN not in surviving


# ---------------------------------------------------------------------------
# T005 -- root-source pinning (research.md D2 install-layout guard)
# ---------------------------------------------------------------------------


def test_root_divergence_follows_resolve_doctrine_root() -> None:
    """The gate must source ``doctrine_root`` from ``resolve_doctrine_root()``,
    never ``pack_context.pack_roots[0]`` -- a naive ``__file__`` join that can
    disagree with the projection root in installed/wheel layouts (D2).

    Constructs a ``PackContext`` whose ``pack_roots[0]`` is a directory that
    does NOT contain the real doctrine corpus. If the gate resolved stems
    against ``pack_roots[0]`` it could not find ``001-architectural-
    integrity-standard`` there and would (per the contract's
    skip-with-report rule) drop the node. The node must still survive,
    proving resolution followed ``resolve_doctrine_root()`` instead.
    """
    wrong_root = Path("/nonexistent/not-the-doctrine-root")
    assert wrong_root != resolve_doctrine_root()

    ctx = _pack_context(
        activated_directives=frozenset({_REAL_DIRECTIVE_STEM}),
        pack_roots=(wrong_root,),
    )

    surviving = _real_graph_node_urns(ctx)

    assert _REAL_DIRECTIVE_CANONICAL_URN in surviving


# ---------------------------------------------------------------------------
# T005 -- batched-once resolution (O(kinds), not O(nodes))
# ---------------------------------------------------------------------------


def test_resolution_is_batched_once_not_per_node(monkeypatch: pytest.MonkeyPatch) -> None:
    """``resolve_artifact_urn`` must be called a bounded number of times per
    filter call -- proportional to the number of activated stems across
    kinds, never to the number of graph nodes.

    A per-node implementation (resolving inside ``_node_is_activated``,
    called once per node at ``drg.py:351``) would make the call count scale
    with the graph's node count. Batching once in
    ``filter_graph_by_activation`` keeps it constant regardless of how many
    nodes of that kind exist in the graph.
    """
    call_count = 0
    real_resolve = drg_module.resolve_artifact_urn

    def _counting_resolve(*args: object, **kwargs: object) -> str:
        nonlocal call_count
        call_count += 1
        return real_resolve(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(drg_module, "resolve_artifact_urn", _counting_resolve)

    ctx = _pack_context(activated_directives=frozenset({_REAL_DIRECTIVE_STEM}))
    small_graph = load_built_in_graph()

    filter_graph_by_activation(small_graph, ctx)
    small_graph_call_count = call_count

    call_count = 0
    # Same activated stem, but a graph with many more directive-kind nodes
    # (the full built-in graph plus synthetic extra directive nodes bypassing
    # validation, mirroring the existing hermetic-node idiom in
    # ``tests/charter/test_activation_filtered_drg.py``).
    from charter.drg import DRGGraph, DRGNode, NodeKind

    extra_nodes = [DRGNode(urn=f"directive:SYNTHETIC_{i:04d}", kind=NodeKind.DIRECTIVE) for i in range(500)]
    large_graph = DRGGraph.model_construct(
        schema_version=small_graph.schema_version,
        generated_at=small_graph.generated_at,
        generated_by=small_graph.generated_by,
        nodes=[*small_graph.nodes, *extra_nodes],
        edges=small_graph.edges,
    )

    filter_graph_by_activation(large_graph, ctx)
    large_graph_call_count = call_count

    assert small_graph_call_count > 0
    assert large_graph_call_count == small_graph_call_count


# ---------------------------------------------------------------------------
# Direct coverage: defensive MissionTypeNotAnArtifactKind catch
# ---------------------------------------------------------------------------


def test_unresolvable_kind_token_yields_empty_resolution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``_resolve_activated_urns_for_kind`` catches
    ``MissionTypeNotAnArtifactKind`` defensively, mirroring the reference
    pattern at ``consistency_check.py:892-894``.

    This is unreachable through the gate's live call path: the fixed kind
    domain it iterates (``_SINGULAR_TO_PER_KIND_FIELD``) never keys on
    ``"mission-type"``. Exercised directly here (by monkeypatching
    ``ArtifactKind.from_operator_token`` to raise) so the branch has real
    coverage instead of being an untested defensive no-op.
    """

    def _raise_mission_type(_token: str) -> None:
        raise MissionTypeNotAnArtifactKind("synthetic for test")

    monkeypatch.setattr(drg_module.ArtifactKind, "from_operator_token", staticmethod(_raise_mission_type))

    result = drg_module._resolve_activated_urns_for_kind(
        "directive",
        frozenset({_REAL_DIRECTIVE_STEM}),
        doctrine_root=resolve_doctrine_root(),
        org_roots=[],
    )

    assert result == frozenset()


# ---------------------------------------------------------------------------
# Cross-layer-ambiguous directive id -- fail closed, not silently admitted
# (#4194 landing remediation: the layer-precedence fix in
# ``kind_vocabulary.resolve_config_id`` now rejects a stem two org packs
# disagree on; this pins that the gate observes the rejection as "no URN",
# never as a spuriously-admitted node).
# ---------------------------------------------------------------------------


def test_cross_layer_ambiguous_directive_id_resolves_to_no_urn(tmp_path: Path) -> None:
    """A persisted ``activated_directives`` entry naming a declared identity
    that is genuinely cross-layer-ambiguous -- two org packs both ship a
    ``shared.directive.yaml`` stem, disagreeing on which id it names -- must
    resolve to **no** canonical URN, never to ``f"directive:{token}"``
    admitted verbatim.

    Before the fix, ``resolve_config_id`` swallowed the collision (the stale
    reordering happened to return *some* stem without ever raising
    ``UnrepresentableDirectiveIdError``), so ``resolve_artifact_urn``'s
    declared-id fallback returned the unexamined token as a URN and this
    gate would have folded a URN naming no single, unambiguous artifact into
    the resolved set (fail **open**). After the fix, ``resolve_config_id``
    raises, the fallback's ``except ValueError`` re-raises
    ``UnknownArtifactIdError``, and this function's own
    ``except UnknownArtifactIdError: continue`` (skip-with-report) drops the
    token -- the resolved set for the whole kind is the empty frozenset
    (block-all for this kind), never a set containing a bogus entry.
    """
    company = tmp_path / "company"
    team = tmp_path / "team"
    (company / "directives").mkdir(parents=True)
    (team / "directives").mkdir(parents=True)
    (company / "directives" / "shared.directive.yaml").write_text(
        'schema_version: "1.0"\nid: OTHER-POLICY\ntitle: shared\nintent: Apply policy.\nenforcement: required\n'
    )
    (team / "directives" / "shared.directive.yaml").write_text(
        'schema_version: "1.0"\nid: CHOSEN-POLICY\ntitle: shared\nintent: Apply policy.\nenforcement: required\n'
    )

    resolved = drg_module._resolve_activated_urns_for_kind(
        "directive",
        frozenset({"CHOSEN-POLICY"}),
        doctrine_root=resolve_doctrine_root(),
        org_roots=[company, team],
    )

    assert resolved == frozenset()
