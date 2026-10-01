"""Unit tests for finalize-tasks with wps.yaml (FR-006, FR-007, FR-011, FR-012).

Tests that wps.yaml acts as the tier-0 dependency source, bypassing the prose
parser when present, and that tasks.md is regenerated from the manifest.
"""

from __future__ import annotations

from pathlib import Path
from contextlib import AbstractContextManager
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.agent.mission import app
from specify_cli.coordination.commit_router import CommitRouterResult

pytestmark = pytest.mark.fast

runner = CliRunner()

_FAKE_SHA = "b" * 40


def _committed_router_result() -> CommitRouterResult:
    """The committed CommitRouterResult the planning-commit seam returns.

    WP02/#2056 de-god re-routed ``_commit_to_branch`` through the canonical
    ``commit_for_mission`` seam, so tests mock that seam (not the retired
    ``mission.safe_commit`` shim, which is no longer on the call path).
    """
    return CommitRouterResult(status="committed", placement_ref="main", commit_hash=_FAKE_SHA)


def _status_patch(git_status_out: str = "M tasks.md") -> AbstractContextManager[MagicMock]:
    """Patch the finalize commit-candidate dirtiness probe (real git is out of scope for these mocks)."""
    return patch(
        "specify_cli.cli.commands.agent.mission_finalize._finalize_candidates_dirty",
        return_value=bool(git_status_out.strip()),
    )


def _make_run_command(git_status_out: str = "M tasks.md"):
    """Return a side-effect for run_command that handles git calls."""

    def _side_effect(cmd, **kwargs):  # noqa: ANN001
        if "status" in cmd and "--porcelain" in cmd:
            return (0, git_status_out, "")
        if "rev-parse" in cmd and "HEAD" in cmd:
            return (0, _FAKE_SHA, "")
        if "branch" in cmd or "checkout" in cmd or "current-branch" in cmd:
            return (0, "main", "")
        return (0, "", "")

    return _side_effect


def _build_feature_with_wps_yaml(
    tmp_path: Path,
    wps_yaml_content: str,
    tasks_md_content: str = "",
    extra_wp_files: dict[str, str] | None = None,
) -> Path:
    """Create a minimal feature dir with wps.yaml and optional tasks.md.

    Returns feature_dir.
    """
    feature_dir = tmp_path / "kitty-specs" / "069-test"
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text('{"target_branch": "main"}\n', encoding="utf-8")

    # Minimal spec.md with a functional requirement
    (feature_dir / "spec.md").write_text(
        "# Spec\n"
        "## Functional Requirements\n"
        "| ID | Requirement | Acceptance Criteria | Status |\n"
        "| --- | --- | --- | --- |\n"
        "| FR-001 | Test requirement | Covered by WP01. | proposed |\n",
        encoding="utf-8",
    )

    (feature_dir / "wps.yaml").write_text(wps_yaml_content, encoding="utf-8")

    if tasks_md_content:
        (feature_dir / "tasks.md").write_text(tasks_md_content, encoding="utf-8")

    # Default WP01 prompt file
    wp_file = tasks_dir / "WP01-test.md"
    wp_file.write_text(
        "---\n"
        "work_package_id: WP01\n"
        "title: Test\n"
        "dependencies: []\n"
        "requirement_refs: [FR-001]\n"
        "subtasks: []\n"
        "owned_files:\n"
        "  - src/module_a/**\n"
        "authoritative_surface: src/module_a/\n"
        "execution_mode: code_change\n"
        "---\n"
        "# WP01\n",
        encoding="utf-8",
    )

    # Additional WP files if requested
    if extra_wp_files:
        for filename, content in extra_wp_files.items():
            (tasks_dir / filename).write_text(content, encoding="utf-8")

    return feature_dir


def _invoke_finalize_tasks(
    tmp_path: Path,
    feature_dir: Path,
    git_status_out: str = "M tasks.md",
    extra_args: list[str] | None = None,
) -> object:
    """Invoke finalize-tasks with all infrastructure helpers patched.

    Returns the typer CliRunner result.
    """
    args = ["finalize-tasks", "--mission", "069-test", "--json"]
    if extra_args:
        args.extend(extra_args)

    with (
        patch(
            "specify_cli.cli.commands.agent.mission.locate_project_root",
            return_value=tmp_path,
        ),
        patch(
            "specify_cli.cli.commands.agent.mission._find_feature_directory",
            return_value=feature_dir,
        ),
        patch(
            "specify_cli.cli.commands.agent.mission._show_branch_context",
            return_value=(None, "main"),
        ),
        patch(
            "specify_cli.coordination.commit_router.commit_for_mission",
            return_value=_committed_router_result(),
        ),
        patch(
            "specify_cli.cli.commands.agent.mission.run_command",
            side_effect=_make_run_command(git_status_out),
        ),
        _status_patch(git_status_out),
    ):
        return runner.invoke(app, args)


