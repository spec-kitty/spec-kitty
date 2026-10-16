"""Unit tests for finalize-tasks with wps.yaml (FR-006, FR-007, FR-011, FR-012).

Tests that wps.yaml acts as the tier-0 dependency source, bypassing the prose
parser when present, and that tasks.md is regenerated from the manifest.
"""

from __future__ import annotations

import json
from pathlib import Path
from contextlib import AbstractContextManager
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.agent.mission import app
from specify_cli.cli.commands.agent import mission_finalize
from specify_cli.coordination.commit_router import CommitRouterResult
from specify_cli.core.dependency_graph import dependency_readiness_for_wp
from specify_cli.core.wps_manifest import generate_tasks_md_from_manifest, load_wps_manifest
from specify_cli.status.wp_metadata import read_wp_frontmatter

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

    def test_outline_validates_manifest_refs_before_wp_prompts_exist(self, tmp_path: Path) -> None:
        feature_dir = _build_feature_with_wps_yaml(
            tmp_path,
            "work_packages:\n  - id: WP01\n    title: Test\n    dependencies: []\n    requirement_refs: [FR-001]\n",
        )
        (feature_dir / "tasks" / "WP01-test.md").unlink()

        result = _invoke_finalize_tasks(tmp_path, feature_dir, extra_args=["--validate-only"])

        assert result.exit_code == 0, result.stdout
        assert '"validation_stage": "tasks-outline"' in result.stdout
        assert '"WP01": ["FR-001"]' in result.stdout

    def test_outline_rejects_unmapped_manifest_refs(self, tmp_path: Path) -> None:
        feature_dir = _build_feature_with_wps_yaml(
            tmp_path,
            "work_packages:\n  - id: WP01\n    title: Test\n    dependencies: []\n    requirement_refs: []\n",
        )
        (feature_dir / "tasks" / "WP01-test.md").unlink()

        result = _invoke_finalize_tasks(tmp_path, feature_dir, extra_args=["--validate-only"])

        assert result.exit_code == 1
        assert '"missing_requirement_refs_wps": ["WP01"]' in result.stdout
        assert '"unmapped_functional_requirements": ["FR-001"]' in result.stdout

    def test_finalization_requires_wp_prompts(self, tmp_path: Path) -> None:
        feature_dir = _build_feature_with_wps_yaml(
            tmp_path,
            "work_packages:\n  - id: WP01\n    title: Test\n    dependencies: []\n    requirement_refs: [FR-001]\n",
        )
        (feature_dir / "tasks" / "WP01-test.md").unlink()

        result = _invoke_finalize_tasks(tmp_path, feature_dir)

        assert result.exit_code == 1
        assert "WP prompt files are required to finalize tasks" in result.stdout

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


# ---------------------------------------------------------------------------
# #5448: wps.yaml that leaves a WP's dependencies out must not erase the WP file's
# ---------------------------------------------------------------------------


def _wp_file(n: int, deps: str) -> str:
    """Return a minimal WP prompt file whose frontmatter ``dependencies`` is ``deps``."""
    return (
        "---\n"
        f"work_package_id: WP0{n}\n"
        f"title: Test {n}\n"
        f"dependencies: {deps}\n"
        "requirement_refs: [FR-001]\n"
        "subtasks: []\n"
        "owned_files:\n"
        f"  - src/m{n}/**\n"
        f"authoritative_surface: src/m{n}/\n"
        "execution_mode: code_change\n"
        "---\n"
        f"# WP0{n}\n"
    )


def _wp03_manifest_lines(variant: str) -> str:
    """Return the WP03 manifest row for ``variant`` (empty string for ``no_entry``)."""
    head = "  - id: WP03\n    title: Test 3\n"
    tail = "    requirement_refs: [FR-001]\n"
    middle = {
        "absent": "",
        "depends_on": "    depends_on: [WP02]\n",
        "no_entry": None,
        "explicit_agree": "    dependencies: [WP02]\n",
        "explicit_disagree": "    dependencies: [WP01]\n",
    }[variant]
    return "" if middle is None else head + middle + tail


