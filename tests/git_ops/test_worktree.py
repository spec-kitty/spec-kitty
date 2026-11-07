"""Unit tests for worktree management utilities."""

from __future__ import annotations


from pathlib import Path

import pytest

from specify_cli.consolidation.mission_number.bake import assign_next_mission_number
from specify_cli.core.worktree import (
    validate_feature_structure,
)

pytestmark = pytest.mark.git_repo
TEST_MISSION_ID = "01KNXQS9ATWWFXS3K5ZJ9E5008"
TEST_MID8 = TEST_MISSION_ID[:8]

class TestAssignNextMissionNumber:
    """Tests for merge-time display-number allocation."""

    def test_returns_1_when_no_features_exist(self, tmp_path: Path) -> None:
        """Should return 1 when no numbered missions exist."""
        specs_dir = tmp_path / "kitty-specs"
        specs_dir.mkdir()
        result = assign_next_mission_number(tmp_path, specs_dir)
        assert result == 1

    def test_scans_kitty_specs_directory(self, tmp_path: Path) -> None:
        """Should scan kitty-specs/ for integer mission_number values."""
        specs_dir = tmp_path / "kitty-specs"
        specs_dir.mkdir()
        for name, number in (
            ("alpha", 1),
            ("beta", 2),
            ("gamma", 5),
        ):
            mission_dir = specs_dir / f"{name}-{TEST_MID8}"
            mission_dir.mkdir()
            (mission_dir / "meta.json").write_text(f'{{"mission_number": {number}}}', encoding="utf-8")

        result = assign_next_mission_number(tmp_path, specs_dir)
        assert result == 6

    def test_ignores_missing_or_non_integer_mission_numbers(self, tmp_path: Path) -> None:
        """Should ignore missions with null, string, or absent mission_number."""
        specs_dir = tmp_path / "kitty-specs"
        specs_dir.mkdir()
        for name, payload in (
            ("alpha", '{"mission_number": null}'),
            ("beta", '{"mission_number": "003"}'),
            ("gamma", '{"mission_slug": "gamma"}'),
            ("delta", '{"mission_number": 4}'),
        ):
            mission_dir = specs_dir / f"{name}-{TEST_MID8}"
            mission_dir.mkdir()
            (mission_dir / "meta.json").write_text(payload, encoding="utf-8")

        result = assign_next_mission_number(tmp_path, specs_dir)
        assert result == 5