class TestFinalizTasksWithWpsYaml:
    """Tests for wps.yaml tier-0 integration in finalize-tasks (FR-006, FR-007, FR-011, FR-012)."""

    def test_wps_yaml_deps_used_not_prose(self, tmp_path: Path) -> None:
        """FR-006: wps.yaml dependencies take precedence over tasks.md prose.

        wps.yaml declares WP01 with dependencies: [] (explicit empty).
        tasks.md has misleading prose "Depends on WP02, WP03".
        After finalize-tasks, WP01 frontmatter must have no deps.
        """
        wps_yaml = (
            "work_packages:\n"
            "  - id: WP01\n"
            "    title: Test\n"
            "    dependencies: []\n"
            "    requirement_refs: [FR-001]\n"
        )
        # tasks.md has a misleading prose dependency reference — should be IGNORED
        misleading_tasks_md = (
            "## Work Package WP01: Test\n"
            "**Requirement Refs**: FR-001\n"
            "Depends on WP02, WP03\n"
        )
        feature_dir = _build_feature_with_wps_yaml(tmp_path, wps_yaml, misleading_tasks_md)

        result = _invoke_finalize_tasks(tmp_path, feature_dir)

        assert result.exit_code == 0, f"Exit code {result.exit_code}: {result.stdout}"

        # WP01 frontmatter should have no deps despite prose saying WP02, WP03
        wp_file = feature_dir / "tasks" / "WP01-test.md"
        content = wp_file.read_text(encoding="utf-8")

        # Find the dependencies line in frontmatter (between first --- and second ---)
        fm_section = content.split("---")[1]
        deps_line = next(
            (line for line in fm_section.splitlines() if "dependencies" in line), ""
        )
        # Should not contain WP02 or WP03
        assert "WP02" not in deps_line, (
            f"WP02 should not appear in dependencies (prose parser bypassed), got: {deps_line!r}"
        )
        assert "WP03" not in deps_line, (
            f"WP03 should not appear in dependencies (prose parser bypassed), got: {deps_line!r}"
        )

    def test_explicit_empty_deps_not_overwritten(self, tmp_path: Path) -> None:
        """FR-007: dependencies: [] in wps.yaml is authoritative, not overwritten by preserve-existing.

        Scenario: WP01 frontmatter has [WP02] (from a previous finalize run).
        wps.yaml says dependencies: [].
        After finalize-tasks, WP01 frontmatter must have [] — not [WP02].
        """
        wps_yaml = (
            "work_packages:\n"
            "  - id: WP01\n"
            "    title: Test\n"
            "    dependencies: []\n"
            "    requirement_refs: [FR-001]\n"
        )
        # No tasks.md — wps.yaml is sole source
        feature_dir = _build_feature_with_wps_yaml(tmp_path, wps_yaml)

        # Override WP01 frontmatter to have an existing dependency [WP02]
        wp_file = feature_dir / "tasks" / "WP01-test.md"
        wp_file.write_text(
            "---\n"
            "work_package_id: WP01\n"
            "title: Test\n"
            "dependencies:\n"
            "  - WP02\n"
            "requirement_refs: [FR-001]\n"
            "subtasks: []\n"
            "owned_files:\n"
            "  - src/module_a/**\n"
            "authoritative_surface: src/module_a/\n"
            "execution_mode: code_change\n"
            "---\n"
            "# WP01\n",
            encoding="utf-8",
        )

        result = _invoke_finalize_tasks(tmp_path, feature_dir)

        assert result.exit_code == 0, f"Exit code {result.exit_code}: {result.stdout}"

        # WP01 frontmatter should not contain WP02 after finalize
        updated_content = wp_file.read_text(encoding="utf-8")
        fm_section = updated_content.split("---")[1]
        # Extract full frontmatter as a blob and check WP02 is gone
        assert "WP02" not in fm_section, (
            f"WP02 should be removed when wps.yaml declares dependencies: [], "
            f"but found it in frontmatter:\n{fm_section}"
        )

    def test_tasks_md_regenerated_from_manifest(self, tmp_path: Path) -> None:
        """FR-011: finalize-tasks regenerates tasks.md when wps.yaml is present.

        Old tasks.md content is replaced by manifest-generated content
        that includes the WP title and the 'Generated by finalize-tasks' marker.
        """
        wps_yaml = (
            "work_packages:\n"
            "  - id: WP01\n"
            "    title: My First WP\n"
            "    dependencies: []\n"
            "    requirement_refs: [FR-001]\n"
        )
        old_tasks_md = "# Old content that should be overwritten entirely\n"
        feature_dir = _build_feature_with_wps_yaml(tmp_path, wps_yaml, old_tasks_md)

        result = _invoke_finalize_tasks(tmp_path, feature_dir)

        assert result.exit_code == 0, f"Exit code {result.exit_code}: {result.stdout}"

        new_tasks_md = (feature_dir / "tasks.md").read_text(encoding="utf-8")
        assert "Old content" not in new_tasks_md, (
            "Old tasks.md content should have been replaced by manifest-generated content"
        )
        assert "My First WP" in new_tasks_md, (
            "Regenerated tasks.md should contain the WP title from wps.yaml"
        )
        assert "Generated by finalize-tasks" in new_tasks_md, (
            "Regenerated tasks.md should contain the 'Generated by finalize-tasks' marker"
        )

    def test_no_wps_yaml_uses_prose_parser(self, tmp_path: Path) -> None:
        """FR-012: Missions without wps.yaml use prose parser (backward compat).

        When no wps.yaml is present, the tasks.md prose parser runs and
        populates WP01 frontmatter with WP02 as a dependency.
        """
        feature_dir = tmp_path / "kitty-specs" / "069-test"
        tasks_dir = feature_dir / "tasks"
        tasks_dir.mkdir(parents=True)
        (feature_dir / "meta.json").write_text('{"target_branch": "main"}\n', encoding="utf-8")

        # Minimal spec.md
        (feature_dir / "spec.md").write_text(
            "# Spec\n"
            "## Functional Requirements\n"
            "| ID | Requirement | Acceptance Criteria | Status |\n"
            "| --- | --- | --- | --- |\n"
            "| FR-001 | Test requirement | Covered by WP01. | proposed |\n"
            "| FR-002 | Test requirement 2 | Covered by WP02. | proposed |\n",
            encoding="utf-8",
        )

        # tasks.md with prose dependency (no wps.yaml)
        tasks_md = (
            "## Work Package WP01: Test\n"
            "**Requirement Refs**: FR-001\n"
            "Depends on WP02\n"
            "\n"
            "## Work Package WP02: Foundation\n"
            "**Requirement Refs**: FR-002\n"
        )
        (feature_dir / "tasks.md").write_text(tasks_md, encoding="utf-8")

        # WP01 prompt file — no existing dependencies
        (tasks_dir / "WP01-test.md").write_text(
            "---\n"
            "work_package_id: WP01\n"
            "title: Test\n"
            "requirement_refs: [FR-001]\n"
            "subtasks: []\n"
            "owned_files:\n"
            "  - src/module_a/**\n"
            "authoritative_surface: src/module_a/\n"
            "execution_mode: code_change\n"
            "---\n"
            "# WP01\n",
            encoding="utf-8",
        )

        # WP02 prompt file
        (tasks_dir / "WP02-test.md").write_text(
            "---\n"
            "work_package_id: WP02\n"
            "title: Foundation\n"
            "requirement_refs: [FR-002]\n"
            "subtasks: []\n"
            "owned_files:\n"
            "  - src/module_b/**\n"
            "authoritative_surface: src/module_b/\n"
            "execution_mode: code_change\n"
            "---\n"
            "# WP02\n",
            encoding="utf-8",
        )

        with (
            patch(
                "specify_cli.cli.commands.agent.mission.locate_project_root",
                return_value=tmp_path,
            ),
            patch(
                "specify_cli.cli.commands.agent.mission._find_feature_directory",
                return_value=feature_dir,
            ),
            patch(
                "specify_cli.cli.commands.agent.mission._show_branch_context",
                return_value=(None, "main"),
            ),
            patch(
                "specify_cli.coordination.commit_router.commit_for_mission",
                return_value=_committed_router_result(),
            ),
            patch(
                "specify_cli.cli.commands.agent.mission.run_command",
                side_effect=_make_run_command("M tasks.md"),
            ),
            _status_patch("M tasks.md"),
        ):
            result = runner.invoke(
                app, ["finalize-tasks", "--mission", "069-test", "--json"]
            )

        assert result.exit_code == 0, f"Exit code {result.exit_code}: {result.stdout}"

        # WP01 should have WP02 in its dependencies (from prose parser)
        wp1_content = (tasks_dir / "WP01-test.md").read_text(encoding="utf-8")
        fm_section = wp1_content.split("---")[1]
        assert "WP02" in fm_section, (
            f"WP02 should be in WP01 dependencies when parsed from tasks.md prose "
            f"(no wps.yaml), but frontmatter was:\n{fm_section}"
        )
