"""Unit tests for finalize-tasks JSON output schema.

Extracted from tests/legacy/integration/test_finalize_tasks_json_output.py.
The legacy tests were integration-level (real git repos + subprocess); these
replicate the same behavioural contracts as fast unit tests using mock patches.

Covers:
- commit_hash is 40-char hex when a commit is created
- commit_created is True on first run, False on idempotent second run
- files_committed includes tasks.md and WP file paths
- all 6 required JSON fields are present and correctly typed

WP01 additions (T009):
- test_json_reports_modified_unchanged_preserved: three categories in JSON output
"""

from __future__ import annotations

from pathlib import Path
from contextlib import AbstractContextManager
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.agent import mission_finalize
from specify_cli.cli.commands.agent.mission import app
from specify_cli.coordination.commit_router import CommitRouterResult

pytestmark = pytest.mark.fast

runner = CliRunner()

_FAKE_SHA = "a" * 40


def _committed_router_result(*, commit_success: bool = True) -> CommitRouterResult:
    """Build the CommitRouterResult the planning-commit seam returns.

    WP02/#2056 de-god re-routed ``_commit_to_branch`` through the canonical
    ``commit_for_mission`` seam, so tests mock that seam (not the retired
    ``mission.safe_commit`` shim, which is no longer on the call path).
    """
    if commit_success:
        return CommitRouterResult(
            status="committed",
            placement_ref="main",
            commit_hash=_FAKE_SHA,
            commit_hashes=(("main", _FAKE_SHA),),
        )
    return CommitRouterResult(
        status="error", placement_ref="main", diagnostic="safe_commit: git commit failed"
    )


_FAKE_COORD_SHA = "b" * 40
_COORD_BRANCH = "kitty/mission-001-test-A1B2C3D4"


def _committed_router_result_coord_split() -> CommitRouterResult:
    """Build the split-commit CommitRouterResult a coord-topology finalize returns.

    #2549 facet B: under coord topology, ``commit_for_mission`` issues TWO
    commits -- one for primary-partition artifacts (tasks.md, lanes.json,
    tasks/WP*) landing on the feature branch, one for placement-partition
    artifacts (status.events.jsonl, status.json, acceptance-matrix.json,
    issue-matrix.md) landing on the coordination branch. The legacy single
    ``commit_hash`` still names the feature-branch commit (the caller
    partition); ``commit_hashes`` carries BOTH.
    """
    return CommitRouterResult(
        status="committed",
        placement_ref="main",
        commit_hash=_FAKE_SHA,
        commit_hashes=(("main", _FAKE_SHA), (_COORD_BRANCH, _FAKE_COORD_SHA)),
    )


def _build_feature(tmp_path: Path) -> tuple[Path, Path]:
    """Create a minimal feature + WP structure under tmp_path.

    Returns (feature_dir, tasks_dir).
    """
    feature_dir = tmp_path / "kitty-specs" / "001-test"
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
    (feature_dir / "tasks.md").write_text(
        "## Work Package WP01\n**Requirement Refs**: FR-001\n\n## Work Package WP02\n**Requirement Refs**: FR-001\n",
        encoding="utf-8",
    )
    # Give each WP distinct owned_files to avoid ownership overlap validation errors
    wp_data = {
        "WP01": ("src/module_a/**", "src/module_a/"),
        "WP02": ("src/module_b/**", "src/module_b/"),
    }
    for wp_id in ("WP01", "WP02"):
        owned_file, auth_surface = wp_data[wp_id]
        (tasks_dir / f"{wp_id}-test.md").write_text(
            f"---\n"
            f"work_package_id: {wp_id}\n"
            f"execution_mode: code_change\n"
            f"owned_files:\n  - {owned_file}\n"
            f"authoritative_surface: {auth_surface}\n"
            f"---\n\n# {wp_id}\n",
            encoding="utf-8",
        )
    return feature_dir, tasks_dir


