"""Unit tests for TacticRepository."""

from pathlib import Path

import pytest
from ruamel.yaml import YAML

from charter.offering.tactics.repository import TacticRepository
pytestmark = [pytest.mark.fast, pytest.mark.doctrine]



class TestTacticRepository:
    def test_list_all_from_shipped(self, tmp_tactic_dir: Path) -> None:
        """list_all returns all tactics from the given directory."""
        repo = TacticRepository(built_in_dir=tmp_tactic_dir)
        tactics = repo.list_all()
        assert {t.id for t in tactics} == {"test-tactic"}
        assert tactics[0].id == "test-tactic"

    def test_get_by_id(self, tmp_tactic_dir: Path) -> None:
        """get() with kebab-case ID returns the tactic."""
        repo = TacticRepository(built_in_dir=tmp_tactic_dir)
        tactic = repo.get("test-tactic")
        assert tactic is not None
        assert tactic.name == "Test Tactic"
        assert len(tactic.steps) == 1

    def test_get_returns_none_for_unknown(self, tmp_tactic_dir: Path) -> None:
        repo = TacticRepository(built_in_dir=tmp_tactic_dir)
        assert repo.get("nonexistent-tactic") is None

    def test_malformed_yaml_skipped_with_warning(self, tmp_path: Path) -> None:
        """Malformed YAML files are skipped, not crash."""
        shipped = tmp_path / "built-in"
        shipped.mkdir()
        bad_file = shipped / "bad.tactic.yaml"
        bad_file.write_text("not: valid: yaml: [")

        with pytest.warns(UserWarning, match="Skipping invalid"):
            repo = TacticRepository(built_in_dir=shipped)

        assert repo.list_all() == []

    def test_save_writes_valid_yaml(
        self, tmp_path: Path, sample_tactic_data: dict
    ) -> None:
        from charter.offering.tactics.models import Tactic

        project_dir = tmp_path / "project"
        repo = TacticRepository(
            built_in_dir=tmp_path / "empty", project_dir=project_dir
        )

        tactic = Tactic.model_validate(sample_tactic_data)
        path = repo.save(tactic)

        assert path.exists()
        assert path.suffix == ".yaml"

        yaml = YAML(typ="safe")
        data = yaml.load(path)
        assert data["id"] == "test-tactic"

    def test_save_raises_without_project_dir(
        self, tmp_path: Path, sample_tactic_data: dict
    ) -> None:
        from charter.offering.tactics.models import Tactic

        repo = TacticRepository(built_in_dir=tmp_path / "empty")
        tactic = Tactic.model_validate(sample_tactic_data)
        with pytest.raises(ValueError, match="project_dir not configured"):
            repo.save(tactic)

    def test_field_level_merge_with_project_override(
        self, tmp_path: Path
    ) -> None:
        """Project tactic overrides shipped fields at field level."""
        shipped = tmp_path / "built-in"
        shipped.mkdir()
        project = tmp_path / "project"
        project.mkdir()

        yaml = YAML()
        yaml.default_flow_style = False

        base = {
            "schema_version": "1.0",
            "id": "merge-test",
            "name": "Base Name",
            "steps": [{"title": "Base Step"}],
        }
        override = {
            "schema_version": "1.0",
            "id": "merge-test",
            "name": "Overridden Name",
            "purpose": "Added purpose",
            "steps": [{"title": "Overridden Step"}],
        }

        with (shipped / "merge-test.tactic.yaml").open("w") as f:
            yaml.dump(base, f)
        with (project / "merge-test.tactic.yaml").open("w") as f:
            yaml.dump(override, f)

        repo = TacticRepository(built_in_dir=shipped, project_dir=project)
        tactic = repo.get("merge-test")
        assert tactic is not None
        assert tactic.name == "Overridden Name"
        assert tactic.purpose == "Added purpose"

    def test_nested_models_parse(self, tmp_path: Path) -> None:
        """Tactics with steps parse nested models correctly."""
        from ruamel.yaml import YAML as RuamelYAML

        shipped = tmp_path / "tactics"
        shipped.mkdir()
        data = {
            "schema_version": "1.0",
            "id": "nested-test",
            "name": "Nested Test",
            "steps": [
                {"title": "Step A", "examples": ["Example 1", "Example 2"]},
                {"title": "Step B"},
            ],
        }
        y = RuamelYAML()
        y.default_flow_style = False
        with (shipped / "nested-test.tactic.yaml").open("w") as f:
            y.dump(data, f)

        repo = TacticRepository(built_in_dir=shipped)
        tactic = repo.get("nested-test")
        assert tactic is not None
        assert tactic.steps[0].title == "Step A"
        assert len(tactic.steps[0].examples) == 2

    def test_save_and_reload_preserves_fields(
        self, tmp_path: Path, enriched_tactic_data: dict
    ) -> None:
        """Acceptance: saving and reloading preserves all fields."""
        from charter.offering.tactics.models import Tactic


        project_dir = tmp_path / "project"
        repo = TacticRepository(
            built_in_dir=tmp_path / "empty", project_dir=project_dir
        )

        tactic = Tactic.model_validate(enriched_tactic_data)
        repo.save(tactic)

        repo2 = TacticRepository(
            built_in_dir=tmp_path / "empty", project_dir=project_dir
        )
        loaded = repo2.get("enriched-tactic")
        assert loaded is not None
        assert loaded.name == tactic.name
        assert loaded.purpose == tactic.purpose
        assert len(loaded.steps) == len(tactic.steps)
        assert len(loaded.references) == len(tactic.references)

    def test_filters_language_scoped_tactics_when_active_languages_do_not_match(
        self, tmp_path: Path
    ) -> None:
        shipped = tmp_path / "built-in"
        shipped.mkdir()

        yaml = YAML()
        yaml.default_flow_style = False

        with (shipped / "python.tactic.yaml").open("w", encoding="utf-8") as handle:
            yaml.dump(
                {
                    "schema_version": "1.0",
                    "id": "python-tactic",
                    "name": "Python Tactic",
                    "applies_to_languages": ["python"],
                    "steps": [{"title": "Run Python workflow"}],
                },
                handle,
            )
        with (shipped / "generic.tactic.yaml").open("w", encoding="utf-8") as handle:
            yaml.dump(
                {
                    "schema_version": "1.0",
                    "id": "generic-tactic",
                    "name": "Generic Tactic",
                    "steps": [{"title": "Run generic workflow"}],
                },
                handle,
            )

        repo = TacticRepository(built_in_dir=shipped, active_languages=["typescript"])
        tactic_ids = {tactic.id for tactic in repo.list_all()}

        assert "generic-tactic" in tactic_ids
        assert "python-tactic" not in tactic_ids

    def test_skips_project_tactics_when_language_scope_does_not_match(
        self, tmp_path: Path
    ) -> None:
        shipped = tmp_path / "built-in"
        shipped.mkdir()
        project = tmp_path / "project"
        project.mkdir()

        yaml = YAML()
        yaml.default_flow_style = False

        with (shipped / "merge-test.tactic.yaml").open("w", encoding="utf-8") as handle:
            yaml.dump(
                {
                    "schema_version": "1.0",
                    "id": "merge-test",
                    "name": "Base Name",
                    "steps": [{"title": "Base Step"}],
                },
                handle,
            )
        with (project / "merge-test.tactic.yaml").open("w", encoding="utf-8") as handle:
            yaml.dump(
                {
                    "schema_version": "1.0",
                    "id": "merge-test",
                    "name": "Python Override",
                    "applies_to_languages": ["python"],
                    "steps": [{"title": "Python Step"}],
                },
                handle,
            )
        with (project / "python-only.tactic.yaml").open("w", encoding="utf-8") as handle:
            yaml.dump(
                {
                    "schema_version": "1.0",
                    "id": "python-only",
                    "name": "Python Only",
                    "applies_to_languages": ["python"],
                    "steps": [{"title": "Python Step"}],
                },
                handle,
            )

        repo = TacticRepository(
            built_in_dir=shipped,
            project_dir=project,
            active_languages=["typescript"],
        )

        merge_test = repo.get("merge-test")
        assert merge_test is not None
        assert merge_test.name == "Base Name"
        assert repo.get("python-only") is None
