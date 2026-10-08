"""WP06 (mission #2680) — silent-degrade guard for the sharding migration.

Merged-graph equality alone is *not* sufficient. Three consumers swallow
:class:`DRGLoadError` and fall back to an empty / degraded graph rather than
crashing (paula-patterns' finding). If the sharded layout failed to load, those
consumers would silently lose data while every "the merged graph is equal" test
stayed green — because they would each be reading an *empty* graph, not the
sharded one. This file asserts the three consumers produce **identical, healthy
outputs** against the sharded layout, matching the pre-shard reference:

* T031 — ``agent_profiles.repository`` resolves the same ``specializes_from``
  lineage parents (empty graph → lost lineage).
* T032 — ``charter_runtime.lint._drg`` reports a healthy ``GraphState`` (empty →
  ``GraphState.MISSING``); ``charter.offering.pack_validator`` sees the full built-in URN
  universe, so org-pack dangling-edge detection still resolves built-in targets
  (empty → false-pass / false-dangling).

The reference for T031 is again the in-memory ``generate_graph`` return value
(not a self-compare), injected into a second repository via its ``drg=`` seam.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from ruamel.yaml import YAML

from charter.offering.agent_profiles.repository import AgentProfileRepository
from charter.offering.drg.loader import built_in_graph_source, load_built_in_graph
from charter.offering.drg.migration.hand_authored_overlay import (
    generate_reference_graph_with_overlay,
)
from charter.offering.drg.models import DRGGraph, NodeKind, Relation
from specify_cli.charter_runtime.lint._drg import load_merged_drg
from specify_cli.charter_runtime.lint.findings import GraphState
from charter.offering.packs.pack_validator import validate_pack

pytestmark = [pytest.mark.unit, pytest.mark.fast, pytest.mark.corpus]


@pytest.fixture(scope="module")
def reference_graph() -> DRGGraph:
    """In-memory ``generate_graph`` return value + the hand-authored overlay
    (the non-vacuous reference).

    Post-WP03 (doctrine-tension-edges-01KY1WPC): merges in the enumerable
    hand-authored ``in_tension_with``/``reconciles_tension``/``rejects``
    edges and ``anti_pattern`` nodes (``charter.offering.drg.migration.
    hand_authored_overlay``) that the extractor cannot mint from frontmatter
    (C-005), so ``test_pack_validator_builtin_urn_set_is_full`` compares the
    shipped built-in URN universe against its true full reference rather than
    a subset that would spuriously look "extra" on the shipped side.
    """
    doctrine_root = built_in_graph_source()
    return generate_reference_graph_with_overlay(doctrine_root)


def _lineage_children(graph: DRGGraph) -> list[str]:
    """Profile ids that declare a ``specializes_from`` parent, sorted.

    Derived from the reference graph so the proof exercises whatever lineage the
    shipped doctrine actually authors (currently the four implementer
    specialists → ``implementer-ivan``) without hardcoding the roster.
    """
    from charter.offering.agent_profiles.repository import _profile_id_from_urn

    children = {
        _profile_id_from_urn(e.source)
        for e in graph.edges
        if e.relation == Relation.SPECIALIZES_FROM
    }
    return sorted(children)


# ---------------------------------------------------------------------------
# T031 — profile lineage is not silently degraded (FR-013 / DD-10)
# ---------------------------------------------------------------------------


def test_profile_lineage_parents_identical_and_non_empty(
    reference_graph: DRGGraph,
) -> None:
    """``get_ancestors`` returns the same, non-empty chain on both layouts.

    ``repository.py`` catches ``DRGLoadError`` and degrades to an empty DRG (no
    parents). Injecting the in-memory reference vs. loading the sharded layout
    from disk and getting *identical, non-empty* ancestor chains proves the
    sharded read did not degrade lineage resolution to empty.
    """
    ref_repo = AgentProfileRepository(drg=reference_graph)
    # drg=None → repository loads the sharded on-disk graph via load_built_in_graph.
    sharded_repo = AgentProfileRepository()

    children = _lineage_children(reference_graph)
    assert children, "expected shipped doctrine to author specializes_from lineage"

    for profile_id in children:
        ref_ancestors = ref_repo.get_ancestors(profile_id)
        sharded_ancestors = sharded_repo.get_ancestors(profile_id)
        assert ref_ancestors, f"{profile_id}: reference lineage unexpectedly empty"
        assert sharded_ancestors == ref_ancestors, (
            f"{profile_id}: lineage degraded under sharded layout — "
            f"reference={ref_ancestors} sharded={sharded_ancestors}"
        )


def test_resolve_profile_succeeds_against_sharded_layout(
    reference_graph: DRGGraph,
) -> None:
    """``resolve_profile`` on a lineage child resolves identically on both.

    Guards the merge path (not just the raw edge read): a degraded DRG would
    resolve the child without its parent's merged fields.
    """
    child = _lineage_children(reference_graph)[0]
    ref_repo = AgentProfileRepository(drg=reference_graph)
    sharded_repo = AgentProfileRepository()

    ref_profile = ref_repo.resolve_profile(child)
    sharded_profile = sharded_repo.resolve_profile(child)

    assert sharded_profile.profile_id == ref_profile.profile_id
    # The parent contributes the lineage chain; both must agree it is present.
    assert sharded_repo.get_ancestors(child) == ref_repo.get_ancestors(child)


# ---------------------------------------------------------------------------
# T032 — charter-lint + pack-validator see the built-in universe (FR-013)
# ---------------------------------------------------------------------------


def test_charter_lint_graph_state_is_healthy_not_missing() -> None:
    """``load_merged_drg`` resolves the sharded built-in as a healthy state.

    With no project DRG under ``.kittify/doctrine/``, ``load_merged_drg`` falls
    to the built-in seam. A failed sharded load would return
    ``(None, GraphState.MISSING)``; a healthy one returns a populated graph
    tagged ``GraphState.BUILT_IN_ONLY``.
    """
    with tempfile.TemporaryDirectory() as tmp:
        graph, state = load_merged_drg(Path(tmp))

    assert state is not GraphState.MISSING, (
        "charter-lint reported MISSING against the sharded built-in layout — "
        "the DRGLoadError-swallowing built-in read degraded silently"
    )
    assert state is GraphState.BUILT_IN_ONLY
    assert graph is not None
    assert graph.nodes, "charter-lint loaded an empty built-in graph"


def test_pack_validator_builtin_urn_set_is_full(
    reference_graph: DRGGraph,
) -> None:
    """The pack-validator's built-in URN set equals the reference (non-empty).

    ``pack_validator._validate_drg`` computes ``{n.urn for n in
    load_built_in_graph().nodes}`` and swallows ``DRGLoadError`` into an *empty*
    set (a validator false-pass). This asserts that exact expression yields the
    full reference URN universe.
    """
    built_in_urns = {n.urn for n in load_built_in_graph().nodes}
    assert built_in_urns, "pack-validator would see an empty built-in URN set"
    assert built_in_urns == reference_graph.node_urns()


def test_pack_validator_resolves_builtin_edge_targets(
    reference_graph: DRGGraph,
) -> None:
    """Behavioural proof: a pack edge to a built-in URN is not flagged dangling.

    Builds a minimal pack whose DRG fragment carries an edge to a real built-in
    directive URN and runs the real ``validate_pack``. If the built-in universe
    had degraded to empty, that target would be reported as a dangling edge
    (``drg_dangling_edge``). No such error ⇒ the validator still sees the
    built-in universe end-to-end.
    """
    built_in_target = min(
        n.urn for n in reference_graph.nodes if n.kind == NodeKind.DIRECTIVE
    )

    fragment = {
        "schema_version": "1.0",
        "generated_at": "STATIC",
        "generated_by": "wp06-silent-degrade-probe",
        "nodes": [{"urn": "tactic:wp06-silent-degrade-probe", "kind": "tactic"}],
        "edges": [
            {
                "source": "tactic:wp06-silent-degrade-probe",
                "target": built_in_target,
                "relation": "suggests",
            }
        ],
    }

    with tempfile.TemporaryDirectory() as tmp:
        drg_dir = Path(tmp) / "drg"
        drg_dir.mkdir()
        yaml = YAML()
        with (drg_dir / "probe.graph.yaml").open("w", encoding="utf-8") as fh:
            yaml.dump(fragment, fh)

        result = validate_pack(Path(tmp))

    dangling = [
        issue
        for issue in result.errors
        if getattr(issue, "category", "") == "drg_dangling_edge"
    ]
    assert not dangling, (
        "pack-validator flagged a built-in edge target as dangling — the "
        f"built-in URN universe degraded to empty: {[d.message for d in dangling]}"
    )
