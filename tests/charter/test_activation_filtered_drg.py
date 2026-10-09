"""Activation-filtered DRG traversal tests (WP11, T070).

Covers:

- T070-1: ``filter_graph_by_activation`` keeps mission-step contracts whose
  owning mission type is in ``activated_mission_types`` and drops the rest.
- T070-2: ``filter_graph_by_activation`` drops non-activated mission types
  AND the steps they own.
- T070-3: FR-006 directive-scope semantics — non-activated artifact kinds
  (e.g. tactics) are filtered out when ``activated_kinds`` does not list
  them, even when the owning mission type is activated.
- T070-4: Direct doctrine-API access (``MissionTemplateRepository.get``)
  bypasses the activation filter and continues to return the underlying
  mission asset.
- T070-5: An empty ``activated_mission_types`` set produces an empty
  step-contract slice while leaving non-step artifacts subject only to
  the kind filter.
- T070-6: Activation filter preserves edges only when both endpoints
  survive; cross-cutting edges to filtered-out nodes are dropped.
- T070-7: The org-pack loader resolves the legacy
  ``mission_step_contracts`` plural to the canonical ``mission_steps``
  form (T066b backward-compat alias).

All tests are hermetic: ``PackContext`` instances are constructed
directly so the filter logic can be exercised without writing
``config.yaml`` to disk.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from charter.drg import (
    DRGEdge,
    DRGGraph,
    DRGNode,
    NodeKind,
    Relation,
)
from charter.activation.drg_activation import filter_graph_by_activation
from charter.activation.pack_context import PackContext
from charter.offering.drg.org_pack_loader import OrgDRGFragment

# ---------------------------------------------------------------------------
# About mission-step URNs in the DRG
# ---------------------------------------------------------------------------
# As of WP11 the doctrine ``NodeKind`` enum does not include a member for
# ``mission_step_contract``; mission steps are surfaced through the
# ``ActiveCharterService.mission_step_contracts`` repository (a non-DRG path) and
# the WP11 activation filter targets future DRG-resolved mission-step
# fragments. To exercise the filter today without changing ``NodeKind``
# (out of scope for WP11), tests below mint mission-step-like nodes
# directly by bypassing the ``DRGNode`` URN-prefix validator. The filter
# code itself only inspects URN strings, so this hermetic shape is faithful
# to its production behaviour.

pytestmark = [pytest.mark.unit]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_ALL_KINDS = frozenset(
    {
        "directives",
        "tactics",
        "styleguides",
        "toolguides",
        "paradigms",
        "procedures",
        "agent_profiles",
        "mission_steps",
    }
)


def _ctx(
    *,
    kinds: frozenset[str] = _ALL_KINDS,
    mission_types: frozenset[str] = frozenset({"software-dev", "documentation"}),
    repo_root: Path | None = None,
) -> PackContext:
    """Construct a hermetic PackContext for filter tests."""
    return PackContext(
        activated_kinds=kinds,
        activated_mission_types=mission_types,
        pack_roots=(),
        org_pack_names=(),
        repo_root=repo_root or Path("/nonexistent"),
    )


def _graph(nodes: list[DRGNode], edges: list[DRGEdge] | None = None) -> DRGGraph:
    # ``model_construct`` skips validators so that step-shaped URNs (whose
    # singular ``mission_step_contract`` kind is not yet in ``NodeKind``)
    # can be embedded in the graph. The activation filter operates purely
    # on URN strings so the surrogate ``kind`` does not affect outcomes.
    return DRGGraph.model_construct(
        schema_version="1.0",
        generated_at="2026-05-30T00:00:00Z",
        generated_by="test",
        nodes=nodes,
        edges=edges or [],
    )


def _step_node(mission_type: str, step_id: str) -> DRGNode:
    """Mint a mission-step URN using the WP11 owner-prefix convention.

    ``NodeKind`` does not yet enumerate ``mission_step_contract`` (see
    module docstring), so we bypass the URN-prefix validator by
    constructing the model via ``model_construct`` and tagging it with a
    surrogate kind. The activation filter only reads the URN string, so
    its filtering decision is unchanged by the surrogate kind.
    """
    return DRGNode.model_construct(
        urn=f"mission_step_contract:{mission_type}/{step_id}",
        kind=NodeKind.TEMPLATE,  # surrogate; not inspected by the filter
        label=f"{mission_type}/{step_id}",
    )


# ---------------------------------------------------------------------------
# T070-1 + T070-2: mission-step / mission-type activation filter
# ---------------------------------------------------------------------------


def test_activated_mission_type_steps_pass_filter() -> None:
    """A step whose owner mission type is activated survives the filter."""
    graph = _graph(
        [
            _step_node("software-dev", "implement"),
            _step_node("software-dev", "review"),
        ]
    )

    ctx = _ctx(mission_types=frozenset({"software-dev"}))
    filtered = filter_graph_by_activation(graph, ctx)

    surviving = {n.urn for n in filtered.nodes}
    assert surviving == {
        "mission_step_contract:software-dev/implement",
        "mission_step_contract:software-dev/review",
    }


def test_non_activated_mission_type_steps_are_dropped() -> None:
    """Steps whose owner mission type is not activated do not survive."""
    graph = _graph(
        [
            _step_node("software-dev", "implement"),
            _step_node("documentation", "audit"),
        ]
    )

    ctx = _ctx(mission_types=frozenset({"software-dev"}))
    filtered = filter_graph_by_activation(graph, ctx)

    surviving = {n.urn for n in filtered.nodes}
    assert surviving == {"mission_step_contract:software-dev/implement"}
    assert "mission_step_contract:documentation/audit" not in surviving


# ---------------------------------------------------------------------------
# T070-3: FR-006 directive-scope — kind filter applies
# ---------------------------------------------------------------------------


def test_fr006_mission_type_scoped_directive_dropped_when_kind_not_activated() -> None:
    """A tactic that is scoped to an activated mission type
    is still filtered out when the project charter does not activate
    ``tactics`` as a kind. This is the FR-006 binding: mission-type-scoped
    artifacts respect the per-kind activation set."""
    graph = _graph(
        [
            DRGNode(
                urn="directive:project-scoped-must-have",
                kind=NodeKind.DIRECTIVE,
                label="Always-on directive",
            ),
            DRGNode(
                urn="tactic:software-dev-only",
                kind=NodeKind.TACTIC,
                label="Mission-type-scoped tactic",
            ),
        ]
    )

    # activated_kinds excludes ``tactics`` — only directives are activated.
    ctx = _ctx(kinds=frozenset({"directives"}))
    filtered = filter_graph_by_activation(graph, ctx)

    surviving = {n.urn for n in filtered.nodes}
    assert "directive:project-scoped-must-have" in surviving
    assert "tactic:software-dev-only" not in surviving


# ---------------------------------------------------------------------------
# T070-4: Direct doctrine-API bypass (T069 invariant)
# ---------------------------------------------------------------------------


def test_doctrine_api_bypass_returns_non_activated_mission() -> None:
    """Direct ``MissionTemplateRepository.get_*`` calls must return mission
    assets even when the corresponding mission type is not activated in the
    project charter. T069 documents this invariant: the activation filter
    is a charter-mediated-resolution gate, not a hard removal."""
    from charter.offering.missions import MissionTemplateRepository

    repo = MissionTemplateRepository.default()

    # "documentation" is intentionally absent from any PackContext we build
    # in this test — the direct API call must still find it.
    config = repo.get_mission_config("documentation")
    assert config is not None
    assert config.origin.endswith("/mission.yaml")

    # And the mission-type listing surface continues to enumerate it.
    assert "documentation" in repo.list_missions()


# ---------------------------------------------------------------------------
# T070-5: empty activation set → empty mission-step slice
# ---------------------------------------------------------------------------


def test_empty_activated_mission_types_drops_all_steps() -> None:
    """Empty ``activated_mission_types`` removes every step contract while
    leaving non-step artifacts subject only to the kind filter."""
    graph = _graph(
        [
            _step_node("software-dev", "implement"),
            _step_node("documentation", "audit"),
            DRGNode(urn="directive:always-on", kind=NodeKind.DIRECTIVE),
        ]
    )

    ctx = _ctx(mission_types=frozenset())
    filtered = filter_graph_by_activation(graph, ctx)

    surviving = {n.urn for n in filtered.nodes}
    assert surviving == {"directive:always-on"}


# ---------------------------------------------------------------------------
# T070-6: edges are filtered consistently
# ---------------------------------------------------------------------------


def test_edges_to_filtered_nodes_are_dropped() -> None:
    """An edge whose endpoint is filtered out must not survive."""
    step_kept = _step_node("software-dev", "implement")
    step_dropped = _step_node("documentation", "audit")
    directive = DRGNode(urn="directive:foo", kind=NodeKind.DIRECTIVE)
    graph = _graph(
        [step_kept, step_dropped, directive],
        [
            DRGEdge(
                source=step_kept.urn,
                target="directive:foo",
                relation=Relation.REQUIRES,
            ),
            DRGEdge(
                source=step_dropped.urn,
                target="directive:foo",
                relation=Relation.REQUIRES,
            ),
        ],
    )

    ctx = _ctx(mission_types=frozenset({"software-dev"}))
    filtered = filter_graph_by_activation(graph, ctx)

    surviving_urns = {n.urn for n in filtered.nodes}
    assert step_dropped.urn not in surviving_urns

    # Only the edge whose source survives is preserved.
    surviving_edges = [(e.source, e.target) for e in filtered.edges]
    assert (step_kept.urn, "directive:foo") in surviving_edges
    assert (step_dropped.urn, "directive:foo") not in surviving_edges


# ---------------------------------------------------------------------------
# T070-7: T066b — legacy ``mission_step_contracts`` alias resolves
# ---------------------------------------------------------------------------


def test_org_pack_loader_resolves_legacy_mission_step_contracts_alias() -> None:
    """A pack authored against the pre-WP01 plural ``mission_step_contracts``
    must continue to validate, and the resulting node's ``kind`` must be
    normalised to the canonical ``mission_steps`` form (T066b)."""
    fragment = OrgDRGFragment.model_validate(
        {
            "pack_name": "legacy-pack",
            "source_kind": "local_path",
            "source_ref": "/nonexistent/legacy-pack",
            "layer_index": 1,
            "provenance_marker": "org",
            "nodes": [
                {
                    "id": "implement",
                    "kind": "mission_step_contracts",
                    "title": "Implement step",
                }
            ],
            "edges": [],
        }
    )

    assert {n.id for n in fragment.nodes} == {"implement"}
    # Canonical post-WP01 form is the singular ``mission_steps``.
    assert fragment.nodes[0].kind == "mission_steps"


def test_org_pack_loader_accepts_canonical_mission_steps() -> None:
    """The post-WP01 canonical plural ``mission_steps`` must validate
    natively and round-trip unchanged."""
    fragment = OrgDRGFragment.model_validate(
        {
            "pack_name": "modern-pack",
            "source_kind": "local_path",
            "source_ref": "/nonexistent/modern-pack",
            "layer_index": 1,
            "provenance_marker": "org",
            "nodes": [
                {
                    "id": "implement",
                    "kind": "mission_steps",
                    "title": "Implement step",
                }
            ],
            "edges": [],
        }
    )

    assert fragment.nodes[0].kind == "mission_steps"


# ---------------------------------------------------------------------------
# Defensive coverage: unknown URN kind survives the filter
# ---------------------------------------------------------------------------


def test_unknown_kind_passes_filter_by_default() -> None:
    """An extension kind not in :data:`_SINGULAR_TO_PLURAL` is allowed
    through by default — the DRG schema validator (not the activation
    filter) is the gatekeeper for kind legality."""
    graph = _graph(
        [
            DRGNode(urn="action:start", kind=NodeKind.ACTION),
            DRGNode(urn="glossary:term-x", kind=NodeKind.GLOSSARY),
        ]
    )

    ctx = _ctx(kinds=frozenset({"directives"}))  # no actions / glossary
    filtered = filter_graph_by_activation(graph, ctx)

    surviving_urns = {n.urn for n in filtered.nodes}
    # Both are unknown to the kind map → default-allow.
    assert "action:start" in surviving_urns
    assert "glossary:term-x" in surviving_urns
