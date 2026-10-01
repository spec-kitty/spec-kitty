"""``finalize-tasks --validate-only`` never rewrites a tracked tasks.md (#3221).

The T017 regeneration (``tasks.md`` rewritten from ``wps.yaml``) used to run
unconditionally — including in ``--validate-only`` mode — bypassing the INV-6
``pending_writes`` queue that ``_assert_no_write_in_validate_only`` guards.
The rewrite was idempotent on a consistent tree, so it was only observable
when ``tasks.md`` was stale: a command advertised as a read-only pre-flight
silently erased the staleness it was asked to check.

Contract (mirrors the reproduction in spec-kitty#3221): GIVEN a mission with
``wps.yaml`` and a stale ``tasks.md``, WHEN ``finalize-tasks --validate-only``
runs, THEN ``tasks.md`` is byte-identical afterwards AND the JSON report
carries ``tasks_md_stale: true``. The commit-phase run (no
``--validate-only``) still regenerates ``tasks.md``.
"""

from __future__ import annotations

import json
from pathlib import Path
from contextlib import AbstractContextManager
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.agent.mission import app
from specify_cli.coordination.commit_router import CommitRouterResult
from specify_cli.core.wps_manifest import (
    generate_tasks_md_from_manifest,
    load_wps_manifest,
)

pytestmark = pytest.mark.fast

runner = CliRunner()

_FAKE_SHA = "b" * 40
_MISSION = "069-tasks-md-readonly"

_WPS_YAML = "work_packages:\n  - id: WP01\n    title: Test\n    dependencies: []\n    requirement_refs: [FR-001]\n"


def _status_patch(git_status_out: str = "M tasks.md") -> AbstractContextManager[MagicMock]:
    """Patch the finalize commit-candidate dirtiness probe (real git is out of scope for these mocks)."""
    return patch(
        "specify_cli.cli.commands.agent.mission_finalize._finalize_candidates_dirty",
        return_value=bool(git_status_out.strip()),
    )


def _run_command(git_status_out: str = "M tasks.md"):  # noqa: ANN202
    def _side_effect(cmd, **kwargs):  # noqa: ANN001, ANN003
        if "status" in cmd and "--porcelain" in cmd:
            return (0, git_status_out, "")
        if "rev-parse" in cmd and "HEAD" in cmd:
            return (0, _FAKE_SHA, "")
        if "branch" in cmd or "checkout" in cmd or "current-branch" in cmd:
            return (0, "main", "")
        return (0, "", "")

    return _side_effect


def _build_feature(tmp_path: Path, tasks_md_content: str | None) -> Path:
    """Mission dir with wps.yaml + spec.md + WP01 file + optional tasks.md."""
    feature_dir = tmp_path / "kitty-specs" / _MISSION
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text('{"target_branch": "main"}\n', encoding="utf-8")
    (feature_dir / "spec.md").write_text(
        "# Spec\n"
        "## Functional Requirements\n"
        "| ID | Requirement | Acceptance Criteria | Status |\n"
        "| --- | --- | --- | --- |\n"
        "| FR-001 | Test requirement | Covered by WP01. | proposed |\n",
        encoding="utf-8",
    )
    (feature_dir / "wps.yaml").write_text(_WPS_YAML, encoding="utf-8")
    if tasks_md_content is not None:
        (feature_dir / "tasks.md").write_text(tasks_md_content, encoding="utf-8")
    (tasks_dir / "WP01-test.md").write_text(
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
    return feature_dir


def _invoke(tmp_path: Path, feature_dir: Path, *extra_args: str) -> object:
    args = ["finalize-tasks", "--mission", _MISSION, "--json", *extra_args]
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
            return_value=CommitRouterResult(status="committed", placement_ref="main", commit_hash=_FAKE_SHA),
        ),
        patch(
            "specify_cli.cli.commands.agent.mission.run_command",
            side_effect=_run_command(),
        ),
        _status_patch(),
    ):
        return runner.invoke(app, args)


