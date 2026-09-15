"""Tests for the gate-binding schema on `MissionStepContract` (WP05).

Mission ``doctrine-controlled-transition-gates-01KY51Z7`` (epic #2535, half A).
Locks:

- ``GateBinding`` schema validation (defaults, ``extra="forbid"`` rejection,
  required ``schema_version``, invalid ``handler_kind`` rejection) -- FR-005.
- The ``handler_kind="asset"`` inert round-trip (validated, byte-stable,
  never executed) -- FR-005, C-002, NFR-004.
- The authored ``for_review`` binding on ``review.step-contract.yaml`` --
  FR-005, matching the WP04 ``GATE_REGISTRY`` key exactly.
- ``MissionStepContract.save()`` byte-stability: a previously-clean contract
  never gains a spurious ``gates: []`` on re-save -- NFR-004.
- Back-compat: every built-in contract still loads with ``gates`` absent
  (defaulting to ``[]``) -- FR-006.

Authored red-first per the mission's ATDD discipline: before T020-T023,
``GateBinding`` did not exist and ``MissionStepContract`` had no ``gates``
field, so every test in this module failed on import/collection.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from charter.offering.missions.step_contracts import (
    GateBinding,
    MissionStepContract,
    MissionStepContractRepository,
)

pytestmark = pytest.mark.fast


_VALID_BINDING: dict[str, object] = {
    "on_transition": "in_progress->for_review",
    "handler": "spec-kitty-pre-review",
    "schema_version": "1.0",
}


@pytest.fixture
def minimal_step_contract_data() -> dict[str, object]:
    """Minimal valid step contract with one step, no ``gates`` declared."""
    return {
        "schema_version": "1.0",
        "id": "test-implement",
        "action": "implement",
        "mission": "software-dev",
        "steps": [
            {"id": "bootstrap", "description": "Load charter context"},
        ],
    }


# ---------------------------------------------------------------------------
# GateBinding schema validation (T021, T024 #1/#2)
# ---------------------------------------------------------------------------


class TestGateBindingSchema:
    def test_minimal_binding_applies_defaults(self) -> None:
        binding = GateBinding.model_validate(_VALID_BINDING)
        assert binding.on_transition == "in_progress->for_review"
        assert binding.handler == "spec-kitty-pre-review"
        assert binding.handler_kind == "mission_step_contract"
        assert binding.schema_version == "1.0"
        assert binding.fail_open is True
        assert binding.provenance is None

    def test_frozen(self) -> None:
        binding = GateBinding.model_validate(_VALID_BINDING)
        with pytest.raises(ValidationError):
            binding.handler = "other"

    def test_unknown_key_rejected(self) -> None:
        with pytest.raises(ValidationError):
            GateBinding.model_validate({**_VALID_BINDING, "retries": 3})

    def test_missing_schema_version_rejected(self) -> None:
        payload = dict(_VALID_BINDING)
        del payload["schema_version"]
        with pytest.raises(ValidationError):
            GateBinding.model_validate(payload)

    def test_invalid_handler_kind_rejected(self) -> None:
        with pytest.raises(ValidationError):
            GateBinding.model_validate({**_VALID_BINDING, "handler_kind": "webhook"})

    def test_missing_on_transition_rejected(self) -> None:
        payload = dict(_VALID_BINDING)
        del payload["on_transition"]
        with pytest.raises(ValidationError):
            GateBinding.model_validate(payload)

    def test_missing_handler_rejected(self) -> None:
        payload = dict(_VALID_BINDING)
        del payload["handler"]
        with pytest.raises(ValidationError):
            GateBinding.model_validate(payload)


class TestAssetHandlerKindInertRoundTrip:
    """T024 #3 -- `handler_kind: "asset"` is accepted, byte-stable, never run."""

    def test_asset_binding_validates_and_round_trips_byte_stable(self) -> None:
        payload = {
            **_VALID_BINDING,
            "handler": "third-party-scanner",
            "handler_kind": "asset",
            "provenance": "org:acme-security-pack",
        }
        binding = GateBinding.model_validate(payload)
        assert binding.handler_kind == "asset"
        assert binding.provenance == "org:acme-security-pack"

        dumped = binding.model_dump(mode="json")
        reloaded = GateBinding.model_validate(dumped)
        assert reloaded.model_dump(mode="json") == dumped

    def test_asset_binding_is_inert_data_only(self) -> None:
        """No executor exists in half A: the model is inert data, never dispatched."""
        binding = GateBinding.model_validate(
            {**_VALID_BINDING, "handler_kind": "asset"}
        )
        # The model exposes no callable/execution surface -- it is a pure
        # data record. There is no `run`/`execute`/`__call__` to invoke.
        assert not hasattr(binding, "run")
        assert not hasattr(binding, "execute")
        assert not callable(binding)


# ---------------------------------------------------------------------------
# MissionStepContract.gates (T020)
# ---------------------------------------------------------------------------


