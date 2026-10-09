"""The single-owner DRG wiring.

One owner states each rule and every other artifact references the owner by
id. Trimming copies can remove the only path that delivered an owner, so this
module pins the DRG edges that keep each owner delivered.

Non-default relations are curated ``_CURATED_ARTIFACT_EDGES`` entries in
``charter.offering.drg.migration.extractor`` (a procedure's YAML ``references``
to a tactic/procedure mints ``requires``; a tactic's mints ``suggests``;
``refines`` has no YAML path at all). The assertions read the SHIPPED graph
(``load_built_in_graph``), so a curated edge that never reached the committed
fragments fails here, not only in the extractor. Absence of the retired nodes
is guarded in ``test_retired_ids_absent.py``.
"""

from __future__ import annotations

import pytest

from charter.offering.drg.models import RELATION_DESCRIPTIONS, DRGGraph, Relation

pytestmark = [pytest.mark.doctrine, pytest.mark.fast]

_SQUAD = "procedure:adversarial-squad-deployment"
_TFBF = "procedure:test-first-bug-fixing"
_BDD_TACTIC = "tactic:bdd-scenario-formulation"
_GWT = "styleguide:given-when-then-authoring"
_SUPPLY_CHAIN_TACTIC = "tactic:supply-chain-install-safety"
_LINT_ASSET = "asset:common-docs-structural-lint"


def _relations(graph: DRGGraph, source: str, target: str) -> set[Relation]:
    return {e.relation for e in graph.edges if e.source == source and e.target == target}


def _has(graph: DRGGraph, source: str, target: str, relation: Relation) -> bool:
    return relation in _relations(graph, source, target)


# --------------------------------------------------------------------------- #
# Retired nodes are gone; successors are present.
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "urn",
    [
        _BDD_TACTIC,
        "styleguide:boring-code-review",
        "toolguide:javascript-supply-chain",
        "toolguide:python-supply-chain",
        "toolguide:java-supply-chain",
        "tactic:common-docs-scaffold",
        "tactic:common-docs-write",
        "tactic:common-docs-find",
    ],
)
def test_successor_node_is_present(built_in_graph: DRGGraph, urn: str) -> None:
    assert urn in built_in_graph.node_urns()


# --------------------------------------------------------------------------- #
# Squad procedure.
# --------------------------------------------------------------------------- #


def test_squad_procedure_suggests_model_task_routing(built_in_graph: DRGGraph) -> None:
    """Model-tier choice is delegated, advisory (never ``requires``)."""
    assert _relations(built_in_graph, _SQUAD, "tactic:model-task-routing") == {Relation.SUGGESTS}


def test_squad_procedure_does_not_require_five_paradigm(built_in_graph: DRGGraph) -> None:
    """The squad procedure does not hard-require the fixed-lens tactic (the tactic refines the procedure instead)."""
    assert not _has(built_in_graph, _SQUAD, "tactic:five-paradigm-parallel-debugging", Relation.REQUIRES)


@pytest.mark.parametrize(
    "source",
    ["directive:DIRECTIVE_043", "directive:DIRECTIVE_052", "procedure:mission-tracer-files"],
)
def test_citers_point_at_squad_procedure_with_suggests_only(built_in_graph: DRGGraph, source: str) -> None:
    """Every citer points at the owner with ``suggests`` only (no hard chain)."""
    assert _relations(built_in_graph, source, _SQUAD) == {Relation.SUGGESTS}


@pytest.mark.parametrize(
    "source",
    ["tactic:five-paradigm-parallel-debugging", "tactic:paula-patterns-architecture-scout-review"],
)
def test_fixed_lens_tactics_refine_the_squad_procedure(built_in_graph: DRGGraph, source: str) -> None:
    """``refines`` only -- no duplicate ``suggests`` for the pair."""
    assert _relations(built_in_graph, source, _SQUAD) == {Relation.REFINES}


_ZERO_EDGE_RELATIONS = sorted((r for r in Relation if "zero edges" in RELATION_DESCRIPTIONS[r]), key=lambda r: r.value)


@pytest.mark.parametrize("relation", _ZERO_EDGE_RELATIONS, ids=lambda r: r.value)
def test_relation_described_as_edgeless_has_no_built_in_edges(built_in_graph: DRGGraph, relation: Relation) -> None:
    """A relation whose description claims "zero edges" in the built-in graph must really have none."""
    edges = [(e.source, e.target) for e in built_in_graph.edges if e.relation is relation]
    assert edges == [], f"{relation.value}: description claims zero built-in edges but the shipped graph has {edges[:3]}"


# --------------------------------------------------------------------------- #
# Testing / bug-fixing / BDD.
# --------------------------------------------------------------------------- #


def test_testing_principles_requires_quadruple_a(built_in_graph: DRGGraph) -> None:
    """The inline Quad-A copy was trimmed, so delivery needs a hard edge."""
    assert _has(
        built_in_graph,
        "styleguide:testing-principles",
        "styleguide:quadruple-a-test-format",
        Relation.REQUIRES,
    )


@pytest.mark.parametrize(
    ("target", "relation"),
    [
        ("directive:DIRECTIVE_034", Relation.REQUIRES),
        ("directive:DIRECTIVE_025", Relation.REQUIRES),
        ("procedure:red-main-release-discipline", Relation.REQUIRES),
        ("directive:DIRECTIVE_052", Relation.SUGGESTS),
        ("procedure:disciplined-defect-diagnosis", Relation.SUGGESTS),
    ],
)
def test_test_first_bug_fixing_points_at_its_owners(built_in_graph: DRGGraph, target: str, relation: Relation) -> None:
    """052 and the diagnosis hand-off are advisory (``suggests``) pointers."""
    assert _has(built_in_graph, _TFBF, target, relation)


