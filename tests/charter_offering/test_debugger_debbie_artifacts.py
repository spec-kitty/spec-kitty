"""Smoke tests for the Debugger Debbie doctrine artifacts."""

from __future__ import annotations

import pytest

from charter.offering.drg.models import DRGGraph
from charter.offering.service import CharterOfferingService

pytestmark = [pytest.mark.fast, pytest.mark.doctrine, pytest.mark.corpus]


@pytest.fixture(scope="module")
def service() -> CharterOfferingService:
    # No explicit built-in root: each repository self-resolves the flattened
    # built-in tier via resolve_pack_root("built-in") (packs/built-in/<kind>). Post-
    # relocation, pointing at src/doctrine would load an emptied tree.
    return CharterOfferingService()


def test_debugger_debbie_profile_loads(service: CharterOfferingService) -> None:
    profile = service.agent_profiles.get("debugger-debbie")

    assert profile is not None
    assert profile.profile_id == "debugger-debbie"
    assert profile.name == "Debugger Debbie"
    assert "investigator" in [str(role) for role in profile.roles]
    assert profile.specialization.primary_focus
    assert any(ref.id == "five-paradigm-parallel-debugging" for ref in profile.tactic_references)


def test_five_paradigm_tactic_loads(service: CharterOfferingService) -> None:
    tactic = service.tactics.get("five-paradigm-parallel-debugging")

    assert tactic is not None
    assert tactic.schema_version == "1.0"
    assert tactic.name == "Five-Paradigm Parallel Debugging"
    assert len(tactic.steps) == 6
    assert any(ref.id == "DIRECTIVE_040" for ref in tactic.references)


def test_directive_040_loads(service: CharterOfferingService) -> None:
    directive = service.directives.get("DIRECTIVE_040")

    assert directive is not None
    assert directive.schema_version == "1.0"
    assert directive.title == "Recurring-Bug Structural-Intervention Discipline"
    assert str(getattr(directive.enforcement, "value", directive.enforcement)) == "required"
    assert any("five-paradigm" in procedure for procedure in directive.procedures)


def test_debugger_debbie_graph_nodes_and_edges_exist(built_in_graph: DRGGraph) -> None:
    graph = built_in_graph
    nodes = graph.node_urns()

    assert "directive:DIRECTIVE_040" in nodes
    assert "tactic:five-paradigm-parallel-debugging" in nodes
    assert "agent_profile:debugger-debbie" in nodes

    edges = {(edge.source, edge.target, str(edge.relation)) for edge in graph.edges}
    assert (
        "directive:DIRECTIVE_040",
        "tactic:five-paradigm-parallel-debugging",
        "requires",
    ) in edges
    assert (
        "agent_profile:debugger-debbie",
        "tactic:five-paradigm-parallel-debugging",
        "requires",
    ) in edges