def _patch_context(
    tmp_path: Path, feature_dir: Path, *, commit_success: bool = True, git_status_out: str = "M tasks.md"
):
    """Return a context-manager stack that patches the infrastructure helpers."""
    return (
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
            return_value=_committed_router_result(commit_success=commit_success),
        ),
        patch(
            "specify_cli.cli.commands.agent.mission.run_command",
            side_effect=_make_run_command(git_status_out),
        ),
        _status_patch(git_status_out),
    )


def _status_patch(git_status_out: str = "M tasks.md") -> AbstractContextManager[MagicMock]:
    """Patch the finalize commit-candidate dirtiness probe (real git is out of scope for these mocks)."""
    return patch(
        "specify_cli.cli.commands.agent.mission_finalize._finalize_candidates_dirty",
        return_value=bool(git_status_out.strip()),
    )


def _make_run_command(git_status_out: str):
    """Return a side-effect for run_command that:
    - Returns git_status_out for 'git status --porcelain' calls
    - Returns the fake SHA for 'git rev-parse HEAD' calls
    """

    def _side_effect(cmd, **kwargs):  # noqa: ANN001
        if "status" in cmd and "--porcelain" in cmd:
            return (0, git_status_out, "")
        if "rev-parse" in cmd and "HEAD" in cmd:
            return (0, _FAKE_SHA, "")
        return (0, "", "")

    return _side_effect


