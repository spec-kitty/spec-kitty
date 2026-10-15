"""Unit tests for wps_manifest module."""
from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from specify_cli.core.wps_manifest import (
    WorkPackageEntry,
    WpsManifest,
    dependencies_are_explicit,
    generate_tasks_md_from_manifest,
    load_wps_manifest,
)


pytestmark = [pytest.mark.unit, pytest.mark.fast]
class TestLoadWpsManifest:
    def test_load_valid_manifest(self, tmp_path: Path) -> None:
        wps = tmp_path / "wps.yaml"
        wps.write_text(
            "work_packages:\n"
            "  - id: WP01\n"
            "    title: 'First WP'\n"
            "    dependencies: []\n",
            encoding="utf-8",
        )
        manifest = load_wps_manifest(tmp_path)
        assert manifest is not None
        assert frozenset(wp.id for wp in manifest.work_packages) == frozenset({"WP01"})
        assert manifest.work_packages[0].title == "First WP"

    def test_absent_returns_none(self, tmp_path: Path) -> None:
        result = load_wps_manifest(tmp_path)
        assert result is None

    def test_malformed_raises_validation_error_with_field_name(self, tmp_path: Path) -> None:
        wps = tmp_path / "wps.yaml"
        wps.write_text(
            "work_packages:\n  - id: INVALID_ID\n    title: 'test'\n",
            encoding="utf-8",
        )
        with pytest.raises(ValidationError) as exc_info:
            load_wps_manifest(tmp_path)
        error_str = str(exc_info.value)
        assert "id" in error_str or "WP" in error_str  # field name appears in error

    def test_missing_required_title_raises(self, tmp_path: Path) -> None:
        wps = tmp_path / "wps.yaml"
        wps.write_text(
            "work_packages:\n  - id: WP01\n",  # missing title
            encoding="utf-8",
        )
        with pytest.raises(ValidationError):
            load_wps_manifest(tmp_path)

    def test_load_multiple_work_packages(self, tmp_path: Path) -> None:
        wps = tmp_path / "wps.yaml"
        wps.write_text(
            "work_packages:\n"
            "  - id: WP01\n"
            "    title: 'First'\n"
            "  - id: WP02\n"
            "    title: 'Second'\n"
            "    dependencies: [WP01]\n",
            encoding="utf-8",
        )
        manifest = load_wps_manifest(tmp_path)
        assert manifest is not None
        assert frozenset(wp.id for wp in manifest.work_packages) == frozenset({"WP01", "WP02"})
        assert manifest.work_packages[1].dependencies == ["WP01"]

    def test_invalid_dependency_raises(self, tmp_path: Path) -> None:
        wps = tmp_path / "wps.yaml"
        wps.write_text(
            "work_packages:\n"
            "  - id: WP01\n"
            "    title: 'T'\n"
            "    dependencies: [NOTAWP]\n",
            encoding="utf-8",
        )
        with pytest.raises(ValidationError):
            load_wps_manifest(tmp_path)

    def test_optional_fields_default(self, tmp_path: Path) -> None:
        wps = tmp_path / "wps.yaml"
        wps.write_text(
            "work_packages:\n  - id: WP01\n    title: 'Minimal'\n",
            encoding="utf-8",
        )
        manifest = load_wps_manifest(tmp_path)
        assert manifest is not None
        entry = manifest.work_packages[0]
        assert entry.dependencies == []
        assert entry.owned_files == []
        assert entry.requirement_refs == []
        assert entry.subtasks == []
        assert entry.prompt_file is None
        assert entry.plan_concern_refs == []
        assert entry.cross_cutting is False


class TestDependenciesAreExplicit:
    def test_present_empty_list_is_explicit(self, tmp_path: Path) -> None:
        """dependencies: [] in YAML → explicit."""
        wps = tmp_path / "wps.yaml"
        wps.write_text(
            "work_packages:\n  - id: WP01\n    title: 'T'\n    dependencies: []\n",
            encoding="utf-8",
        )
        manifest = load_wps_manifest(tmp_path)
        assert manifest is not None
        assert dependencies_are_explicit(manifest.work_packages[0]) is True

    def test_absent_key_is_not_explicit(self, tmp_path: Path) -> None:
        """No 'dependencies' key in YAML → not explicit."""
        wps = tmp_path / "wps.yaml"
        wps.write_text(
            "work_packages:\n  - id: WP01\n    title: 'T'\n",
            encoding="utf-8",
        )
        manifest = load_wps_manifest(tmp_path)
        assert manifest is not None
        assert dependencies_are_explicit(manifest.work_packages[0]) is False

    def test_present_nonempty_list_is_explicit(self, tmp_path: Path) -> None:
        wps = tmp_path / "wps.yaml"
        wps.write_text(
            "work_packages:\n  - id: WP02\n    title: 'T'\n    dependencies: [WP01]\n",
            encoding="utf-8",
        )
        manifest = load_wps_manifest(tmp_path)
        assert manifest is not None
        assert dependencies_are_explicit(manifest.work_packages[0]) is True

    def test_multiple_wps_track_independently(self, tmp_path: Path) -> None:
        wps = tmp_path / "wps.yaml"
        wps.write_text(
            "work_packages:\n"
            "  - id: WP01\n"
            "    title: 'With deps key'\n"
            "    dependencies: []\n"
            "  - id: WP02\n"
            "    title: 'Without deps key'\n",
            encoding="utf-8",
        )
        manifest = load_wps_manifest(tmp_path)
        assert manifest is not None
        assert dependencies_are_explicit(manifest.work_packages[0]) is True
        assert dependencies_are_explicit(manifest.work_packages[1]) is False


