"""Step-contract activation identity end to end (#6741).

The defect: a built-in mission step contract is a node whose URN tail is the owning
``(mission, action)`` pair (``mission_step_contract:documentation/accept``), while every activation
surface used the contract's declared id (``documentation-accept``). Each surface minted
``"<kind>:<declared id>"`` locally, so the token resolved to a URN no node carries: the config<->graph
parity check reported a gap with a resynthesis remedy that could never help, and a deny entry written
as a declared id matched nothing.

These tests go through the pre-existing entry points (the activation filter, the parity check, the
deny resolution) against the real shipped graph.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from charter.activation.activation_ledger import resolve_deny
from charter.activation.consistency_check import _check_graph_kind_parity, _resolve_graph_kind_parity_stem
from charter.activation.drg_activation import filter_graph_by_activation
from charter.activation.identity_index import IdentityIndex
from charter.activation.invocation_context import ProjectContext
from charter.activation.pack_context import PackContext
from charter.offering.artifact_kinds import ArtifactKind
from charter.offering.drg.models import NodeKind

pytestmark = [pytest.mark.fast, pytest.mark.doctrine]

_REPO_ROOT = Path(__file__).resolve().parents[3]

#: A real built-in step contract: declared id ``documentation-accept``, shipped URN
#: ``mission_step_contract:documentation/accept``.
_STEP_TOKEN = "documentation-accept"
_STEP_URN = "mission_step_contract:documentation/accept"
_SIBLING_STEP_URN = "mission_step_contract:documentation/audit"

#: A real built-in step contract on the software-dev mission type, used for the deny case.
_DENIED_STEP_TOKEN = "implement"
_DENIED_STEP_URN = "mission_step_contract:software-dev/implement"
_UNTOUCHED_STEP_URN = "mission_step_contract:software-dev/plan"


@pytest.fixture(scope="module")
def identity() -> IdentityIndex:
    return IdentityIndex.build(_REPO_ROOT)


@pytest.fixture(scope="module")
def base_context() -> PackContext:
    return PackContext.from_config(_REPO_ROOT)


def _context(base: PackContext, **overrides: object) -> PackContext:
    return dataclasses.replace(base, **overrides)  # type: ignore[arg-type]


def _msc_urns(context: PackContext, identity: IdentityIndex) -> set[str]:
    from charter.activation._drg_helpers import load_validated_graph

    graph = filter_graph_by_activation(load_validated_graph(_REPO_ROOT), context, identity=identity)
    return {node.urn for node in graph.nodes if node.kind is NodeKind.MISSION_STEP_CONTRACT}


# --------------------------------------------------------------------------- #
# The parity check: an activated step contract is not a gap
# --------------------------------------------------------------------------- #


def test_an_activated_step_contract_reports_no_graph_gap(
    base_context: PackContext, identity: IdentityIndex
) -> None:
    """RED before #6741: the gap ``mission-step-contract/documentation-accept`` was reported."""
    ctx = ProjectContext(
        repo_root=_REPO_ROOT,
        pack_context=_context(base_context, activated_mission_step_contracts=frozenset({_STEP_TOKEN})),
    )
    gaps: list[str] = []
    errors: list[str] = []
    suggestions: list[str] = []

    _check_graph_kind_parity(
        ctx,
        {"mission-step-contract": [_STEP_TOKEN]},
        gaps,
        errors,
        suggestions,
        identity=identity,
    )

    assert gaps == []
    assert errors == []
    assert not any("resynthesize" in entry for entry in suggestions), suggestions


def test_a_filtered_out_step_contract_names_the_activation_keys_not_a_resynthesis(
    base_context: PackContext, identity: IdentityIndex
) -> None:
    """The node exists in the DRG but its owning mission type is inactive: say so (#6741 FR-006)."""
    ctx = ProjectContext(
        repo_root=_REPO_ROOT,
        pack_context=_context(
            base_context,
            activated_mission_types=frozenset({"software-dev"}),
            activated_mission_step_contracts=frozenset({_STEP_TOKEN}),
        ),
    )
    gaps: list[str] = []
    errors: list[str] = []
    suggestions: list[str] = []

    _check_graph_kind_parity(
        ctx,
        {"mission-step-contract": [_STEP_TOKEN]},
        gaps,
        errors,
        suggestions,
        identity=identity,
    )

    gap_suggestions = [entry for entry in suggestions if entry.startswith("mission-step-contract/")]
    assert gaps == ["mission-step-contract/documentation-accept"]
    assert len(gap_suggestions) == 1, suggestions
    assert "activated_mission_types" in gap_suggestions[0]
    assert "resynthesize" not in gap_suggestions[0]
    assert "will not change this" in gap_suggestions[0]