class TestFinalizeTasks:
    """Unit tests for finalize-tasks JSON output schema."""

    def test_missing_meta_warning_is_suppressed_in_json_mode(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Missing-meta diagnostics must not precede the JSON payload."""
        feature_dir, _ = _build_feature(tmp_path)
        (feature_dir / "meta.json").unlink()

        mission_finalize._warn_missing_meta(feature_dir, None, json_output=True)

        captured = capsys.readouterr()
        assert captured.out == ""
        assert captured.err == ""

    def test_missing_meta_warning_still_emits_in_human_mode(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Human mode keeps the operator-facing missing-meta warning."""
        feature_dir, _ = _build_feature(tmp_path)
        (feature_dir / "meta.json").unlink()

        mission_finalize._warn_missing_meta(feature_dir, None, json_output=False)

        assert "meta.json missing" in capsys.readouterr().out

    def test_json_output_commit_hash_is_40_char_hex(self, tmp_path: Path) -> None:
        """commit_hash in JSON output should be a 40-character hex SHA."""
        # Arrange
        feature_dir, _ = _build_feature(tmp_path)

        # Assumption check
        assert (feature_dir / "tasks.md").exists()

        # Act
        with (
            patch("specify_cli.cli.commands.agent.mission.locate_project_root", return_value=tmp_path),
            patch("specify_cli.cli.commands.agent.mission._find_feature_directory", return_value=feature_dir),
            patch("specify_cli.cli.commands.agent.mission._show_branch_context", return_value=(None, "main")),
            patch(
                "specify_cli.coordination.commit_router.commit_for_mission",
                return_value=_committed_router_result(),
            ),
            patch("specify_cli.cli.commands.agent.mission.run_command", side_effect=_make_run_command("M tasks.md")),
            _status_patch("M tasks.md"),
        ):
            result = runner.invoke(app, ["finalize-tasks", "--json"])

        # Assert
        assert result.exit_code == 0, result.stdout
        import json

        lines = [l for l in result.stdout.splitlines() if l.strip().startswith("{")]
        payload = json.loads(lines[-1])
        assert "commit_hash" in payload
        commit_hash = payload["commit_hash"]
        assert commit_hash is not None
        assert len(commit_hash) == 40, f"Expected 40-char SHA, got: {commit_hash!r}"
        assert all(c in "0123456789abcdef" for c in commit_hash), (
            f"commit_hash should be lowercase hex, got: {commit_hash!r}"
        )

    def test_json_output_commit_created_true_when_changes_exist(self, tmp_path: Path) -> None:
        """commit_created should be True when relevant files have changes to commit."""
        # Arrange
        feature_dir, _ = _build_feature(tmp_path)

        # Assumption check
        assert (feature_dir / "tasks.md").exists()

        # Act
        with (
            patch("specify_cli.cli.commands.agent.mission.locate_project_root", return_value=tmp_path),
            patch("specify_cli.cli.commands.agent.mission._find_feature_directory", return_value=feature_dir),
            patch("specify_cli.cli.commands.agent.mission._show_branch_context", return_value=(None, "main")),
            patch(
                "specify_cli.coordination.commit_router.commit_for_mission",
                return_value=_committed_router_result(),
            ),
            patch("specify_cli.cli.commands.agent.mission.run_command", side_effect=_make_run_command("M tasks.md")),
            _status_patch("M tasks.md"),
        ):
            result = runner.invoke(app, ["finalize-tasks", "--json"])

        # Assert
        assert result.exit_code == 0, result.stdout
        import json

        lines = [l for l in result.stdout.splitlines() if l.strip().startswith("{")]
        payload = json.loads(lines[-1])
        assert payload["commit_created"] is True
        assert isinstance(payload["commit_created"], bool)

    def test_json_output_commit_created_false_when_nothing_to_commit(self, tmp_path: Path) -> None:
        """commit_created should be False when git status reports no relevant changes."""
        # Arrange
        feature_dir, _ = _build_feature(tmp_path)

        # Assumption check
        assert (feature_dir / "tasks.md").exists()

        # Act — git status returns empty output (nothing to commit)
        with (
            patch("specify_cli.cli.commands.agent.mission.locate_project_root", return_value=tmp_path),
            patch("specify_cli.cli.commands.agent.mission._find_feature_directory", return_value=feature_dir),
            patch("specify_cli.cli.commands.agent.mission._show_branch_context", return_value=(None, "main")),
            patch(
                "specify_cli.coordination.commit_router.commit_for_mission",
                return_value=_committed_router_result(),
            ),
            patch("specify_cli.cli.commands.agent.mission.run_command", side_effect=_make_run_command("")),
            _status_patch(""),
        ):
            result = runner.invoke(app, ["finalize-tasks", "--json"])

        # Assert
        assert result.exit_code == 0, result.stdout
        import json

        lines = [l for l in result.stdout.splitlines() if l.strip().startswith("{")]
        payload = json.loads(lines[-1])
        assert payload["commit_created"] is False

    def test_json_output_files_committed_includes_tasks_and_wp_files(self, tmp_path: Path) -> None:
        """files_committed should list tasks.md and all WP file paths."""
        # Arrange
        feature_dir, _ = _build_feature(tmp_path)

        # Assumption check
        assert (feature_dir / "tasks" / "WP01-test.md").exists()
        assert (feature_dir / "tasks" / "WP02-test.md").exists()

        # Act
        with (
            patch("specify_cli.cli.commands.agent.mission.locate_project_root", return_value=tmp_path),
            patch("specify_cli.cli.commands.agent.mission._find_feature_directory", return_value=feature_dir),
            patch("specify_cli.cli.commands.agent.mission._show_branch_context", return_value=(None, "main")),
            patch(
                "specify_cli.coordination.commit_router.commit_for_mission",
                return_value=_committed_router_result(),
            ),
            patch("specify_cli.cli.commands.agent.mission.run_command", side_effect=_make_run_command("M tasks.md")),
            _status_patch("M tasks.md"),
        ):
            result = runner.invoke(app, ["finalize-tasks", "--json"])

        # Assert
        assert result.exit_code == 0, result.stdout
        import json

        lines = [l for l in result.stdout.splitlines() if l.strip().startswith("{")]
        payload = json.loads(lines[-1])
        assert isinstance(payload["files_committed"], list)
        files = payload["files_committed"]
        assert any("tasks.md" in f for f in files), f"tasks.md not found in {files}"
        assert any("WP01" in f for f in files), f"WP01 not found in {files}"
        assert any("WP02" in f for f in files), f"WP02 not found in {files}"

    def test_json_output_schema_has_all_required_fields(self, tmp_path: Path) -> None:
        """All 6 required JSON fields must be present with correct types."""
        # Arrange
        feature_dir, tasks_dir = _build_feature(tmp_path)
        required_fields = [
            "result",
            "commit_created",
            "commit_hash",
            "files_committed",
            "updated_wp_count",
            "tasks_dir",
        ]

        # Assumption check
        assert (feature_dir / "spec.md").exists()

        # Act
        with (
            patch("specify_cli.cli.commands.agent.mission.locate_project_root", return_value=tmp_path),
            patch("specify_cli.cli.commands.agent.mission._find_feature_directory", return_value=feature_dir),
            patch("specify_cli.cli.commands.agent.mission._show_branch_context", return_value=(None, "main")),
            patch(
                "specify_cli.coordination.commit_router.commit_for_mission",
                return_value=_committed_router_result(),
            ),
            patch("specify_cli.cli.commands.agent.mission.run_command", side_effect=_make_run_command("M tasks.md")),
            _status_patch("M tasks.md"),
        ):
            result = runner.invoke(app, ["finalize-tasks", "--json"])

        # Assert
        assert result.exit_code == 0, result.stdout
        import json

        lines = [l for l in result.stdout.splitlines() if l.strip().startswith("{")]
        payload = json.loads(lines[-1])
        for field in required_fields:
            assert field in payload, f"Missing required field: {field!r}"
        assert isinstance(payload["result"], str)
        assert isinstance(payload["commit_created"], bool)
        assert isinstance(payload["commit_hash"], (str, type(None)))
        assert isinstance(payload["files_committed"], list)
        assert isinstance(payload["updated_wp_count"], int)
        assert isinstance(payload["tasks_dir"], str)

    def test_json_output_commit_hashes_reports_both_branches_under_coord_topology(
        self, tmp_path: Path
    ) -> None:
        """#2549 facet B: under coord topology, JSON reports BOTH commit hashes.

        A coord-topology finalize issues two commits (feature branch + coord
        branch) as separate commits on separate branches. Pre-fix, the JSON
        payload named only the feature-branch ``commit_hash`` while
        ``files_committed`` listed files from BOTH partitions -- misleading
        automated callers. This pins the fix: the new ``commit_hashes`` field
        carries an entry per branch, and the coord-branch hash is present and
        genuinely differs from the feature-branch hash.
        """
        feature_dir, _ = _build_feature(tmp_path)

        with (
            patch("specify_cli.cli.commands.agent.mission.locate_project_root", return_value=tmp_path),
            patch("specify_cli.cli.commands.agent.mission._find_feature_directory", return_value=feature_dir),
            patch("specify_cli.cli.commands.agent.mission._show_branch_context", return_value=(None, "main")),
            patch(
                "specify_cli.coordination.commit_router.commit_for_mission",
                return_value=_committed_router_result_coord_split(),
            ),
            patch("specify_cli.cli.commands.agent.mission.run_command", side_effect=_make_run_command("M tasks.md")),
            _status_patch("M tasks.md"),
        ):
            result = runner.invoke(app, ["finalize-tasks", "--json"])

        assert result.exit_code == 0, result.stdout
        import json as _json

        lines = [l for l in result.stdout.splitlines() if l.strip().startswith("{")]
        payload = _json.loads(lines[-1])

        # Backward-compatible single-value field still names the feature-branch commit.
        assert payload["commit_hash"] == _FAKE_SHA

        assert "commit_hashes" in payload, "JSON must include commit_hashes"
        commit_hashes = payload["commit_hashes"]
        assert isinstance(commit_hashes, list)
        assert len(commit_hashes) == 2, f"expected 2 branch commits, got {commit_hashes!r}"

        hashes_by_branch = {entry["branch"]: entry["hash"] for entry in commit_hashes}
        assert hashes_by_branch["main"] == _FAKE_SHA
        assert hashes_by_branch[_COORD_BRANCH] == _FAKE_COORD_SHA
        assert hashes_by_branch[_COORD_BRANCH] is not None
        assert hashes_by_branch[_COORD_BRANCH] != hashes_by_branch["main"], (
            "the coordination-branch commit hash must be reported and must "
            "differ from the feature-branch commit hash"
        )

    def test_json_output_commit_hashes_single_entry_for_flat_topology(self, tmp_path: Path) -> None:
        """#2549 facet B backward compat: a flat/single_branch finalize reports one hash.

        A flat/single_branch mission has no coordination partition -- everything
        commits in one commit on one branch. ``commit_hashes`` must carry exactly
        that one ``{branch, hash}`` entry, matching the legacy ``commit_hash``
        field, so existing single-commit callers see no behavioural change.
        """
        feature_dir, _ = _build_feature(tmp_path)

        with (
            patch("specify_cli.cli.commands.agent.mission.locate_project_root", return_value=tmp_path),
            patch("specify_cli.cli.commands.agent.mission._find_feature_directory", return_value=feature_dir),
            patch("specify_cli.cli.commands.agent.mission._show_branch_context", return_value=(None, "main")),
            patch(
                "specify_cli.coordination.commit_router.commit_for_mission",
                return_value=_committed_router_result(),
            ),
            patch("specify_cli.cli.commands.agent.mission.run_command", side_effect=_make_run_command("M tasks.md")),
            _status_patch("M tasks.md"),
        ):
            result = runner.invoke(app, ["finalize-tasks", "--json"])

        assert result.exit_code == 0, result.stdout
        import json as _json

        lines = [l for l in result.stdout.splitlines() if l.strip().startswith("{")]
        payload = _json.loads(lines[-1])

        commit_hashes = payload["commit_hashes"]
        assert isinstance(commit_hashes, list)
        assert commit_hashes == [{"branch": "main", "hash": _FAKE_SHA}], (
            f"flat topology must report exactly one branch commit, got {commit_hashes!r}"
        )
        assert payload["commit_hash"] == commit_hashes[0]["hash"]

    def test_json_reports_modified_unchanged_preserved(self, tmp_path: Path) -> None:
        """Success JSON output must include modified_wps, unchanged_wps, preserved_wps (T008/T009)."""
        # Arrange
        feature_dir, _ = _build_feature(tmp_path)

        # Act
        with (
            patch("specify_cli.cli.commands.agent.mission.locate_project_root", return_value=tmp_path),
            patch("specify_cli.cli.commands.agent.mission._find_feature_directory", return_value=feature_dir),
            patch("specify_cli.cli.commands.agent.mission._show_branch_context", return_value=(None, "main")),
            patch(
                "specify_cli.coordination.commit_router.commit_for_mission",
                return_value=_committed_router_result(),
            ),
            patch("specify_cli.cli.commands.agent.mission.run_command", side_effect=_make_run_command("M tasks.md")),
            _status_patch("M tasks.md"),
        ):
            result = runner.invoke(app, ["finalize-tasks", "--json"])

        # Assert
        assert result.exit_code == 0, result.stdout
        import json as _json

        lines = [l for l in result.stdout.splitlines() if l.strip().startswith("{")]
        payload = _json.loads(lines[-1])
        assert payload.get("result") == "success"
        assert "modified_wps" in payload, "JSON must include modified_wps"
        assert "unchanged_wps" in payload, "JSON must include unchanged_wps"
        assert "preserved_wps" in payload, "JSON must include preserved_wps"
        assert isinstance(payload["modified_wps"], list)
        assert isinstance(payload["unchanged_wps"], list)
        assert isinstance(payload["preserved_wps"], list)
