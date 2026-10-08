"""Step-contract advisory-compatibility for the supply-chain security layer
(WP05, T017).

Mission ``supply-chain-security-checks-layer-01KZBFBS``. WP02 already pins
implement's step-ordering (``supply_chain_security_check`` precedes
``quality_gate``, see
``tests/charter_offering/mission_step_contracts/test_shipped_contracts.py``). This
module covers two distinct binding classes instead of duplicating that check:

1. **Delegation content** -- each of the three security stages
   (``plan``/``implement``'s ``supply_chain_security_check`` and ``review``'s
   ``supply_chain_security_review``) actually delegates to the
   ``supply-chain-install-safety`` tactic, not merely exists under a
   plausible-looking id.
2. **A repo-wide fail-closed-gate invariant** -- not scoped to software-dev --
   proving this mission did not introduce a new fail-closed gate anywhere in
   the shipped step-contract corpus (documentation and research mission types
   included), plus the explicit ``gates == []`` / ``fail_open: true``
   assertions the WP mandate calls out by name.
"""

from __future__ import annotations

import pytest

from charter.offering.artifact_kinds import ArtifactKind
from charter.offering.missions.step_contracts import MissionStepContract, MissionStepContractRepository

pytestmark = [pytest.mark.doctrine, pytest.mark.fast]

_SECURITY_STAGE_IDS = {
    "plan": "supply_chain_security_check",
    "implement": "supply_chain_security_check",
    "review": "supply_chain_security_review",
}
_EXPECTED_TACTIC_CANDIDATE = "supply-chain-install-safety"


@pytest.fixture(scope="module")
def repo() -> MissionStepContractRepository:
    return MissionStepContractRepository()


class TestSecurityStagesDelegateToSupplyChainTactic:
    """Each software-dev action's security stage delegates to the new tactic."""

    @pytest.mark.parametrize("action", ["plan", "implement", "review"])
    def test_security_stage_delegates_to_supply_chain_tactic(
        self, repo: MissionStepContractRepository, action: str
    ) -> None:
        contract = repo.get_by_action("software-dev", action)
        assert contract is not None, f"No shipped step contract for software-dev/{action}"

        stage_id = _SECURITY_STAGE_IDS[action]
        stage = next((s for s in contract.steps if s.id == stage_id), None)
        assert stage is not None, f"{action}: missing step '{stage_id}'"

        assert stage.delegates_to is not None, f"{action}/{stage_id}: no delegates_to"
        assert stage.delegates_to.kind == ArtifactKind.TACTIC, (
            f"{action}/{stage_id}: expected delegation kind TACTIC, "
            f"got {stage.delegates_to.kind}"
        )
        assert _EXPECTED_TACTIC_CANDIDATE in stage.delegates_to.candidates, (
            f"{action}/{stage_id}: expected candidate '{_EXPECTED_TACTIC_CANDIDATE}' "
            f"in {stage.delegates_to.candidates}"
        )


class TestNoFailClosedGateAnywhereInShippedContracts:
    """This mission must not have introduced a new fail-closed transition gate.

    Checked at two granularities: a repo-wide invariant across every shipped
    step contract (any mission type -- documentation/research included, not
    just software-dev), and the specific per-action assertions the WP mandate
    calls out explicitly (``gates == []`` for plan/implement, unchanged
    ``fail_open: true`` for review).
    """

    def test_every_shipped_gate_is_fail_open(self, repo: MissionStepContractRepository) -> None:
        contracts: list[MissionStepContract] = repo.list_all()
        assert len(contracts) > 0, "Expected at least one shipped step contract"

        fail_closed = [
            (contract.id, gate.on_transition)
            for contract in contracts
            for gate in contract.gates
            if not gate.fail_open
        ]
        assert fail_closed == [], (
            f"Fail-closed gate(s) found in shipped contracts: {fail_closed}. "
            "The supply-chain security layer must remain advisory-only in v1 "
            "-- no new hard gate."
        )

    @pytest.mark.parametrize("action", ["plan", "implement"])
    def test_software_dev_action_gained_no_gates(
        self, repo: MissionStepContractRepository, action: str
    ) -> None:
        contract = repo.get_by_action("software-dev", action)
        assert contract is not None
        assert contract.gates == [], (
            f"{action}: expected no gates block, got {contract.gates!r}"
        )

    def test_review_gate_is_unchanged_and_still_fail_open(
        self, repo: MissionStepContractRepository
    ) -> None:
        contract = repo.get_by_action("software-dev", "review")
        assert contract is not None

        # Exact gate set (not a bare count): fails both if a gate is added/removed
        # and if the surviving gate's transition or fail-open posture drifts.
        gate_fail_open_by_transition = {gate.on_transition: gate.fail_open for gate in contract.gates}
        assert gate_fail_open_by_transition == {"in_progress->for_review": True}, (
            f"Expected exactly one fail-open gate on in_progress->for_review, "
            f"got {contract.gates!r}"
        )