def test_an_artifact_absent_from_the_drg_keeps_the_regenerate_suggestion(
    identity: IdentityIndex,
) -> None:
    """The paired control for the new arm: an unresolvable node still sends the operator to regenerate."""
    gaps: list[str] = []
    suggestions: list[str] = []

    _resolve_graph_kind_parity_stem(
        "directive",
        ArtifactKind.DIRECTIVE,
        "001-architectural-integrity-standard",
        frozenset(),
        identity=identity,
        full_urns=frozenset(),
        graph_kind_gaps=gaps,
        suggestions=suggestions,
    )

    assert gaps == ["directive/001-architectural-integrity-standard"]
    assert len(suggestions) == 1
    assert "Regenerate graph.yaml" in suggestions[0]
    assert "resynthesize" in suggestions[0]


# --------------------------------------------------------------------------- #
# The filter: the activated contract survives, the shipped set is unchanged
# --------------------------------------------------------------------------- #


def test_the_activated_step_contract_survives_the_filter(
    base_context: PackContext, identity: IdentityIndex
) -> None:
    ctx = _context(base_context, activated_mission_step_contracts=frozenset({_STEP_TOKEN}))

    surviving = _msc_urns(ctx, identity)

    assert _STEP_URN in surviving
    assert f"mission_step_contract:{_STEP_TOKEN}" not in surviving


def test_the_mission_type_ownership_rule_still_precedes_the_per_id_gate(
    base_context: PackContext, identity: IdentityIndex
) -> None:
    """C-002: an explicit step-contract allow list cannot resurrect an inactive mission type's node."""
    ctx = _context(
        base_context,
        activated_mission_types=frozenset({"software-dev"}),
        activated_mission_step_contracts=frozenset({_STEP_TOKEN}),
    )

    surviving = _msc_urns(ctx, identity)

    assert _STEP_URN not in surviving
    assert "mission_step_contract:software-dev/implement" in surviving


def test_the_default_ledger_keeps_the_whole_shipped_step_contract_set(
    base_context: PackContext, identity: IdentityIndex
) -> None:
    """NFR-002: no `activated_mission_step_contracts` key -> the surviving set is unchanged (21 nodes)."""
    assert base_context.activated_mission_step_contracts is None

    surviving = _msc_urns(base_context, identity)

    assert len(surviving) == 21
    assert _STEP_URN in surviving


# --------------------------------------------------------------------------- #
# Deny: a declared id now matches the node it names
# --------------------------------------------------------------------------- #


def test_denying_a_step_contract_by_its_declared_id_drops_its_node(
    base_context: PackContext, identity: IdentityIndex
) -> None:
    """RED before #6741: ``DenySet.urns`` held ``mission_step_contract:implement``, matching no node."""
    deny = resolve_deny(ArtifactKind.MISSION_STEP_CONTRACT, [_DENIED_STEP_TOKEN], identity)
    assert deny.urns == frozenset({_DENIED_STEP_URN})

    ctx = _context(base_context, denied=(("mission_step_contracts", deny),))
    surviving = _msc_urns(ctx, identity)

    assert _DENIED_STEP_URN not in surviving
    assert _UNTOUCHED_STEP_URN in surviving       # same mission type, not denied
    assert _SIBLING_STEP_URN in surviving         # different mission type, not denied


def test_denying_by_the_mission_scoped_spelling_still_works(
    base_context: PackContext, identity: IdentityIndex
) -> None:
    """The #6741-era spelling keeps working: an unknown token carries itself into the deny set."""
    deny = resolve_deny(ArtifactKind.MISSION_STEP_CONTRACT, ["software-dev/implement"], identity)

    ctx = _context(base_context, denied=(("mission_step_contracts", deny),))
    surviving = _msc_urns(ctx, identity)

    assert _DENIED_STEP_URN not in surviving
    assert _UNTOUCHED_STEP_URN in surviving


# --------------------------------------------------------------------------- #
# Every other kind is untouched
# --------------------------------------------------------------------------- #


def test_every_activated_directive_resolves_exactly_as_the_old_construction_did(
    base_context: PackContext, identity: IdentityIndex
) -> None:
    """NFR-002 for ordinary kinds: ``"<kind>:<declared id>"``, byte for byte, for every activation."""
    activated = base_context.activated_directives
    assert activated, "this repository activates directives; an empty set would make this vacuous"

    for token in sorted(activated):
        declared = identity.declared_id(ArtifactKind.DIRECTIVE, token)
        assert declared is not None, token
        assert identity.urn(ArtifactKind.DIRECTIVE, token) == f"directive:{declared}"


def test_the_helper_reports_a_drifted_node_urn(identity: IdentityIndex) -> None:
    """Non-vacuity: the parity helper names the pre-fix spelling as a gap when the node set disagrees."""
    # A surviving set that spells the token the pre-#6741 way: the parity check must not treat the
    # declared-id spelling as the node, or it would go green again on a graph that carries no node.
    drifted = frozenset({"mission_step_contract:documentation-accept"})
    gaps: list[str] = []
    suggestions: list[str] = []

    _resolve_graph_kind_parity_stem(
        "mission-step-contract",
        ArtifactKind.MISSION_STEP_CONTRACT,
        _STEP_TOKEN,
        drifted,
        identity=identity,
        full_urns=drifted,
        graph_kind_gaps=gaps,
        suggestions=suggestions,
    )

    assert gaps == ["mission-step-contract/documentation-accept"]