class TestValidateFeatureStructure:
    """Tests for validate_feature_structure function."""

    def test_validates_missing_feature_directory(self, tmp_path: Path) -> None:
        """Should return error when feature directory doesn't exist."""
        # Setup
        feature_dir = tmp_path / "nonexistent"

        # Execute
        result = validate_feature_structure(feature_dir)

        # Verify
        assert result["valid"] is False
        assert "Feature directory not found" in result["errors"][0]
        assert result["warnings"] == []

    def test_validates_missing_spec_file(self, tmp_path: Path) -> None:
        """Should return error when spec.md is missing."""
        # Setup
        feature_dir = tmp_path / "001-test"
        feature_dir.mkdir()

        # Execute
        result = validate_feature_structure(feature_dir)

        # Verify
        assert result["valid"] is False
        assert "Missing required file: spec.md" in result["errors"]

    def test_warns_about_missing_directories(self, tmp_path: Path) -> None:
        """Should return warnings when recommended directories are missing."""
        # Setup
        feature_dir = tmp_path / "001-test"
        feature_dir.mkdir()
        (feature_dir / "spec.md").write_text("spec")

        # Execute
        result = validate_feature_structure(feature_dir)

        # Verify
        assert result["valid"] is True  # Not an error, just warnings
        assert "Missing recommended directory: checklists/" in result["warnings"]
        assert "Missing recommended directory: research/" in result["warnings"]
        assert "Missing recommended directory: tasks/" in result["warnings"]

    def test_validates_complete_structure(self, tmp_path: Path) -> None:
        """Should pass validation when all required files and directories exist."""
        # Setup
        feature_dir = tmp_path / "001-test"
        feature_dir.mkdir()
        (feature_dir / "spec.md").write_text("spec")
        (feature_dir / "checklists").mkdir()
        (feature_dir / "research").mkdir()
        (feature_dir / "tasks").mkdir()

        # Execute
        result = validate_feature_structure(feature_dir)

        # Verify
        assert result["valid"] is True
        assert result["errors"] == []
        assert result["warnings"] == []
        assert result["paths"]["mission_dir"] == result["paths"]["feature_dir"]

    def test_validates_tasks_md_when_requested(self, tmp_path: Path) -> None:
        """Should validate tasks.md exists when check_tasks=True."""
        # Setup
        feature_dir = tmp_path / "001-test"
        feature_dir.mkdir()
        (feature_dir / "spec.md").write_text("spec")

        # Execute
        result = validate_feature_structure(feature_dir, check_tasks=True)

        # Verify
        assert result["valid"] is False
        assert "Missing required file: tasks.md" in result["errors"]

    def test_includes_tasks_file_when_present_without_strict_tasks_check(self, tmp_path: Path) -> None:
        """Should expose tasks.md path when present even if check_tasks=False."""
        feature_dir = tmp_path / "001-test"
        feature_dir.mkdir()
        (feature_dir / "spec.md").write_text("spec")
        (feature_dir / "tasks.md").write_text("tasks")

        result = validate_feature_structure(feature_dir, check_tasks=False)

        assert result["valid"] is True
        assert result["paths"]["tasks_file"] == str(feature_dir / "tasks.md")
        assert result["artifact_files"]["tasks_file"] == str(feature_dir / "tasks.md")
        assert "tasks.md" in result["available_docs"]

    def test_includes_paths_in_result(self, tmp_path: Path) -> None:
        """Should include important paths in validation result."""
        # Setup
        feature_dir = tmp_path / "001-test"
        feature_dir.mkdir()
        (feature_dir / "spec.md").write_text("spec")
        (feature_dir / "checklists").mkdir()
        (feature_dir / "research").mkdir()
        (feature_dir / "tasks").mkdir()

        # Execute
        result = validate_feature_structure(feature_dir)

        # Verify
        assert "paths" in result
        assert result["paths"]["spec_file"] == str(feature_dir / "spec.md")
        assert result["paths"]["checklists_dir"] == str(feature_dir / "checklists")
        assert result["paths"]["tasks_dir"] == str(feature_dir / "tasks")
        assert result["paths"]["feature_dir"] == str(feature_dir)
        # FR-010 (research_dir file-vs-dir fix): the research planning artifact is
        # the FILE ``research.md``, not the legacy ``research/`` directory. A bare
        # ``research/`` directory must NOT be surfaced as an artifact directory.
        assert "research_dir" not in result["paths"]
        assert "research_dir" not in result["artifact_dirs"]

    def test_includes_typed_artifact_maps_and_compat_aliases(self, tmp_path: Path) -> None:
        """Should expose deterministic file/dir maps with compatibility aliases.

        FR-010: the inventory is sourced from the canonical mission writer
        metadata, so writer-produced planning artifacts (``research.md``,
        ``data-model.md``) that exist on disk are reported truthfully, not
        omitted by a hardcoded spec/plan/tasks set.
        """
        feature_dir = tmp_path / "001-test"
        feature_dir.mkdir()
        (feature_dir / "spec.md").write_text("spec")
        (feature_dir / "plan.md").write_text("plan")
        (feature_dir / "tasks.md").write_text("tasks")
        (feature_dir / "research.md").write_text("research")
        (feature_dir / "data-model.md").write_text("data model")
        (feature_dir / "checklists").mkdir()
        (feature_dir / "tasks").mkdir()

        result = validate_feature_structure(feature_dir, check_tasks=True)

        assert result["artifact_files"]["spec_file"] == str(feature_dir / "spec.md")
        assert result["artifact_files"]["plan_file"] == str(feature_dir / "plan.md")
        assert result["artifact_files"]["tasks_file"] == str(feature_dir / "tasks.md")
        assert result["artifact_files"]["research_file"] == str(feature_dir / "research.md")
        assert result["artifact_files"]["data_model_file"] == str(feature_dir / "data-model.md")
        assert result["artifact_dirs"]["feature_dir"] == str(feature_dir)
        assert result["artifact_dirs"]["tasks_dir"] == str(feature_dir / "tasks")
        assert sorted(result["available_docs"]) == [
            "data-model.md",
            "plan.md",
            "research.md",
            "spec.md",
            "tasks.md",
        ]
        assert result["FEATURE_DIR"] == str(feature_dir)
        assert sorted(result["AVAILABLE_DOCS"]) == [
            "data-model.md",
            "plan.md",
            "research.md",
            "spec.md",
            "tasks.md",
        ]

    def test_inventory_reports_writer_artifacts_and_omits_absent(self, tmp_path: Path) -> None:
        """FR-010 red-first: research.md / data-model.md / quickstart.md are
        reported ONLY when present, sourced from the writer metadata.

        Before the fix the inventory hardcoded spec/plan/tasks and OMITTED these
        writer-produced planning artifacts even when present. After the fix they
        appear (present) and are correctly absent when not on disk.
        """
        feature_dir = tmp_path / "001-test"
        feature_dir.mkdir()
        (feature_dir / "spec.md").write_text("spec")
        (feature_dir / "plan.md").write_text("plan")
        (feature_dir / "research.md").write_text("research")
        (feature_dir / "data-model.md").write_text("data model")
        # quickstart.md deliberately NOT created.

        result = validate_feature_structure(feature_dir)

        assert "research.md" in result["available_docs"]
        assert "data-model.md" in result["available_docs"]
        assert result["artifact_files"]["research_file"] == str(feature_dir / "research.md")
        assert result["artifact_files"]["data_model_file"] == str(feature_dir / "data-model.md")
        # Absent optional artifacts stay out of the inventory (no false positives).
        assert "quickstart.md" not in result["available_docs"]
        assert "quickstart_file" not in result["artifact_files"]

    def test_inventory_reports_writer_directory_artifacts(self, tmp_path: Path) -> None:
        """FR-010: directory artifacts declared by the writer metadata
        (``contracts/``) are inventoried as artifact directories when present."""
        feature_dir = tmp_path / "001-test"
        feature_dir.mkdir()
        (feature_dir / "spec.md").write_text("spec")
        (feature_dir / "contracts").mkdir()

        result = validate_feature_structure(feature_dir)

        assert result["artifact_dirs"]["contracts_dir"] == str(feature_dir / "contracts")

    def test_inventory_does_not_drift_from_writer_metadata(self, tmp_path: Path) -> None:
        """NFR-004 / C-005 regression guard: the file-artifact inventory is
        derived from the canonical mission writer metadata, not a hardcoded set.

        Materialize every file artifact the software-dev writer declares and
        assert each shows up in ``available_docs``. If a future change re-hardcodes
        the inventory (dropping a writer-declared artifact), this goes red — the
        two-copy trap NFR-004 forbids.
        """
        from specify_cli.mission import get_mission_by_name

        mission = get_mission_by_name("software-dev")
        writer_files = [
            name
            for name in (*mission.get_required_artifacts(), *mission.get_optional_artifacts())
            if not name.endswith("/")
        ]
        assert writer_files, "writer metadata must declare at least one file artifact"

        feature_dir = tmp_path / "001-test"
        feature_dir.mkdir()
        for name in writer_files:
            (feature_dir / name).write_text(name)

        result = validate_feature_structure(feature_dir, check_tasks=True)

        for name in writer_files:
            assert name in result["available_docs"], (
                f"writer-declared artifact {name!r} missing from inventory "
                "(inventory drifted from mission writer metadata)"
            )
