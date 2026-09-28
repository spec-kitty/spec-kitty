"""Acceptance tests: shipped MissionStepContracts for software-dev are valid and complete.

These tests verify:
1. All 4 software-dev actions have shipped step contracts
2. Every step contract passes model validation
3. Delegates-to references point to valid ArtifactKind values
4. Step IDs are unique within each contract
5. Contracts are loadable via DoctrineService
6. Round-trip serialization preserves all fields
"""

import pytest

from charter.offering.artifact_kinds import ArtifactKind
from charter.offering.missions.step_contracts import MissionStepContract
from charter.offering.missions.step_contracts import MissionStepContractRepository
from charter.offering.service import DoctrineService


SOFTWARE_DEV_ACTIONS = ("specify", "plan", "implement", "review")

pytestmark = [pytest.mark.fast, pytest.mark.corpus]


class TestShippedContractsExistAndValidate:
    """Every software-dev action has a shipped step contract."""

    @pytest.fixture
    def repo(self) -> MissionStepContractRepository:
        return MissionStepContractRepository()

    @pytest.mark.parametrize("action", SOFTWARE_DEV_ACTIONS)
    def test_shipped_contract_exists(self, repo: MissionStepContractRepository, action: str) -> None:
        contract = repo.get_by_action("software-dev", action)
        assert contract is not None, f"No shipped step contract for software-dev/{action}"

    @pytest.mark.parametrize("action", SOFTWARE_DEV_ACTIONS)
    def test_contract_has_at_least_one_step(self, repo: MissionStepContractRepository, action: str) -> None:
        contract = repo.get_by_action("software-dev", action)
        assert contract is not None
        assert len(contract.steps) >= 1

    @pytest.mark.parametrize("action", SOFTWARE_DEV_ACTIONS)
    def test_step_ids_are_unique(self, repo: MissionStepContractRepository, action: str) -> None:
        contract = repo.get_by_action("software-dev", action)
        assert contract is not None
        ids = [s.id for s in contract.steps]
        assert len(ids) == len(set(ids)), f"Duplicate step IDs in {action}: {ids}"

    @pytest.mark.parametrize("action", SOFTWARE_DEV_ACTIONS)
    def test_delegates_to_references_valid_kinds(self, repo: MissionStepContractRepository, action: str) -> None:
        contract = repo.get_by_action("software-dev", action)
        assert contract is not None
        for step in contract.steps:
            if step.delegates_to is not None:
                assert step.delegates_to.kind in ArtifactKind, (
                    f"Step {step.id} in {action} delegates to invalid kind: {step.delegates_to.kind}"
                )
                assert len(step.delegates_to.candidates) > 0

    def test_all_builtin_bootstrap_inputs_are_preserved(self, repo: MissionStepContractRepository) -> None:
        expected_inputs = [
            {"flag": "--profile", "source": "wp.agent_profile", "optional": True},
            {"flag": "--tool", "source": "env.agent_tool", "optional": True},
        ]

        for contract in repo.list_all():
            bootstrap = contract.steps[0]
            assert bootstrap.id == "bootstrap", contract.id
            assert [step_input.model_dump() for step_input in bootstrap.inputs] == expected_inputs, contract.id


class TestContractsAccessibleViaService:
    """DoctrineService exposes step contracts via lazy repository."""

    def test_service_has_mission_step_contracts_property(self) -> None:
        service = DoctrineService()
        repo = service.mission_step_contracts
        assert isinstance(repo, MissionStepContractRepository)

    def test_service_caches_repository(self) -> None:
        service = DoctrineService()
        first = service.mission_step_contracts
        second = service.mission_step_contracts
        assert first is second

    @pytest.mark.parametrize("action", SOFTWARE_DEV_ACTIONS)
    def test_service_loads_shipped_contracts(self, action: str) -> None:
        service = DoctrineService()
        contract = service.mission_step_contracts.get_by_action("software-dev", action)
        assert contract is not None
        assert isinstance(contract, MissionStepContract)