def _build_three_wp_feature(tmp_path: Path, variant: str) -> Path:
    """WP01 [] <- WP02 [WP01] <- WP03 [WP02] in the files; WP03's manifest row follows ``variant``."""
    wps_yaml = (
        "work_packages:\n"
        "  - id: WP01\n    title: Test 1\n    dependencies: []\n    requirement_refs: [FR-001]\n"
        "  - id: WP02\n    title: Test 2\n    dependencies: [WP01]\n    requirement_refs: [FR-001]\n"
    ) + _wp03_manifest_lines(variant)
    return _build_feature_with_wps_yaml(
        tmp_path,
        wps_yaml,
        extra_wp_files={
            "WP02-test.md": _wp_file(2, "[WP01]"),
            "WP03-test.md": _wp_file(3, "[WP02]"),
        },
    )


def _report(result: object) -> dict[str, object]:
    out = result.stdout  # type: ignore[attr-defined]
    return json.loads(out[out.find("{") :])


def _wp03_deps_after(feature_dir: Path) -> list[str]:
    meta, _ = read_wp_frontmatter(feature_dir / "tasks" / "WP03-test.md")
    return list(meta.dependencies)


def _lane_of(feature_dir: Path, wp_id: str) -> dict[str, object]:
    lanes = json.loads((feature_dir / "lanes.json").read_text(encoding="utf-8"))["lanes"]
    return next(lane for lane in lanes if wp_id in lane["wp_ids"])


_ABSENT_ARMS = ["absent", "depends_on", "no_entry"]


class TestFinalizeKeepsFrontmatterDepsWhenManifestOmitsThem:
    """#5448: an absent/misspelled ``dependencies`` key or a missing entry falls back to the WP file.

    The explicit-``[]`` control is ``test_explicit_empty_deps_not_overwritten`` above.
    """

    @pytest.mark.parametrize("variant", _ABSENT_ARMS)
    def test_absent_key_keeps_frontmatter_dependencies(self, tmp_path: Path, variant: str) -> None:
        """Issue #5448 (arms: absent key, ``depends_on`` typo, no entry): WP03 keeps ``[WP02]``."""
        feature_dir = _build_three_wp_feature(tmp_path, variant)

        result = _invoke_finalize_tasks(tmp_path, feature_dir)

        assert result.exit_code == 0, result.stdout
        deps = _wp03_deps_after(feature_dir)
        assert deps == ["WP02"]
        wp02_lane = _lane_of(feature_dir, "WP02")
        wp03_lane = _lane_of(feature_dir, "WP03")
        assert wp02_lane["lane_id"] in wp03_lane["depends_on_lanes"]
        assert _report(result)["dependencies_parsed"]["WP03"] == ["WP02"]  # type: ignore[index]
        readiness = dependency_readiness_for_wp("WP03", deps, {"WP01": "planned", "WP02": "planned", "WP03": "planned"})
        assert readiness.satisfied is False
        assert "WP02" in readiness.unsatisfied

    def test_absent_key_tasks_md_lists_resolved_dependencies(self, tmp_path: Path) -> None:
        """Issue #5448: the regenerated tasks.md prints the resolved dependencies, not "None"."""
        feature_dir = _build_three_wp_feature(tmp_path, "absent")

        result = _invoke_finalize_tasks(tmp_path, feature_dir)

        assert result.exit_code == 0, result.stdout
        section = (feature_dir / "tasks.md").read_text(encoding="utf-8").split("## Work Package WP03")[1]
        assert "**Dependencies**: WP02" in section

    @pytest.mark.parametrize("variant", _ABSENT_ARMS)
    def test_validate_only_previews_resolved_dependencies(self, tmp_path: Path, variant: str) -> None:
        """Issue #5448: ``--validate-only`` no longer plans to erase WP03's dependencies, and writes nothing."""
        feature_dir = _build_three_wp_feature(tmp_path, variant)
        wp03 = feature_dir / "tasks" / "WP03-test.md"
        before = wp03.read_bytes()

        result = _invoke_finalize_tasks(tmp_path, feature_dir, extra_args=["--validate-only"])

        assert result.exit_code == 0, result.stdout
        entry = next(e for e in _report(result)["would_modify"] if e["wp_id"] == "WP03")  # type: ignore[attr-defined,union-attr]
        assert "dependencies" not in entry["changes"]
        assert wp03.read_bytes() == before

    def test_validate_only_tasks_md_staleness_uses_resolved_dependencies(self, tmp_path: Path) -> None:
        """Issue #5448: staleness is judged against the resolved (not manifest-only) dependencies."""
        feature_dir = _build_three_wp_feature(tmp_path, "absent")
        manifest = load_wps_manifest(feature_dir)
        assert manifest is not None
        rendered = generate_tasks_md_from_manifest(manifest, "069-test")
        head, sep, tail = rendered.partition("## Work Package WP03")
        assert sep
        assert tail.count("**Dependencies**: None") == 1
        (feature_dir / "tasks.md").write_text(head + sep + tail.replace("**Dependencies**: None", "**Dependencies**: WP02"), encoding="utf-8")

        result = _invoke_finalize_tasks(tmp_path, feature_dir, extra_args=["--validate-only"])

        assert result.exit_code == 0, result.stdout
        assert _report(result)["tasks_md_stale"] is False

    def test_explicit_agreeing_key_is_kept(self, tmp_path: Path) -> None:
        """Control: an explicit manifest key that agrees with the WP file stays as is."""
        feature_dir = _build_three_wp_feature(tmp_path, "explicit_agree")

        result = _invoke_finalize_tasks(tmp_path, feature_dir)

        assert result.exit_code == 0, result.stdout
        assert _wp03_deps_after(feature_dir) == ["WP02"]
        assert _lane_of(feature_dir, "WP02")["lane_id"] in _lane_of(feature_dir, "WP03")["depends_on_lanes"]

    def test_explicit_disagreeing_key_is_refused(self, tmp_path: Path) -> None:
        """Control: two disagreeing non-empty values still refuse."""
        feature_dir = _build_three_wp_feature(tmp_path, "explicit_disagree")

        result = _invoke_finalize_tasks(tmp_path, feature_dir)

        assert result.exit_code != 0
        assert "Dependency disagreement" in result.stdout


