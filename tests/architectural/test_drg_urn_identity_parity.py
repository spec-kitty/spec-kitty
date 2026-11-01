"""Every built-in DRG node's URN tail must be the identity the offering declares (#6741).

This is the structural guard for the defect class behind spec-kitty/spec-kitty#6741: the shipped
mission-step-contract nodes carried a mission-scoped tail (``mission_step_contract:documentation/
accept``) while every activation surface resolved the contract's declared id
(``documentation-accept``) to ``mission_step_contract:documentation-accept`` -- a URN no node
carries. The activation filter, the config<->graph parity check and the deny sets all silently
disagreed with the graph until the identity authority was taught the one step-contract rule.

The invariant, in two directions:

1. **No orphan node** -- every charter-activatable node in the shipped graph resolves to a declared
   artifact through :meth:`charter.activation.identity_index.IdentityIndex.urn`, and the URN the
   authority names is the node's own.
2. **No missing node** -- every shipped step contract has a node (a contract added upstream whose
   fragment lags fails here).

Only the **built-in** graph is read (``load_built_in_graph()``), never this repository's org overlay,
so the gate is deterministic and independent of local configuration. The non-vacuity arm plants a
divergence and asserts the same checker reports it -- a gate that cannot fail is not a gate.
"""

from __future__ import annotations

from collections.abc import Iterable

import pytest

from charter.activation.identity_index import IdentityIndex
from charter.offering.artifact_kinds import CHARTER_ACTIVATABLE_KINDS, ArtifactKind
from charter.offering.drg.loader import load_built_in_graph
from charter.offering.drg.models import DRGNode, NodeKind
from charter.offering.missions.step_contracts import MissionStepContractRepository, step_contract_urn

pytestmark = [pytest.mark.architectural, pytest.mark.doctrine]

#: Kinds exempt from tail resolution: ``anti_pattern`` is a tagged node inside another kind's
#: fragment, never a standalone file, so no identity entry (and no declared id) exists for it --
#: the same exclusion `charter.activation.drg_activation._NO_STEM_RESOLUTION_KINDS` makes.
_NO_STANDALONE_FILE_KINDS = frozenset({ArtifactKind.ANTI_PATTERN.value})

#: Node kinds that are a charter-activatable ``ArtifactKind`` with a declared identity to resolve.
_ACTIVATABLE_URNABLE_KINDS = frozenset(kind.value for kind in CHARTER_ACTIVATABLE_KINDS) - _NO_STANDALONE_FILE_KINDS

#: Kinds this repository must keep shipping nodes for; a silently empty scan would otherwise pass.
_KINDS_EXPECTED_IN_THE_GRAPH = frozenset(
    {
        ArtifactKind.DIRECTIVE.value,
        ArtifactKind.TACTIC.value,
        ArtifactKind.STYLEGUIDE.value,
        ArtifactKind.TOOLGUIDE.value,
        ArtifactKind.PARADIGM.value,
        ArtifactKind.PROCEDURE.value,
        ArtifactKind.AGENT_PROFILE.value,
        ArtifactKind.MISSION_STEP_CONTRACT.value,
    }
)


def _checked_nodes(nodes: Iterable[DRGNode]) -> list[DRGNode]:
    """The nodes this invariant applies to: charter-activatable kinds, and nothing else."""
    return [node for node in nodes if node.urn.partition(":")[0] in _ACTIVATABLE_URNABLE_KINDS]


def _step_contract_urns() -> frozenset[str]:
    """The node URNs the shipped contracts declare, through the one step-contract rule."""
    return frozenset(step_contract_urn(contract.mission, contract.action) for contract in MissionStepContractRepository().list_all())


