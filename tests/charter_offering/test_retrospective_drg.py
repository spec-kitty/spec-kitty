"""DRG resolver tests for the retrospective-facilitator profile and retrospect action.

Covers FR-001 through FR-004:
- FR-001: profile:retrospective-facilitator exists and resolves through DRG.
- FR-002: action:retrospect exists and resolves through DRG.
- FR-003: resolved scope surfaces the required FR-003 minimum URN kinds.
- FR-004: (contract) the resolver is deterministic (same inputs -> same scope set).

It exercises the resolve_context function from charter.offering.drg.query against the
shipped graph, which is served read-only from the session-scoped
``shipped_drg_graph`` fixture in ``tests/charter_offering/conftest.py`` (WP03/T012) so
the shipped graph is built once per session rather than once per module.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from charter.offering.agent_profiles.repository import AgentProfileRepository
from charter.offering.drg.models import DRGGraph, NodeKind
from charter.offering.drg.query import resolve_context

pytestmark = [pytest.mark.fast, pytest.mark.doctrine, pytest.mark.corpus]

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

BUILT_IN_DIR = Path(__file__).resolve().parents[2] / "packs" / "built-in" / "agent_profiles"

# All three built-in missions that own a retrospect action (FR-002)
_RETROSPECT_ACTION_URNS = [
    "action:software-dev/retrospect",
    "action:research/retrospect",
    "action:documentation/retrospect",
]

# FR-003 minimum URN set: the resolved scope MUST contain at least one node
# from each of these categories (expressed as URN prefixes / exact URNs).
#
# - charter/doctrine artifacts: directives (DIRECTIVE_003, DIRECTIVE_010)
# - DRG slice: doctrine versioning directive (DIRECTIVE_018)
# - glossary artifacts: glossary-curation-interview or kitty-glossary-writing
# - mission event-stream / metadata context: requirements-validation-workflow
# - mission output context: stopping-conditions
# - autonomous operation context: autonomous-operation-protocol
# - profile: retrospective-facilitator

_REQUIRED_URNS = frozenset({
    "directive:DIRECTIVE_003",
    "directive:DIRECTIVE_010",
    "directive:DIRECTIVE_018",
    "tactic:requirements-validation-workflow",
    "tactic:stopping-conditions",
    "tactic:autonomous-operation-protocol",
    "tactic:glossary-curation-interview",
    "styleguide:kitty-glossary-writing",
    "agent_profile:retrospective-facilitator",
})


@pytest.fixture
def shipped_graph(shipped_drg_graph: DRGGraph) -> DRGGraph:
    """Read-only shipped DRG, served from the session cache (WP03/T012).

    Previously this module loaded + merged + validated ``graph.yaml`` itself
    once per module. It now consumes the session-scoped ``shipped_drg_graph``
    fixture (``tests/charter_offering/conftest.py``) so the shipped graph is built once
    per test session and shared read-only across modules.
    """
    return shipped_drg_graph


# ---------------------------------------------------------------------------
# FR-001 — profile:retrospective-facilitator exists in the DRG
# ---------------------------------------------------------------------------


def test_retrospective_facilitator_profile_node_exists(shipped_graph: DRGGraph) -> None:
    """FR-001: The shipped graph contains a node for retrospective-facilitator."""
    node = shipped_graph.get_node("agent_profile:retrospective-facilitator")
    assert node is not None, (
        "agent_profile:retrospective-facilitator must be present in graph.yaml"
    )
    assert node.kind == NodeKind.AGENT_PROFILE


# ---------------------------------------------------------------------------
# FR-002 — action:retrospect exists for each built-in mission
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("action_urn", _RETROSPECT_ACTION_URNS)
def test_retrospect_action_node_exists(shipped_graph: DRGGraph, action_urn: str) -> None:
    """FR-002: Each built-in mission has a retrospect action node in the DRG."""
    node = shipped_graph.get_node(action_urn)
    assert node is not None, (
        f"{action_urn} must be present in graph.yaml (FR-002)"
    )
    assert node.kind == NodeKind.ACTION


# ---------------------------------------------------------------------------
# FR-003 — resolved scope surfaces the required URN set
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("action_urn", _RETROSPECT_ACTION_URNS)
def test_resolve_context_non_empty_scope(shipped_graph: DRGGraph, action_urn: str) -> None:
    """FR-003 (partial): Resolving retrospect produces a non-empty scope."""
    ctx = resolve_context(shipped_graph, action_urn, depth=2)
    assert len(ctx.artifact_urns) > 0, (
        f"resolve_context({action_urn!r}) must return a non-empty scope"
    )


@pytest.mark.parametrize("action_urn", _RETROSPECT_ACTION_URNS)
def test_resolve_context_contains_required_urns(shipped_graph: DRGGraph, action_urn: str) -> None:
    """FR-003: Resolved scope contains all required URN kinds for retrospect context.

    Checks that the scope surfaces:
    - charter/doctrine artifacts (DIRECTIVE_003, DIRECTIVE_010)
    - DRG slice artifact (DIRECTIVE_018 - doctrine versioning)
    - glossary artifacts (glossary-curation-interview, kitty-glossary-writing)
    - mission event-stream / metadata context (requirements-validation-workflow)
    - mission output context (stopping-conditions)
    - autonomous operation context (autonomous-operation-protocol)
    - profile (retrospective-facilitator)
    """
    ctx = resolve_context(shipped_graph, action_urn, depth=2)
    missing = _REQUIRED_URNS - ctx.artifact_urns
    assert not missing, (
        f"resolve_context({action_urn!r}) is missing required FR-003 URNs: "
        f"{sorted(missing)}"
    )


@pytest.mark.parametrize("action_urn", _RETROSPECT_ACTION_URNS)
def test_resolve_context_contains_directive_urns(shipped_graph: DRGGraph, action_urn: str) -> None:
    """FR-003: Resolved scope contains directive URNs (charter/doctrine artifacts)."""
    ctx = resolve_context(shipped_graph, action_urn, depth=2)
    directive_urns = {u for u in ctx.artifact_urns if u.startswith("directive:")}
    assert directive_urns, (
        f"resolve_context({action_urn!r}) must contain at least one directive URN"
    )


@pytest.mark.parametrize("action_urn", _RETROSPECT_ACTION_URNS)
def test_resolve_context_contains_tactic_urns(shipped_graph: DRGGraph, action_urn: str) -> None:
    """FR-003: Resolved scope contains tactic URNs (doctrine artifacts)."""
    ctx = resolve_context(shipped_graph, action_urn, depth=2)
    tactic_urns = {u for u in ctx.artifact_urns if u.startswith("tactic:")}
    assert tactic_urns, (
        f"resolve_context({action_urn!r}) must contain at least one tactic URN"
    )


@pytest.mark.parametrize("action_urn", _RETROSPECT_ACTION_URNS)
def test_resolve_context_contains_glossary_urns(shipped_graph: DRGGraph, action_urn: str) -> None:
    """FR-003: Resolved scope contains glossary-related URNs."""
    ctx = resolve_context(shipped_graph, action_urn, depth=2)
    glossary_urns = {
        u for u in ctx.artifact_urns
        if "glossary" in u
    }
    assert glossary_urns, (
        f"resolve_context({action_urn!r}) must contain at least one glossary URN"
    )


@pytest.mark.parametrize("action_urn", _RETROSPECT_ACTION_URNS)
def test_resolve_context_contains_profile_urn(shipped_graph: DRGGraph, action_urn: str) -> None:
    """FR-003: Resolved scope contains the retrospective-facilitator profile URN."""
    ctx = resolve_context(shipped_graph, action_urn, depth=2)
    assert "agent_profile:retrospective-facilitator" in ctx.artifact_urns, (
        f"resolve_context({action_urn!r}) must contain "
        "'agent_profile:retrospective-facilitator'"
    )


# ---------------------------------------------------------------------------
# FR-004 — resolution is deterministic
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("action_urn", _RETROSPECT_ACTION_URNS)
def test_resolve_context_is_deterministic(shipped_graph: DRGGraph, action_urn: str) -> None:
    """FR-004: Same inputs always produce the same resolved scope set."""
    first = resolve_context(shipped_graph, action_urn, depth=2)
    second = resolve_context(shipped_graph, action_urn, depth=2)
    assert first.artifact_urns == second.artifact_urns, (
        f"resolve_context({action_urn!r}) is not deterministic: "
        f"first={sorted(first.artifact_urns)}, second={sorted(second.artifact_urns)}"
    )
    assert first.glossary_scopes == second.glossary_scopes, (
        f"resolve_context({action_urn!r}) glossary scopes are not deterministic"
    )


def test_resolve_context_all_missions_identical_scope(shipped_graph: DRGGraph) -> None:
    """All three built-in mission retrospect actions resolve to identical scope sets.

    The three actions (software-dev, research, documentation) share identical
    governance scope because built-in missions have no mission-specific
    retrospective scope differences.
    """
    scopes = [
        resolve_context(shipped_graph, urn, depth=2).artifact_urns
        for urn in _RETROSPECT_ACTION_URNS
    ]
    assert scopes[0] == scopes[1] == scopes[2], (
        "All three built-in retrospect actions must resolve to the same scope set. "
        f"software-dev: {sorted(scopes[0])}, "
        f"research: {sorted(scopes[1])}, "
        f"documentation: {sorted(scopes[2])}"
    )


# ---------------------------------------------------------------------------
# FR-001 runtime — profile resolves through AgentProfileRepository
# ---------------------------------------------------------------------------


def test_retrospective_facilitator_resolves_through_profile_repository() -> None:
    """FR-001 (runtime): retrospective-facilitator loads via AgentProfileRepository.

    Proves the profile is reachable through the runtime's normal profile-lookup
    path (AgentProfileRepository.get()), not just as a DRG node.  This is the
    path exercised by ProfileRegistry.resolve() at invocation time.
    """
    repo = AgentProfileRepository(built_in_dir=BUILT_IN_DIR)
    profile = repo.get("retrospective-facilitator")
    assert profile is not None, (
        "AgentProfileRepository.get('retrospective-facilitator') must return a profile. "
        "Ensure the file is named retrospective-facilitator.agent.yaml (not .yaml)."
    )
    assert profile.profile_id == "retrospective-facilitator"