class TestFrontmatterFallbackDependencies:
    """Focused cases for ``_frontmatter_fallback_dependencies`` (#5448)."""

    @staticmethod
    def _write(tmp_path: Path, name: str, content: str) -> Path:
        path = tmp_path / name
        path.write_text(content, encoding="utf-8")
        return path

    def test_re_exported_from_mission_finalize(self) -> None:
        from specify_cli.cli.commands.agent import mission_finalize_validation

        assert (
            mission_finalize._frontmatter_fallback_dependencies
            is mission_finalize_validation._frontmatter_fallback_dependencies
        )

    def test_non_empty_frontmatter_is_returned(self, tmp_path: Path) -> None:
        wp = self._write(tmp_path, "WP03-x.md", _wp_file(3, "[WP02]"))
        assert mission_finalize._frontmatter_fallback_dependencies([wp], set()) == {"WP03": ["WP02"]}

    def test_explicit_id_is_skipped_even_with_non_empty_frontmatter(self, tmp_path: Path) -> None:
        wp = self._write(tmp_path, "WP03-x.md", _wp_file(3, "[WP02]"))
        assert mission_finalize._frontmatter_fallback_dependencies([wp], {"WP03"}) == {}

    def test_empty_frontmatter_is_not_in_map(self, tmp_path: Path) -> None:
        wp = self._write(tmp_path, "WP03-x.md", _wp_file(3, "[]"))
        assert mission_finalize._frontmatter_fallback_dependencies([wp], set()) == {}

    @pytest.mark.parametrize(
        "bad_content",
        [
            pytest.param(b"---\nwork_package_id: [unclosed\n---\n", id="bad-yaml"),
            pytest.param(b"---\nwork_package_id: WP02\ntitle: x\ndependencies:\n  a: b\n---\n", id="invalid-metadata"),
            pytest.param(b"---\nwork_package_id: WP02\ntitle: \xff\xfe\n---\n", id="non-utf8"),
        ],
    )
    def test_unreadable_file_is_skipped_without_raising(self, tmp_path: Path, bad_content: bytes) -> None:
        bad = tmp_path / "WP02-x.md"
        bad.write_bytes(bad_content)
        good = self._write(tmp_path, "WP03-x.md", _wp_file(3, "[WP02]"))
        assert mission_finalize._frontmatter_fallback_dependencies([bad, good], set()) == {"WP03": ["WP02"]}

    def test_os_error_on_read_is_skipped_without_raising(self, tmp_path: Path) -> None:
        not_a_file = tmp_path / "WP02-x.md"
        not_a_file.mkdir()
        good = self._write(tmp_path, "WP03-x.md", _wp_file(3, "[WP02]"))
        assert mission_finalize._frontmatter_fallback_dependencies([not_a_file, good], set()) == {"WP03": ["WP02"]}

    def test_non_wp_filename_is_ignored(self, tmp_path: Path) -> None:
        other = self._write(tmp_path, "notes.md", _wp_file(3, "[WP02]"))
        assert mission_finalize._frontmatter_fallback_dependencies([other], set()) == {}