class TestMissionStepContractGates:
    def test_gates_defaults_to_empty_list(self, minimal_step_contract_data: dict[str, object]) -> None:
        contract = MissionStepContract.model_validate(minimal_step_contract_data)
        assert contract.gates == []

    def test_gates_field_accepts_bindings(self, minimal_step_contract_data: dict[str, object]) -> None:
        data = {**minimal_step_contract_data, "gates": [_VALID_BINDING]}
        contract = MissionStepContract.model_validate(data)
        assert len(contract.gates) == 1
        assert contract.gates[0].handler == "spec-kitty-pre-review"

    def test_contract_still_rejects_unknown_top_level_keys(
        self, minimal_step_contract_data: dict[str, object]
    ) -> None:
        data = {**minimal_step_contract_data, "unexpected_field": True}
        with pytest.raises(ValidationError):
            MissionStepContract.model_validate(data)

    def test_contract_still_frozen(self, minimal_step_contract_data: dict[str, object]) -> None:
        contract = MissionStepContract.model_validate(minimal_step_contract_data)
        with pytest.raises(ValidationError):
            contract.gates = [GateBinding.model_validate(_VALID_BINDING)]


# ---------------------------------------------------------------------------
# The authored `for_review` binding (T023, T024 #5)
# ---------------------------------------------------------------------------


class TestReviewContractGateBinding:
    def test_for_review_binding_present_and_matches_registry_key(self) -> None:
        repo = MissionStepContractRepository()
        contract = repo.get_by_action("software-dev", "review")
        assert contract is not None

        assert len(contract.gates) == 1
        binding = contract.gates[0]
        assert binding.on_transition == "in_progress->for_review"
        assert binding.handler == "spec-kitty-pre-review"
        assert binding.handler_kind == "mission_step_contract"
        assert binding.fail_open is True


# ---------------------------------------------------------------------------
# save() byte-stability (T022, T024 #4)
# ---------------------------------------------------------------------------


class TestSaveByteStability:
    def test_clean_contract_re_saves_without_gates_key(
        self, tmp_path: Path, minimal_step_contract_data: dict[str, object]
    ) -> None:
        project_dir = tmp_path / "project"
        repo = MissionStepContractRepository(
            built_in_dir=tmp_path / "empty", project_dir=project_dir
        )
        contract = MissionStepContract.model_validate(minimal_step_contract_data)

        path = repo.save(contract)
        golden = path.read_bytes()
        assert b"gates:" not in golden, "empty `gates` must not appear on save"

        # Re-saving an independently-loaded, equally-clean contract must
        # reproduce byte-identical output (NFR-004).
        reloaded = MissionStepContract.model_validate(minimal_step_contract_data)
        path_again = repo.save(reloaded)
        assert path_again.read_bytes() == golden

    def test_non_default_gates_survive_save(
        self, tmp_path: Path, minimal_step_contract_data: dict[str, object]
    ) -> None:
        """A contract that DOES declare gates keeps them on save."""
        project_dir = tmp_path / "project"
        repo = MissionStepContractRepository(
            built_in_dir=tmp_path / "empty", project_dir=project_dir
        )
        data = {**minimal_step_contract_data, "gates": [_VALID_BINDING]}
        contract = MissionStepContract.model_validate(data)

        path = repo.save(contract)
        assert b"gates:" in path.read_bytes()

    def test_all_built_in_contracts_except_review_re_save_without_gates(
        self, tmp_path: Path
    ) -> None:
        """Byte-golden across every shipped built-in contract (T024/T025).

        ``review.step-contract.yaml`` legitimately declares one binding; every
        other built-in must never gain a spurious ``gates: []`` on re-save.
        """
        project_dir = tmp_path / "project"
        repo = MissionStepContractRepository(project_dir=project_dir)
        contracts = repo.list_all()
        assert contracts, "expected shipped built-in contracts to load"

        for contract in contracts:
            path = repo.save(contract)
            contents = path.read_bytes()
            if contract.id == "review":
                assert b"gates:" in contents
            else:
                assert b"gates:" not in contents, (
                    f"{contract.id} re-saved with a spurious `gates:` key"
                )


# ---------------------------------------------------------------------------
# Back-compat (T025)
# ---------------------------------------------------------------------------


class TestBackCompat:
    def test_every_built_in_contract_loads_with_gates_resolved(self) -> None:
        """Absent `gates` loads to `[]`; `review` is the sole gated contract."""
        repo = MissionStepContractRepository()
        contracts = repo.list_all()
        assert contracts, "expected the shipped built-in contracts to load"

        for contract in contracts:
            if contract.id == "review":
                assert len(contract.gates) == 1
            else:
                assert contract.gates == [], (
                    f"{contract.id} unexpectedly declares gates"
                )

    def test_no_top_level_key_allowlist_blocks_the_review_contract(self) -> None:
        """Guard against a hidden C-009-style allowlist silently dropping `gates`.

        ``tests/specify_cli/mission_step_contracts/test_documentation_composition.py``
        enforces a top-level-key allowlist, but it is parametrized only over
        the ``documentation-*`` contracts -- it never inspects
        ``review.step-contract.yaml``. This test is the positive confirmation
        that the review contract's new `gates` key is not silently rejected
        or dropped by any loader-side mechanism: loading it through the
        canonical repository preserves the binding.
        """
        repo = MissionStepContractRepository()
        contract = repo.get_by_action("software-dev", "review")
        assert contract is not None
        assert contract.gates != [], (
            "the review contract's `gates` key was dropped somewhere in the "
            "load path -- check for a hidden top-level-key allowlist"
        )