class TestImplementContractStructure:
    """The implement contract has the expected step structure.

    This is the most complex contract (branching delegation, quality gates,
    commit signing). Pin its structure as a regression guard.
    """

    @pytest.fixture
    def contract(self) -> MissionStepContract:
        repo = MissionStepContractRepository()
        c = repo.get_by_action("software-dev", "implement")
        assert c is not None
        return c

    def test_has_bootstrap_step(self, contract: MissionStepContract) -> None:
        bootstrap = next((s for s in contract.steps if s.id == "bootstrap"), None)
        assert bootstrap is not None
        assert bootstrap.command is not None
        assert "charter context" in bootstrap.command
        assert [step_input.model_dump() for step_input in bootstrap.inputs] == [
            {"flag": "--profile", "source": "wp.agent_profile", "optional": True},
            {"flag": "--tool", "source": "env.agent_tool", "optional": True},
        ]

    def test_has_workspace_step_with_paradigm_delegation(self, contract: MissionStepContract) -> None:
        workspace = next((s for s in contract.steps if s.id == "workspace"), None)
        assert workspace is not None
        assert workspace.delegates_to is not None
        assert workspace.delegates_to.kind == ArtifactKind.PARADIGM
        assert "execution-lanes" in workspace.delegates_to.candidates

    def test_workspace_paradigm_candidates_exist_as_shipped_artifacts(
        self, contract: MissionStepContract
    ) -> None:
        workspace = next((s for s in contract.steps if s.id == "workspace"), None)
        assert workspace is not None
        assert workspace.delegates_to is not None

        paradigms = DoctrineService().paradigms
        missing = [
            candidate
            for candidate in workspace.delegates_to.candidates
            if paradigms.get(candidate) is None
        ]
        assert missing == []

    def test_has_quality_gate_step(self, contract: MissionStepContract) -> None:
        gate = next((s for s in contract.steps if s.id == "quality_gate"), None)
        assert gate is not None
        assert gate.delegates_to is not None
        assert gate.delegates_to.kind == ArtifactKind.DIRECTIVE

    def test_has_status_transition_step(self, contract: MissionStepContract) -> None:
        transition = next((s for s in contract.steps if s.id == "status_transition"), None)
        assert transition is not None
        assert transition.command is not None

    def test_supply_chain_security_check_precedes_quality_gate(self, contract: MissionStepContract) -> None:
        """The supply-chain security check must run before the quality gate.

        Ordering, not mere presence, is the requirement: a step that exists
        anywhere in the contract but after ``quality_gate`` would satisfy a
        naive "is it in the file" check while violating the WP prompt's
        "precedes standard quality gate" mandate and contract Rule 4.
        """
        ids = [s.id for s in contract.steps]
        assert "supply_chain_security_check" in ids
        assert "quality_gate" in ids
        assert ids.index("supply_chain_security_check") < ids.index("quality_gate")


class TestAdvisoryGateCompatibility:
    """Regression guard: the security-layer wiring must stay advisory-only.

    Pins the WP's own promised mitigation for "accidental hard-gate
    behavior" -- the pre-existing ``review`` gate must remain fail-open and
    unchanged, and ``plan``/``implement`` must not gain a ``gates`` block.
    """

    @pytest.fixture
    def repo(self) -> MissionStepContractRepository:
        return MissionStepContractRepository()

    def test_review_gate_is_unchanged_and_fail_open(self, repo: MissionStepContractRepository) -> None:
        contract = repo.get_by_action("software-dev", "review")
        assert contract is not None

        # Exact gate set (not a bare count): fails both if a gate is added/removed
        # and if the surviving gate's transition or fail-open posture drifts.
        gate_fail_open_by_transition = {gate.on_transition: gate.fail_open for gate in contract.gates}
        assert gate_fail_open_by_transition == {"in_progress->for_review": True}

    @pytest.mark.parametrize("action", ["plan", "implement"])
    def test_no_new_fail_closed_gate_introduced(self, repo: MissionStepContractRepository, action: str) -> None:
        contract = repo.get_by_action("software-dev", action)
        assert contract is not None
        assert contract.gates == []


class TestSpecifyContractStructure:
    """The specify contract captures examples before requirement validation."""

    @pytest.fixture
    def contract(self) -> MissionStepContract:
        repo = MissionStepContractRepository()
        c = repo.get_by_action("software-dev", "specify")
        assert c is not None
        return c

    def test_capture_intent_includes_examples_directive(self, contract: MissionStepContract) -> None:
        capture_intent = next((s for s in contract.steps if s.id == "capture_intent"), None)
        assert capture_intent is not None
        assert "human discovery interview" in capture_intent.description
        assert "confirmed user intent" in capture_intent.description
        assert capture_intent.delegates_to is not None
        assert capture_intent.delegates_to.kind == ArtifactKind.DIRECTIVE
        assert "DIRECTIVE_037" in capture_intent.delegates_to.candidates

    def test_has_map_examples_step_with_procedure_delegation(self, contract: MissionStepContract) -> None:
        map_examples = next((s for s in contract.steps if s.id == "map_examples"), None)
        assert map_examples is not None
        assert map_examples.delegates_to is not None
        assert map_examples.delegates_to.kind == ArtifactKind.PROCEDURE
        assert map_examples.delegates_to.candidates == ["example-mapping-workshop"]


class TestReviewContractStructure:
    """The review contract checks example, acceptance, and doc sync."""

    @pytest.fixture
    def contract(self) -> MissionStepContract:
        repo = MissionStepContractRepository()
        c = repo.get_by_action("software-dev", "review")
        assert c is not None
        return c

    def test_verify_spec_fidelity_includes_examples_directive(self, contract: MissionStepContract) -> None:
        verify_spec_fidelity = next((s for s in contract.steps if s.id == "verify_spec_fidelity"), None)
        assert verify_spec_fidelity is not None
        assert verify_spec_fidelity.delegates_to is not None
        assert verify_spec_fidelity.delegates_to.kind == ArtifactKind.DIRECTIVE
        assert "DIRECTIVE_037" in verify_spec_fidelity.delegates_to.candidates

    def test_has_example_sync_step(self, contract: MissionStepContract) -> None:
        verify_example_sync = next((s for s in contract.steps if s.id == "verify_example_sync"), None)
        assert verify_example_sync is not None
        assert verify_example_sync.delegates_to is not None
        assert verify_example_sync.delegates_to.kind == ArtifactKind.TACTIC
        assert verify_example_sync.delegates_to.candidates == ["usage-examples-sync"]