def test_test_first_bug_fixing_never_requires_052_or_diagnosis(built_in_graph: DRGGraph) -> None:
    """052 is advisory; diagnosis already requires this procedure (no requires cycle)."""
    assert not _has(built_in_graph, _TFBF, "directive:DIRECTIVE_052", Relation.REQUIRES)
    assert not _has(built_in_graph, _TFBF, "procedure:disciplined-defect-diagnosis", Relation.REQUIRES)


@pytest.mark.parametrize("source", [_BDD_TACTIC, "procedure:bdd-scenario-lifecycle"])
def test_bdd_practices_require_given_when_then(built_in_graph: DRGGraph, source: str) -> None:
    """Scenarios are authored per the given-when-then styleguide."""
    assert _has(built_in_graph, source, _GWT, Relation.REQUIRES)
    assert _has(built_in_graph, source, "toolguide:gherkin", Relation.SUGGESTS)


@pytest.mark.parametrize(
    ("target", "relation"),
    [
        (_BDD_TACTIC, Relation.REQUIRES),
        ("procedure:bdd-scenario-lifecycle", Relation.REQUIRES),
        (_GWT, Relation.SUGGESTS),
        ("toolguide:gherkin", Relation.SUGGESTS),
    ],
)
def test_bdd_paradigm_reaches_its_practices(built_in_graph: DRGGraph, target: str, relation: Relation) -> None:
    """The paradigm has edges to its practices (a paradigm's YAML
    reference mints ``requires`` to a tactic/procedure, ``suggests`` otherwise)."""
    assert _has(built_in_graph, "paradigm:behaviour-driven-development", target, relation)


# --------------------------------------------------------------------------- #
# Common docs, change scope, review, supply chain.
# --------------------------------------------------------------------------- #


def test_structural_lint_is_required_by_the_write_tactic(built_in_graph: DRGGraph) -> None:
    """The curation tactic's "run the rulers" step moved to common-docs-write."""
    assert _has(built_in_graph, "tactic:common-docs-write", _LINT_ASSET, Relation.REQUIRES)


@pytest.mark.parametrize("directive", ["DIRECTIVE_024", "DIRECTIVE_001"])
def test_avoid_gold_plating_inherits_locality_directive_edges(built_in_graph: DRGGraph, directive: str) -> None:
    """The successor carries the retired locality-of-change tactic's directive
    edges with the SAME relation they had at base (a tactic's YAML reference
    mints ``suggests``), so the fold neither drops nor escalates them."""
    assert _relations(built_in_graph, "tactic:avoid-gold-plating", f"directive:{directive}") == {Relation.SUGGESTS}


@pytest.mark.parametrize("action", ["implement", "review"])
def test_boring_code_review_is_scoped_as_a_styleguide(built_in_graph: DRGGraph, action: str) -> None:
    assert _has(
        built_in_graph,
        f"action:software-dev/{action}",
        "styleguide:boring-code-review",
        Relation.SCOPE,
    )


def test_directive_039_points_at_the_boring_code_review_styleguide(built_in_graph: DRGGraph) -> None:
    assert _relations(built_in_graph, "directive:DIRECTIVE_039", "styleguide:boring-code-review")


@pytest.mark.parametrize(
    "toolguide",
    ["toolguide:javascript-supply-chain", "toolguide:python-supply-chain", "toolguide:java-supply-chain"],
)
def test_supply_chain_tactic_suggests_each_ecosystem_toolguide(built_in_graph: DRGGraph, toolguide: str) -> None:
    """The neutral tactic points at the per-ecosystem commands."""
    assert _has(built_in_graph, _SUPPLY_CHAIN_TACTIC, toolguide, Relation.SUGGESTS)


@pytest.mark.parametrize("profile", ["python-pedro", "java-jenny", "architect-alphonso"])
def test_profiles_reach_the_supply_chain_tactic(built_in_graph: DRGGraph, profile: str) -> None:
    """The profiles that bind supply-chain doctrine cite the tactic by id."""
    assert _has(built_in_graph, f"agent_profile:{profile}", _SUPPLY_CHAIN_TACTIC, Relation.REQUIRES)


def test_directive_001_suggests_the_architecture_scout_swarm(built_in_graph: DRGGraph) -> None:
    """An escalation, not a prerequisite -- applied because the measured
    action (d=1, d=2) and profile reachability sets lost no member."""
    assert _relations(
        built_in_graph,
        "directive:DIRECTIVE_001",
        "tactic:paula-patterns-architecture-scout-review",
    ) == {Relation.SUGGESTS}


def test_decision_documentation_is_not_delivered_to_implement_via_avoid_gold_plating(built_in_graph: DRGGraph) -> None:
    """The retired locality tactic's DIRECTIVE_003 edge is NOT carried over:
    avoid-gold-plating is reached from implement (boring-code-review ->
    avoid-gold-plating), so the edge would deliver the required
    decision-documentation directive to implement (decision-documentation scoping gate)."""
    assert not _relations(built_in_graph, "tactic:avoid-gold-plating", "directive:DIRECTIVE_003")