class TestGenerateTasksMd:
    def _make_manifest(self) -> WpsManifest:
        return WpsManifest(
            work_packages=[
                WorkPackageEntry(
                    id="WP01",
                    title="First",
                    dependencies=[],
                    subtasks=["T001", "T002"],
                    requirement_refs=["FR-001"],
                ),
                WorkPackageEntry(
                    id="WP02",
                    title="Second",
                    dependencies=["WP01"],
                ),
            ]
        )

    def test_contains_all_wp_titles(self) -> None:
        md = generate_tasks_md_from_manifest(self._make_manifest(), "Test Feature")
        assert "First" in md
        assert "Second" in md

    def test_contains_dependency_lines(self) -> None:
        md = generate_tasks_md_from_manifest(self._make_manifest(), "Test Feature")
        assert "WP01" in md  # WP02 depends on WP01

    def test_empty_deps_shows_none(self) -> None:
        md = generate_tasks_md_from_manifest(self._make_manifest(), "Test Feature")
        assert "None" in md  # WP01 has no deps

    def test_subtask_ids_present(self) -> None:
        md = generate_tasks_md_from_manifest(self._make_manifest(), "Test Feature")
        assert "T001" in md
        assert "T002" in md

    def test_has_generated_header_note(self) -> None:
        md = generate_tasks_md_from_manifest(self._make_manifest(), "Test Feature")
        assert "Generated by finalize-tasks" in md

    def test_feature_name_in_heading(self) -> None:
        md = generate_tasks_md_from_manifest(self._make_manifest(), "Test Feature")
        assert "Test Feature" in md

    def test_requirement_refs_present(self) -> None:
        md = generate_tasks_md_from_manifest(self._make_manifest(), "Test Feature")
        assert "FR-001" in md

    def test_wp_headings_present(self) -> None:
        md = generate_tasks_md_from_manifest(self._make_manifest(), "Test Feature")
        assert "## Work Package WP01" in md
        assert "## Work Package WP02" in md

    def test_prompt_file_shown_when_set(self) -> None:
        manifest = WpsManifest(
            work_packages=[
                WorkPackageEntry(
                    id="WP01",
                    title="With Prompt",
                    prompt_file="tasks/WP01-with-prompt.md",
                )
            ]
        )
        md = generate_tasks_md_from_manifest(manifest, "Feature")
        assert "tasks/WP01-with-prompt.md" in md

    @staticmethod
    def _deps_line(md: str, wp_id: str) -> str:
        section = md.split(f"## Work Package {wp_id}:")[1].split("---")[0]
        return next(line for line in section.splitlines() if line.startswith("**Dependencies**"))

    def test_resolved_dependencies_override_manifest_value(self) -> None:
        md = generate_tasks_md_from_manifest(self._make_manifest(), "F", resolved_dependencies={"WP01": ["WP00"]})
        assert self._deps_line(md, "WP01") == "**Dependencies**: WP00"

    def test_wp_absent_from_resolved_map_keeps_manifest_value(self) -> None:
        md = generate_tasks_md_from_manifest(self._make_manifest(), "F", resolved_dependencies={"WP01": ["WP00"]})
        assert self._deps_line(md, "WP02") == "**Dependencies**: WP01"

    def test_empty_resolved_list_renders_none(self) -> None:
        md = generate_tasks_md_from_manifest(self._make_manifest(), "F", resolved_dependencies={"WP02": []})
        assert self._deps_line(md, "WP02") == "**Dependencies**: None"

    def test_default_output_matches_empty_resolved_map(self) -> None:
        manifest = self._make_manifest()
        assert generate_tasks_md_from_manifest(manifest, "F") == generate_tasks_md_from_manifest(manifest, "F", resolved_dependencies={})


