"""Unit tests for doctrine-native step-contract resolution (WP11, FR-008).

These pin the doctrine primitive that makes the ``MissionStepContractRepository``
artefact the single answer for "which step contracts does a mission type
declare": :meth:`MissionStepContractRepository.get_by_mission` and the
module-level :func:`resolve_step_contract_ids` the charter seam calls to fill
``ResolvedMissionType.step_contracts``.
"""

from pathlib import Path

import pytest
from ruamel.yaml import YAML

from charter.offering.missions.step_contracts import (
    MissionStepContractRepository,
    resolve_step_contract_ids,
)

pytestmark = pytest.mark.fast


def _write_contract(directory: Path, *, contract_id: str, action: str, mission: str) -> None:
    yaml = YAML()
    yaml.default_flow_style = False
    data = {
        "schema_version": "1.0",
        "id": contract_id,
        "action": action,
        "mission": mission,
        "steps": [{"id": "s1", "description": f"{action} step"}],
    }
    with (directory / f"{contract_id}.step-contract.yaml").open("w") as handle:
        yaml.dump(data, handle)


@pytest.fixture
def multi_mission_repo(tmp_path: Path) -> MissionStepContractRepository:
    shipped = tmp_path / "built-in"
    shipped.mkdir()
    # Deliberately author out of action order + interleave missions so the
    # test proves the resolver imposes a deterministic action-ordered result
    # rather than echoing on-disk discovery order.
    _write_contract(shipped, contract_id="sd-review", action="review", mission="software-dev")
    _write_contract(shipped, contract_id="sd-implement", action="implement", mission="software-dev")
    _write_contract(shipped, contract_id="sd-plan", action="plan", mission="software-dev")
    _write_contract(shipped, contract_id="doc-audit", action="audit", mission="documentation")
    return MissionStepContractRepository(built_in_dir=shipped)


class TestGetByMission:
    def test_filters_on_mission_field(self, multi_mission_repo: MissionStepContractRepository) -> None:
        contracts = multi_mission_repo.get_by_mission("software-dev")
        assert {c.id for c in contracts} == {"sd-review", "sd-implement", "sd-plan"}
        assert all(c.mission == "software-dev" for c in contracts)

    def test_orders_by_action_deterministically(
        self, multi_mission_repo: MissionStepContractRepository
    ) -> None:
        actions = [c.action for c in multi_mission_repo.get_by_mission("software-dev")]
        assert actions == ["implement", "plan", "review"]

    def test_unknown_mission_is_empty(self, multi_mission_repo: MissionStepContractRepository) -> None:
        assert multi_mission_repo.get_by_mission("no-such-mission") == []


class TestResolveStepContractIds:
    def test_returns_action_ordered_ids(
        self, multi_mission_repo: MissionStepContractRepository
    ) -> None:
        assert resolve_step_contract_ids("software-dev", repository=multi_mission_repo) == [
            "sd-implement",
            "sd-plan",
            "sd-review",
        ]

    def test_unknown_type_is_empty(
        self, multi_mission_repo: MissionStepContractRepository
    ) -> None:
        assert resolve_step_contract_ids("no-such-mission", repository=multi_mission_repo) == []

    def test_default_repository_reads_shipped_software_dev_contracts(self) -> None:
        # No injected repository: the resolver constructs the built-in artefact
        # repository and answers from the shipped doctrine tree (FR-008).
        ids = resolve_step_contract_ids("software-dev")
        assert set(ids) == {"specify", "plan", "tasks", "implement", "review"}
