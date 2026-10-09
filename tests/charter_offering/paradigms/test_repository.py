"""Unit tests for ParadigmRepository."""

from pathlib import Path

import pytest
from ruamel.yaml import YAML

from charter.offering.paradigms.repository import ParadigmRepository
pytestmark = [pytest.mark.fast, pytest.mark.doctrine]



class TestParadigmRepository:
    def test_list_all_from_shipped(self, tmp_paradigm_dir: Path) -> None:
        """list_all returns all paradigms from the given directory."""
        repo = ParadigmRepository(built_in_dir=tmp_paradigm_dir)
        paradigms = repo.list_all()
        assert {p.id for p in paradigms} == {"test-first"}

    def test_get_by_id(self, tmp_paradigm_dir: Path) -> None:
        """get() returns paradigm by ID."""
        repo = ParadigmRepository(built_in_dir=tmp_paradigm_dir)
        paradigm = repo.get("test-first")
        assert paradigm is not None
        assert paradigm.name == "Test-First Doctrine"

    def test_get_returns_none_for_unknown(self, tmp_paradigm_dir: Path) -> None:
        repo = ParadigmRepository(built_in_dir=tmp_paradigm_dir)
        assert repo.get("nonexistent-paradigm") is None

    def test_load_from_custom_shipped_dir(self, tmp_paradigm_dir: Path) -> None:
        repo = ParadigmRepository(built_in_dir=tmp_paradigm_dir)
        paradigms = repo.list_all()
        assert {p.id for p in paradigms} == {"test-first"}
        assert paradigms[0].id == "test-first"

    def test_malformed_yaml_skipped_with_warning(self, tmp_path: Path) -> None:
        shipped = tmp_path / "built-in"
        shipped.mkdir()
        bad_file = shipped / "bad.paradigm.yaml"
        bad_file.write_text("not: valid: yaml: [")

        with pytest.warns(UserWarning, match="Skipping invalid"):
            repo = ParadigmRepository(built_in_dir=shipped)

        assert repo.list_all() == []

    def test_save_writes_valid_yaml(self, tmp_path: Path, sample_paradigm_data: dict) -> None:
        from charter.offering.paradigms.models import Paradigm

        project_dir = tmp_path / "project"
        repo = ParadigmRepository(built_in_dir=tmp_path / "empty", project_dir=project_dir)

        paradigm = Paradigm.model_validate(sample_paradigm_data)
        path = repo.save(paradigm)

        assert path.exists()
        assert path.suffix == ".yaml"

        yaml = YAML(typ="safe")
        data = yaml.load(path)
        assert data["id"] == "test-first"

    def test_save_raises_without_project_dir(self, tmp_path: Path, sample_paradigm_data: dict) -> None:
        from charter.offering.paradigms.models import Paradigm


        repo = ParadigmRepository(built_in_dir=tmp_path / "empty")
        paradigm = Paradigm.model_validate(sample_paradigm_data)
        with pytest.raises(ValueError, match="project_dir not configured"):
            repo.save(paradigm)

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
            "name": "Base Name",
            "summary": "Base summary",
        }
        override = {
            "schema_version": "1.0",
            "id": "merge-test",
            "name": "Overridden Name",
            "summary": "Overridden summary",
        }

        with (shipped / "merge-test.paradigm.yaml").open("w") as f:
            yaml.dump(base, f)
        with (project / "merge-test.paradigm.yaml").open("w") as f:
            yaml.dump(override, f)

        repo = ParadigmRepository(built_in_dir=shipped, project_dir=project)
        paradigm = repo.get("merge-test")
        assert paradigm is not None
        assert paradigm.name == "Overridden Name"
        assert paradigm.summary == "Overridden summary"

