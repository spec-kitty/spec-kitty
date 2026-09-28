"""Smoke tests for the Paula Patterns doctrine artifacts."""

from __future__ import annotations

import pytest

from charter.offering.drg.models import DRGGraph
from charter.offering.service import DoctrineService

pytestmark = [pytest.mark.fast, pytest.mark.doctrine, pytest.mark.corpus]


@pytest.fixture(scope="module")
def service() -> DoctrineService:
    # No explicit built-in root: repositories self-resolve packs/built-in/<kind>
    # (WP04 seam); src/doctrine is emptied post-relocation.
    return DoctrineService()


def test_paula_patterns_tactic_loads(service: DoctrineService) -> None:
    tactic = service.tactics.get("paula-patterns-architecture-scout-review")

    assert tactic is not None
    assert tactic.schema_version == "1.0"
    assert tactic.name == "Paula Patterns Architecture Scout Review"
    assert len(tactic.steps) == 6
    assert any(ref.id == "DIRECTIVE_001" for ref in tactic.references)
    assert "InstalledCliRuntime" in (tactic.notes or "")


def test_paula_patterns_profile_loads(service: DoctrineService) -> None:
    profile = service.agent_profiles.get("paula-patterns")

    assert profile is not None
    assert profile.profile_id == "paula-patterns"
    assert profile.name == "Paula Patterns"
    assert [str(role) for role in profile.roles] == [
        "architecture-scout",
        "architect",
        "reviewer",
    ]
    assert profile.specialization.primary_focus
    assert any(
        ref.id == "paula-patterns-architecture-scout-review"
        for ref in profile.tactic_references
    )


def test_paula_patterns_graph_node_and_edges_exist(built_in_graph: DRGGraph) -> None:
    graph = built_in_graph
    nodes = graph.node_urns()

    assert "agent_profile:paula-patterns" in nodes
    assert "tactic:paula-patterns-architecture-scout-review" in nodes

    edges = {(edge.source, edge.target, str(edge.relation)) for edge in graph.edges}
    assert (
        "agent_profile:paula-patterns",
        "tactic:paula-patterns-architecture-scout-review",
        "requires",
    ) in edges
    # FR-014 (mission squad-doctrine-single-owner-01M3KBP7): the directive now
    # SUGGESTS the scout swarm (an escalation, not a prerequisite); measured
    # with no action- or profile-channel reachability loss.
    assert (
        "directive:DIRECTIVE_001",
        "tactic:paula-patterns-architecture-scout-review",
        "suggests",
    ) in edges
    assert (
        "directive:DIRECTIVE_001",
        "tactic:paula-patterns-architecture-scout-review",
        "requires",
    ) not in edges
    assert (
        "tactic:paula-patterns-architecture-scout-review",
        "directive:DIRECTIVE_001",
        "suggests",
    ) in edges
    assert (
        "tactic:paula-patterns-architecture-scout-review",
        "tactic:review-intent-and-risk-first",
        "suggests",
    ) in edges