def _payload(result: object) -> dict[str, object]:
    for line in result.output.splitlines():  # type: ignore[attr-defined]
        stripped = line.strip()
        if stripped.startswith("{"):
            return dict(json.loads(stripped))
    raise ValueError(f"No JSON object in finalize-tasks output:\n{result.output}")  # type: ignore[attr-defined]


def _generated(feature_dir: Path) -> str:
    manifest = load_wps_manifest(feature_dir)
    assert manifest is not None
    return generate_tasks_md_from_manifest(manifest, _MISSION)


class TestValidateOnlyNeverRewritesTasksMd:
    def test_stale_tasks_md_is_byte_identical_after_validate_only(self, tmp_path: Path) -> None:
        feature_dir = _build_feature(
            tmp_path,
            "# Tasks\n\n## Work Package WP01\n\n<!-- deliberate staleness probe -->\n",
        )
        tasks_md = feature_dir / "tasks.md"
        before = tasks_md.read_bytes()

        result = _invoke(tmp_path, feature_dir, "--validate-only")

        assert result.exit_code == 0, f"exit {result.exit_code}: {result.output}"
        assert tasks_md.read_bytes() == before, "--validate-only REWROTE a tracked tasks.md (INV-6 / #3221 violated): the staleness probe marker is gone"
        assert _payload(result)["tasks_md_stale"] is True

    def test_fresh_tasks_md_is_byte_identical_and_not_stale(self, tmp_path: Path) -> None:
        feature_dir = _build_feature(tmp_path, None)
        tasks_md = feature_dir / "tasks.md"
        fresh = _generated(feature_dir)
        tasks_md.write_text(fresh, encoding="utf-8")

        result = _invoke(tmp_path, feature_dir, "--validate-only")

        assert result.exit_code == 0, f"exit {result.exit_code}: {result.output}"
        assert tasks_md.read_text(encoding="utf-8") == fresh
        assert _payload(result)["tasks_md_stale"] is False

    def test_missing_tasks_md_is_not_created_by_validate_only(self, tmp_path: Path) -> None:
        feature_dir = _build_feature(tmp_path, None)
        tasks_md = feature_dir / "tasks.md"

        result = _invoke(tmp_path, feature_dir, "--validate-only")

        assert result.exit_code == 0, f"exit {result.exit_code}: {result.output}"
        assert not tasks_md.exists(), "--validate-only CREATED tasks.md (INV-6 / #3221 violated)"
        assert _payload(result)["tasks_md_stale"] is True

    def test_commit_phase_run_still_regenerates_tasks_md(self, tmp_path: Path) -> None:
        feature_dir = _build_feature(tmp_path, "stale hand-edited tasks.md\n")
        tasks_md = feature_dir / "tasks.md"

        result = _invoke(tmp_path, feature_dir)

        assert result.exit_code == 0, f"exit {result.exit_code}: {result.output}"
        assert tasks_md.read_text(encoding="utf-8") == _generated(feature_dir), (
            "the commit-phase run must still regenerate tasks.md (#3221 changed validate-only behavior only)"
        )

    def test_staleness_is_reported_on_the_console(self, tmp_path: Path) -> None:
        """Non-JSON mode: the skipped regeneration surfaces as a diagnostic."""
        feature_dir = _build_feature(
            tmp_path,
            "# Tasks\n\n## Work Package WP01\n\n<!-- deliberate staleness probe -->\n",
        )
        tasks_md = feature_dir / "tasks.md"
        before = tasks_md.read_bytes()

        args = ["finalize-tasks", "--mission", _MISSION, "--validate-only"]
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
                "specify_cli.cli.commands.agent.mission.run_command",
                side_effect=_run_command(),
            ),
            _status_patch(),
        ):
            result = runner.invoke(app, args)

        assert result.exit_code == 0, f"exit {result.exit_code}: {result.output}"
        assert tasks_md.read_bytes() == before
        assert "stale relative to wps.yaml" in result.output, f"staleness diagnostic missing from console output:\n{result.output}"
