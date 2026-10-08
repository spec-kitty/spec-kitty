"""Unit tests for MissionStepContractRepository."""

from pathlib import Path

import pytest
from ruamel.yaml import YAML

from charter.offering.missions.step_contracts import MissionStepContractRepository

pytestmark = [pytest.mark.fast, pytest.mark.corpus]


class TestMissionStepContractRepository:
    def test_list_all_from_shipped(self, tmp_contract_dir: Path) -> None:
        repo = MissionStepContractRepository(built_in_dir=tmp_contract_dir)
        contracts = repo.list_all()
        assert {c.id for c in contracts} == {"test-implement"}
        assert contracts[0].id == "test-implement"

    def test_get_by_id(self, tmp_contract_dir: Path) -> None:
        repo = MissionStepContractRepository(built_in_dir=tmp_contract_dir)
        contract = repo.get("test-implement")
        assert contract is not None
        assert contract.action == "implement"

    def test_get_returns_none_for_unknown(self, tmp_contract_dir: Path) -> None:
        repo = MissionStepContractRepository(built_in_dir=tmp_contract_dir)
        assert repo.get("nonexistent") is None

    def test_malformed_yaml_skipped_with_warning(self, tmp_path: Path) -> None:
        shipped = tmp_path / "built-in"
        shipped.mkdir()
        bad_file = shipped / "bad.step-contract.yaml"
        bad_file.write_text("not: valid: yaml: [")

        with pytest.warns(UserWarning, match="Skipping invalid"):
            repo = MissionStepContractRepository(built_in_dir=shipped)

        assert repo.list_all() == []

    def test_save_writes_valid_yaml(self, tmp_path: Path, minimal_step_contract_data: dict) -> None:
        from charter.offering.missions.step_contracts import MissionStepContract

        project_dir = tmp_path / "project"
        repo = MissionStepContractRepository(built_in_dir=tmp_path / "empty", project_dir=project_dir)

        contract = MissionStepContract.model_validate(minimal_step_contract_data)
        path = repo.save(contract)

        assert path.exists()
        assert path.suffix == ".yaml"

        yaml = YAML(typ="safe")
        data = yaml.load(path)
        assert data["id"] == "test-implement"

    def test_save_raises_without_project_dir(self, tmp_path: Path, minimal_step_contract_data: dict) -> None:
        from charter.offering.missions.step_contracts import MissionStepContract

        repo = MissionStepContractRepository(built_in_dir=tmp_path / "empty")
        contract = MissionStepContract.model_validate(minimal_step_contract_data)
        with pytest.raises(ValueError, match="project_dir not configured"):
            repo.save(contract)

    def test_field_level_merge_with_project_override(self, tmp_path: Path) -> None:
        shipped = tmp_path / "built-in"
        shipped.mkdir()
        project = tmp_path / "project"
        project.mkdir()

        yaml = YAML()
        yaml.default_flow_style = False

        base = {
            "schema_version": "1.0",
            "id": "merge-test",
            "action": "implement",
            "mission": "software-dev",
            "steps": [{"id": "s1", "description": "Base step"}],
        }
        override = {
            "schema_version": "1.0",
            "id": "merge-test",
            "action": "implement",
            "mission": "software-dev",
            "steps": [
                {"id": "s1", "description": "Overridden step"},
                {"id": "s2", "description": "Added step"},
            ],
        }

        with (shipped / "merge-test.step-contract.yaml").open("w") as f:
            yaml.dump(base, f)
        with (project / "merge-test.step-contract.yaml").open("w") as f:
            yaml.dump(override, f)

        repo = MissionStepContractRepository(built_in_dir=shipped, project_dir=project)
        contract = repo.get("merge-test")
        assert contract is not None
        assert len(contract.steps) == 2
        assert contract.steps[0].description == "Overridden step"

    def test_save_and_reload_preserves_fields(self, tmp_path: Path, full_step_contract_data: dict) -> None:
        """Acceptance: saving and reloading preserves all fields."""
        from charter.offering.missions.step_contracts import MissionStepContract

        project_dir = tmp_path / "project"
        repo = MissionStepContractRepository(built_in_dir=tmp_path / "empty", project_dir=project_dir)

        contract = MissionStepContract.model_validate(full_step_contract_data)
        repo.save(contract)

        repo2 = MissionStepContractRepository(built_in_dir=tmp_path / "empty", project_dir=project_dir)
        loaded = repo2.get("implement")
        assert loaded is not None
        assert loaded.action == contract.action
        assert loaded.mission == contract.mission
        assert len(loaded.steps) == len(contract.steps)

        # Verify delegation survived round-trip
        workspace_step = loaded.steps[1]
        assert workspace_step.delegates_to is not None
        assert workspace_step.delegates_to.kind == "paradigm"
        assert len(workspace_step.delegates_to.candidates) == 4

        # Verify guidance survived round-trip
        assert loaded.steps[4].guidance is not None

        # Verify command inputs survived round-trip.
        bootstrap_step = loaded.steps[0]
        assert [input.flag for input in bootstrap_step.inputs] == ["--profile", "--tool"]
        assert [input.source for input in bootstrap_step.inputs] == [
            "wp.agent_profile",
            "env.agent_tool",
        ]

    def test_shipped_contract_inputs_are_preserved_for_every_declaring_contract(self) -> None:
        repo = MissionStepContractRepository()
        shipped_dir = Path("packs/built-in/missions/built_in_step_contracts")
        yaml = YAML(typ="safe")

        declared: dict[str, list[dict[str, object]]] = {}
        for contract_path in sorted(shipped_dir.glob("*.step-contract.yaml")):
            raw = yaml.load(contract_path)
            first_step = raw["steps"][0]
            if first_step.get("inputs"):
                declared[raw["id"]] = first_step["inputs"]

        assert declared

        for contract_id, expected_inputs in declared.items():
            contract = repo.get(contract_id)
            assert contract is not None
            bootstrap_step = contract.steps[0]
            assert [input.flag for input in bootstrap_step.inputs] == [
                input_data["flag"] for input_data in expected_inputs
            ]
            assert [input.source for input in bootstrap_step.inputs] == [
                input_data["source"] for input_data in expected_inputs
            ]
            assert [input.optional for input in bootstrap_step.inputs] == [
                input_data.get("optional", False) for input_data in expected_inputs
            ]


class TestMissionStepContractRepositoryLookup:
    """Tests for the by_action lookup method."""

    def test_get_by_action_and_mission(self, tmp_path: Path) -> None:
        shipped = tmp_path / "built-in"
        shipped.mkdir()

        yaml = YAML()
        yaml.default_flow_style = False

        for action in ("implement", "review"):
            data = {
                "schema_version": "1.0",
                "id": action,
                "action": action,
                "mission": "software-dev",
                "steps": [{"id": "s1", "description": f"{action} step"}],
            }
            with (shipped / f"{action}.step-contract.yaml").open("w") as f:
                yaml.dump(data, f)

        repo = MissionStepContractRepository(built_in_dir=shipped)
        contract = repo.get_by_action("software-dev", "implement")
        assert contract is not None
        assert contract.action == "implement"

        review = repo.get_by_action("software-dev", "review")
        assert review is not None
        assert review.action == "review"

        assert repo.get_by_action("software-dev", "nonexistent") is None
        assert repo.get_by_action("other-mission", "implement") is None
