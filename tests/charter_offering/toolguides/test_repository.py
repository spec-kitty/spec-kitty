"""Unit tests for ToolguideRepository."""

from pathlib import Path

import pytest
from ruamel.yaml import YAML

from charter.offering.toolguides.repository import ToolguideRepository
pytestmark = [pytest.mark.fast, pytest.mark.doctrine]



class TestToolguideRepository:
    def test_list_all_from_shipped(self, tmp_toolguide_dir: Path) -> None:
        """list_all returns all toolguides from the given directory."""
        repo = ToolguideRepository(built_in_dir=tmp_toolguide_dir)
        toolguides = repo.list_all()
        assert {t.id for t in toolguides} == {"test-toolguide"}

    def test_get_by_id(self, tmp_toolguide_dir: Path) -> None:
        """get() returns toolguide by ID."""
        repo = ToolguideRepository(built_in_dir=tmp_toolguide_dir)
        toolguide = repo.get("test-toolguide")
        assert toolguide is not None
        assert toolguide.tool == "bash"

    def test_get_returns_none_for_unknown(self, tmp_toolguide_dir: Path) -> None:
        repo = ToolguideRepository(built_in_dir=tmp_toolguide_dir)
        assert repo.get("nonexistent-toolguide") is None

    def test_load_from_custom_shipped_dir(self, tmp_toolguide_dir: Path) -> None:
        repo = ToolguideRepository(built_in_dir=tmp_toolguide_dir)
        toolguides = repo.list_all()
        assert {t.id for t in toolguides} == {"test-toolguide"}
        assert toolguides[0].id == "test-toolguide"

    def test_malformed_yaml_skipped_with_warning(self, tmp_path: Path) -> None:
        shipped = tmp_path / "built-in"
        shipped.mkdir()
        bad_file = shipped / "bad.toolguide.yaml"
        bad_file.write_text("not: valid: yaml: [")

        with pytest.warns(UserWarning, match="Skipping invalid"):
            repo = ToolguideRepository(built_in_dir=shipped)

        assert repo.list_all() == []

    def test_save_writes_valid_yaml(self, tmp_path: Path, sample_toolguide_data: dict) -> None:
        from charter.offering.toolguides.models import Toolguide

        project_dir = tmp_path / "project"
        repo = ToolguideRepository(built_in_dir=tmp_path / "empty", project_dir=project_dir)

        toolguide = Toolguide.model_validate(sample_toolguide_data)
        path = repo.save(toolguide)

        assert path.exists()
        assert path.suffix == ".yaml"

        yaml = YAML(typ="safe")
        data = yaml.load(path)
        assert data["id"] == "test-toolguide"

    def test_save_raises_without_project_dir(self, tmp_path: Path, sample_toolguide_data: dict) -> None:
        from charter.offering.toolguides.models import Toolguide


        repo = ToolguideRepository(built_in_dir=tmp_path / "empty")
        toolguide = Toolguide.model_validate(sample_toolguide_data)
        with pytest.raises(ValueError, match="project_dir not configured"):
            repo.save(toolguide)

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
            "tool": "bash",
            "title": "Base Title",
            "guide_path": "src/charter/offering/toolguides/built-in/POWERSHELL_SYNTAX.md",
            "summary": "Base summary",
        }
        override = {
            "schema_version": "1.0",
            "id": "merge-test",
            "tool": "powershell",
            "title": "Overridden Title",
            "guide_path": "src/charter/offering/toolguides/built-in/POWERSHELL_SYNTAX.md",
            "summary": "Overridden summary",
            "commands": ["spec-kitty"],
        }

        with (shipped / "merge-test.toolguide.yaml").open("w") as f:
            yaml.dump(base, f)
        with (project / "merge-test.toolguide.yaml").open("w") as f:
            yaml.dump(override, f)

        repo = ToolguideRepository(built_in_dir=shipped, project_dir=project)
        toolguide = repo.get("merge-test")
        assert toolguide is not None
        assert toolguide.tool == "powershell"
        assert toolguide.title == "Overridden Title"
        assert toolguide.commands == ["spec-kitty"]

    def test_filters_language_scoped_toolguides_when_active_languages_do_not_match(
        self, tmp_path: Path
    ) -> None:
        shipped = tmp_path / "built-in"
        shipped.mkdir()

        yaml = YAML()
        yaml.default_flow_style = False

        with (shipped / "python.toolguide.yaml").open("w", encoding="utf-8") as handle:
            yaml.dump(
                {
                    "schema_version": "1.0",
                    "id": "python-toolguide",
                    "tool": "pytest",
                    "title": "Python Toolguide",
                    "guide_path": "src/charter/offering/toolguides/built-in/python.md",
                    "summary": "Python checks",
                    "applies_to_languages": ["python"],
                },
                handle,
            )
        with (shipped / "generic.toolguide.yaml").open("w", encoding="utf-8") as handle:
            yaml.dump(
                {
                    "schema_version": "1.0",
                    "id": "generic-toolguide",
                    "tool": "git",
                    "title": "Generic Toolguide",
                    "guide_path": "src/charter/offering/toolguides/built-in/generic.md",
                    "summary": "Generic checks",
                },
                handle,
            )

        repo = ToolguideRepository(built_in_dir=shipped, active_languages=["typescript"])
        toolguide_ids = {toolguide.id for toolguide in repo.list_all()}

        assert "generic-toolguide" in toolguide_ids
        assert "python-toolguide" not in toolguide_ids

    def test_skips_project_toolguides_when_language_scope_does_not_match(
        self, tmp_path: Path
    ) -> None:
        shipped = tmp_path / "built-in"
        shipped.mkdir()
        project = tmp_path / "project"
        project.mkdir()

        yaml = YAML()
        yaml.default_flow_style = False

        with (shipped / "merge-test.toolguide.yaml").open("w", encoding="utf-8") as handle:
            yaml.dump(
                {
                    "schema_version": "1.0",
                    "id": "merge-test",
                    "tool": "bash",
                    "title": "Base Title",
                    "guide_path": "src/charter/offering/toolguides/built-in/base.md",
                    "summary": "Base summary",
                },
                handle,
            )
        with (project / "merge-test.toolguide.yaml").open("w", encoding="utf-8") as handle:
            yaml.dump(
                {
                    "schema_version": "1.0",
                    "id": "merge-test",
                    "tool": "pytest",
                    "title": "Python Override",
                    "guide_path": "src/charter/offering/toolguides/built-in/python.md",
                    "summary": "Python summary",
                    "applies_to_languages": ["python"],
                },
                handle,
            )
        with (project / "python-only.toolguide.yaml").open("w", encoding="utf-8") as handle:
            yaml.dump(
                {
                    "schema_version": "1.0",
                    "id": "python-only",
                    "tool": "pytest",
                    "title": "Python Only",
                    "guide_path": "src/charter/offering/toolguides/built-in/python.md",
                    "summary": "Python summary",
                    "applies_to_languages": ["python"],
                },
                handle,
            )

        repo = ToolguideRepository(
            built_in_dir=shipped,
            project_dir=project,
            active_languages=["typescript"],
        )

        merge_test = repo.get("merge-test")
        assert merge_test is not None
        assert merge_test.tool == "bash"
        assert repo.get("python-only") is None