class TestPlanConcernRefs:
    """Tests for plan_concern_refs field (T005) and cross_cutting field (T006)."""

    def test_backwards_compat_no_fields(self) -> None:
        """Existing wps.yaml without new fields parses without error."""
        entry = WorkPackageEntry(id="WP01", title="test")
        assert entry.plan_concern_refs == []
        assert entry.cross_cutting is False

    def test_valid_plan_concern_refs(self) -> None:
        entry = WorkPackageEntry(id="WP01", title="test", plan_concern_refs=["IC-01", "IC-23"])
        assert entry.plan_concern_refs == ["IC-01", "IC-23"]

    def test_invalid_concern_ref_single_digit(self) -> None:
        """IC-1 is invalid — must be exactly two digits."""
        with pytest.raises(ValidationError):
            WorkPackageEntry(id="WP01", title="test", plan_concern_refs=["IC-1"])

    def test_invalid_concern_ref_wrong_prefix(self) -> None:
        """WP01 is not a valid IC-## ref."""
        with pytest.raises(ValidationError):
            WorkPackageEntry(id="WP01", title="test", plan_concern_refs=["WP01"])

    def test_invalid_concern_ref_three_digits(self) -> None:
        """IC-123 is invalid — must be exactly two digits."""
        with pytest.raises(ValidationError):
            WorkPackageEntry(id="WP01", title="test", plan_concern_refs=["IC-123"])

    def test_invalid_concern_ref_unicode_digits(self) -> None:
        """Arabic-Indic digits must not match — re.ASCII flag is required."""
        # "١٢" are Arabic-Indic '١٢' — must NOT pass the validator
        with pytest.raises(ValidationError):
            WorkPackageEntry(id="WP01", title="test", plan_concern_refs=["IC-١٢"])

    def test_cross_cutting_true(self) -> None:
        entry = WorkPackageEntry(id="WP01", title="test", cross_cutting=True)
        assert entry.cross_cutting is True

    def test_cross_cutting_default_false(self) -> None:
        entry = WorkPackageEntry(id="WP01", title="test")
        assert entry.cross_cutting is False

    def test_load_manifest_with_plan_concern_refs(self, tmp_path: Path) -> None:
        wps = tmp_path / "wps.yaml"
        wps.write_text(
            "work_packages:\n"
            "  - id: WP01\n"
            "    title: 'With concern refs'\n"
            "    plan_concern_refs: [IC-01, IC-03]\n",
            encoding="utf-8",
        )
        manifest = load_wps_manifest(tmp_path)
        assert manifest is not None
        assert manifest.work_packages[0].plan_concern_refs == ["IC-01", "IC-03"]

    def test_load_manifest_with_cross_cutting(self, tmp_path: Path) -> None:
        wps = tmp_path / "wps.yaml"
        wps.write_text(
            "work_packages:\n"
            "  - id: WP01\n"
            "    title: 'Cross-cutting'\n"
            "    cross_cutting: true\n",
            encoding="utf-8",
        )
        manifest = load_wps_manifest(tmp_path)
        assert manifest is not None
        assert manifest.work_packages[0].cross_cutting is True


class TestGenerateTasksMdPlanConcernRefs:
    """Tests for generate_tasks_md_from_manifest() rendering of plan_concern_refs (T007)."""

    def test_plan_concerns_rendered_when_non_empty(self) -> None:
        manifest = WpsManifest(
            work_packages=[
                WorkPackageEntry(
                    id="WP01",
                    title="With concerns",
                    plan_concern_refs=["IC-01", "IC-03"],
                )
            ]
        )
        md = generate_tasks_md_from_manifest(manifest, "Feature")
        assert "**Plan Concerns**: IC-01, IC-03" in md

    def test_plan_concerns_not_rendered_when_empty(self) -> None:
        manifest = WpsManifest(
            work_packages=[
                WorkPackageEntry(
                    id="WP01",
                    title="No concerns",
                )
            ]
        )
        md = generate_tasks_md_from_manifest(manifest, "Feature")
        assert "Plan Concerns" not in md

    def test_plan_concerns_appear_after_requirement_refs(self) -> None:
        manifest = WpsManifest(
            work_packages=[
                WorkPackageEntry(
                    id="WP01",
                    title="Ordered fields",
                    requirement_refs=["FR-001"],
                    plan_concern_refs=["IC-02"],
                )
            ]
        )
        md = generate_tasks_md_from_manifest(manifest, "Feature")
        req_pos = md.index("Requirement Refs")
        concern_pos = md.index("Plan Concerns")
        assert req_pos < concern_pos

    def test_multiple_wps_independent_concern_rendering(self) -> None:
        """WP01 has concerns; WP02 does not — both render correctly."""
        manifest = WpsManifest(
            work_packages=[
                WorkPackageEntry(
                    id="WP01",
                    title="Has concerns",
                    plan_concern_refs=["IC-01"],
                ),
                WorkPackageEntry(
                    id="WP02",
                    title="No concerns",
                ),
            ]
        )
        md = generate_tasks_md_from_manifest(manifest, "Feature")
        assert "**Plan Concerns**: IC-01" in md
        # Exactly one occurrence — not duplicated for WP02
        assert md.count("Plan Concerns") == 1