def _drifted_urns(
    nodes: Iterable[DRGNode],
    identity: IdentityIndex,
    *,
    expected_step_contract_urns: frozenset[str] | None = None,
) -> list[str]:
    """Node URNs whose node identity is not the one the declared identity resolves to.

    Two arms, one per identity rule:

    * a ``mission_step_contract`` node must be one of the URNs the shipped contracts declare
      (:func:`charter.offering.missions.step_contracts.step_contract_urn`), because its tail is the
      owning ``(mission, action)`` pair rather than a declared id;
    * every other activatable node's tail must be its declared id, as the authority resolves it.

    Both catch the same defect class: a node minted from a field other than the declared identity
    (the #6741 case), and a declared id renamed without regenerating the fragment.
    """
    step_urns = _step_contract_urns() if expected_step_contract_urns is None else expected_step_contract_urns
    drifted: list[str] = []
    for node in nodes:
        kind_value, _sep, tail = node.urn.partition(":")
        kind = ArtifactKind(kind_value)
        if kind is ArtifactKind.MISSION_STEP_CONTRACT:
            if node.urn not in step_urns:
                drifted.append(node.urn)
            continue
        if identity.urn(kind, tail) != node.urn:
            drifted.append(node.urn)
    return sorted(drifted)


@pytest.fixture(scope="module")
def built_in_graph():  # noqa: ANN201 - DRGGraph, imported lazily by the loader
    return load_built_in_graph()


@pytest.fixture(scope="module")
def built_in_identity() -> IdentityIndex:
    """An index over the built-in layer only -- no org roots, no project layer."""
    from charter.offering.pack_paths import built_in_root  # noqa: PLC0415

    return IdentityIndex(org_roots=[], project_root=None, offering_root=built_in_root())


def test_no_built_in_node_urn_drifts_from_the_identity_authority(built_in_graph, built_in_identity: IdentityIndex) -> None:
    """The corpus arm: before #6741 all 21 step-contract nodes were reported here.

    On the pre-fix tree this module cannot even import (``step_contract_urn`` did not exist), so the
    21-node evidence is produced by the planted-divergence arm below, which feeds this same checker
    exactly those spellings.
    """
    checked = _checked_nodes(built_in_graph.nodes)

    assert _drifted_urns(checked, built_in_identity) == []


def test_the_gate_actually_checked_every_kind_it_claims_to_guard(built_in_graph) -> None:
    """Anti-empty-scan: a scan that saw nothing must not pass."""
    seen = {node.urn.partition(":")[0] for node in _checked_nodes(built_in_graph.nodes)}

    assert seen >= _KINDS_EXPECTED_IN_THE_GRAPH


def test_the_shipped_step_contract_nodes_are_exactly_the_shipped_contracts(built_in_graph, built_in_identity: IdentityIndex) -> None:
    """Both directions for step contracts: no extra node, no contract without a node."""
    from_contracts = _step_contract_urns()
    from_graph = {node.urn for node in built_in_graph.nodes if node.kind is NodeKind.MISSION_STEP_CONTRACT}

    assert from_graph == from_contracts
    assert len(from_contracts) == 21


def test_the_gate_bites_on_a_planted_divergence(built_in_identity: IdentityIndex) -> None:
    """Non-vacuity: the pre-fix spelling must be reported by the same checker the corpus uses."""
    planted = [
        DRGNode(urn="mission_step_contract:documentation-accept", kind=NodeKind.MISSION_STEP_CONTRACT),
        DRGNode(urn="mission_step_contract:documentation/accept", kind=NodeKind.MISSION_STEP_CONTRACT),
    ]

    expected = frozenset({"mission_step_contract:documentation/accept"})

    assert _drifted_urns(planted, built_in_identity, expected_step_contract_urns=expected) == ["mission_step_contract:documentation-accept"]


def test_the_gate_bites_on_a_planted_divergence_for_an_ordinary_kind(built_in_identity: IdentityIndex) -> None:
    """The general arm, not just the step-contract special case: a wrong directive tail is reported."""
    planted = [DRGNode(urn="directive:001-architectural-integrity-standard", kind=NodeKind.DIRECTIVE)]

    assert _drifted_urns(planted, built_in_identity) == ["directive:001-architectural-integrity-standard"]
