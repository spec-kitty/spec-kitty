"""DRG node and resolve_context regression tests for documentation mission (#502).

These tests assert facts on the *real* shipped DRG and the documentation
action bundles produced by WP03:

1. Each of the 6 documentation action nodes exists in the validated graph and
   ``resolve_context()`` returns a non-empty ``artifact_urns`` set (FR-004,
   FR-005).
2. Each documentation action's bundle ``index.yaml`` (slug-form
   directives/tactics) maps 1-to-1 to the URN-form ``relation: scope`` edges
   in ``src/charter/offering/graph.yaml`` (FR-006).

The mission spec forbids mocking ``charter.activation._drg_helpers.load_validated_graph``
or ``charter.offering.drg.query.resolve_context`` (C-007); these tests read the real
on-disk graph and call the production resolver directly.

(#4015, operator-signed-off 2026-09-09: the former NFR-007 pure-timing test
``test_resolve_context_within_research_2x`` -- sole assert
``doc_med <= 2 * research_med``, vocab-blocked, zero functional coverage --
was deleted rather than split/helper-wrapped; see mission
``ci-suite-stability-test-isolation-01M22MM5`` WP06.)
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from charter.activation._drg_helpers import load_validated_graph
from charter.offering.drg.loader import load_built_in_graph
from charter.offering.drg.query import resolve_context

# The 6 advancing documentation actions covered by the mission-runtime sidecar.

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_DOC_ACTIONS: tuple[str, ...] = (
    "discover",
    "audit",
    "design",
    "generate",
    "validate",
    "publish",
)

# The 5 advancing research actions (used as the latency baseline in NFR-007).
_RESEARCH_ACTIONS: tuple[str, ...] = (
    "scoping",
    "methodology",
    "gathering",
    "synthesis",
    "output",
)

# Mirror the literal default of StepContractExecutionContext.resolution_depth
# (src/specify_cli/mission_step_contracts/executor.py); composition calls
# `resolve_context(graph, action_urn, depth=context.resolution_depth)`.
_COMPOSITION_RESOLUTION_DEPTH: int = 2

# Slug-form (action bundle index.yaml) -> URN-form (graph.yaml edge target).
# Per contracts/drg-shape.md "Contract: action bundle <-> DRG consistency".
_SLUG_TO_URN: dict[str, str] = {
    "001-architectural-integrity-standard": "directive:DIRECTIVE_001",
    "003-decision-documentation-requirement": "directive:DIRECTIVE_003",
    "010-specification-fidelity-requirement": "directive:DIRECTIVE_010",
    "037-living-documentation-sync": "directive:DIRECTIVE_037",
    "042-common-docs": "directive:DIRECTIVE_042",
    "requirements-validation-workflow": "tactic:requirements-validation-workflow",
    "premortem-risk-identification": "tactic:premortem-risk-identification",
    "adr-drafting-workflow": "tactic:adr-drafting-workflow",
    # WP06 homed the audience/review-flow tactics into the documentation action
    # indices (discover -> stakeholder-alignment; validate/accept ->
    # documentation-curation-audit). Both are shipped graph.yaml nodes.
    "stakeholder-alignment": "tactic:stakeholder-alignment",
    "documentation-curation-audit": "tactic:documentation-curation-audit",
    # Type-grain (governance-profile.yaml selected_directives/selected_tactics)
    # entries, needed by ``_type_grain_urns`` -- these never appear in an
    # action bundle's own index.yaml (FR-013 forbids the duplication), only
    # in the type-grain exclusion set used by test_action_bundle_matches_drg_edges.
    "common-docs-find": "tactic:common-docs-find",
    "common-docs-scaffold": "tactic:common-docs-scaffold",
    "common-docs-write": "tactic:common-docs-write",
    "usage-examples-sync": "tactic:usage-examples-sync",
}


def _type_grain_urns(repo_root: Path) -> set[str]:
    """Type-grain (``governance-profile.yaml``) directive/tactic URNs.

    FR-013 forbids duplicating a type-grain artifact into an action's own
    bundle (``index.yaml``), but the DRG may still carry a direct
    action -> type-grain-artifact ``scope`` edge as a deliberate "reaching"
    edge (see ``hand_authored_overlay.py``'s
    ``documentation/generate -> DIRECTIVE_042`` edge, WP09/FR-015:
    DIRECTIVE_042 is type-wide and therefore governs every action, but only
    ``generate`` needed a direct scope edge to make the otherwise
    action-unreachable common-docs cluster reachable at all). Such edges are
    legitimate type-grain inheritance, not action-grain bundle content, so
    ``test_action_bundle_matches_drg_edges`` excludes them from the strict
    bundle<->graph equality check below rather than requiring every action's
    bundle to redundantly re-declare the whole type grain.
    """
    # Mission doctrine-consumer-surface-missions-extraction-01KZ6G6H (FR-005)
    # relocated missions/ from src/charter/offering/missions to packs/built-in/missions.
    profile_path = (
        repo_root
        / "packs"
        / "built-in"
        / "missions"
        / "documentation"
        / "governance-profile.yaml"
    )
    profile = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
    slugs: list[str] = list(profile.get("selected_directives", []) or []) + list(
        profile.get("selected_tactics", []) or []
    )
    return {_SLUG_TO_URN[slug] for slug in slugs}


def _repo_root() -> Path:
    """Locate the repository root via a delete-stable ``pyproject.toml`` marker.

    Keyed on ``pyproject.toml`` rather than ``src/charter/offering/graph.yaml`` so the
    finder survives the WP05 monolith->fragment migration: the shipped
    ``graph.yaml`` is deleted, but ``pyproject.toml`` is not.
    """
    here = Path(__file__).resolve()
    for parent in (here, *here.parents):
        if (parent / "pyproject.toml").is_file():
            return parent
    raise RuntimeError("Could not locate repo root containing pyproject.toml")


@pytest.mark.parametrize("action", _DOC_ACTIONS)
def test_each_documentation_action_has_drg_node_and_context(action: str) -> None:
    """FR-004 + FR-005: DRG node exists and resolve_context returns artifact_urns."""
    repo_root = _repo_root()
    graph = load_validated_graph(repo_root)
    urn = f"action:documentation/{action}"
    node = graph.get_node(urn)
    assert node is not None, f"missing DRG node: {urn}"

    ctx = resolve_context(graph, urn, depth=_COMPOSITION_RESOLUTION_DEPTH)
    assert ctx.artifact_urns, (
        f"empty artifact_urns for {urn}; verify graph.yaml edges "
        f"from this action node to directives/tactics."
    )


@pytest.mark.parametrize("action", _DOC_ACTIONS)
def test_action_bundle_matches_drg_edges(action: str) -> None:
    """FR-006: action-bundle index.yaml directives/tactics match graph.yaml URN edges.

    Type-grain-aware (landing fold, PR #3070): a type-wide directive/tactic
    (declared in ``governance-profile.yaml``) may reach a specific action via
    a direct hand-authored ``scope`` edge (e.g.
    ``documentation/generate -> DIRECTIVE_042``, WP09/FR-015) without being
    duplicated into that action's own bundle -- FR-013 forbids the
    duplication. Such edges are excluded from the equality check via
    ``_type_grain_urns`` so the assertion still enforces exact parity for
    genuine action-grain content while tolerating legitimate type-grain
    inheritance.
    """
    repo_root = _repo_root()
    bundle_path = (
        repo_root
        / "packs"
        / "built-in"
        / "missions"
        / "documentation"
        / "actions"
        / action
        / "index.yaml"
    )
    bundle = yaml.safe_load(bundle_path.read_text(encoding="utf-8"))
    slugs: list[str] = list(bundle.get("directives", []) or []) + list(
        bundle.get("tactics", []) or []
    )
    expected_urns = {_SLUG_TO_URN[slug] for slug in slugs}

    # FR-006 edge check reads the built-in DRG through the WP03 seam so it stays
    # layout-agnostic across the WP05 monolith->fragment migration.
    graph = load_built_in_graph()
    actual_urns = {
        edge.target
        for edge in graph.edges
        if edge.source == f"action:documentation/{action}"
        and str(edge.relation) == "scope"
    }

    type_grain_urns = _type_grain_urns(repo_root)
    inherited_urns = actual_urns & type_grain_urns
    actual_action_grain_urns = actual_urns - inherited_urns

    assert expected_urns == actual_action_grain_urns, (
        f"bundle <-> DRG mismatch for {action}: bundle has {expected_urns}, "
        f"graph (excl. type-grain-inherited {inherited_urns}) has "
        f"{actual_action_grain_urns}"
    )
