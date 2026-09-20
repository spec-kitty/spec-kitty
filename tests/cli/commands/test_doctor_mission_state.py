"""Characterization tests for `spec-kitty doctor mission-state` (WP06 / T029).

Captures today's observable behavior across all three dispatch arms
(--audit / --fix / --teamspace-dry-run) and error paths before the refactor.
Tests must remain green through T030 typing fix and T031-T033 refactor commits.

Per tdd-red-green-refactor tactic: this commit is isolated from any refactor.
Per function-over-form-testing tactic: assertions on exit code and stdout/stderr
substrings; no assertions on internal call sequences.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

import specify_cli.cli.commands._mission_state_doctor as mission_state_mod
import specify_cli.cli.commands.doctor as doctor_mod
from specify_cli.cli.commands.doctor import app

pytestmark = [pytest.mark.integration]

runner = CliRunner()


# ---------------------------------------------------------------------------
# Fixtures — minimal mission directories for scan operations
# ---------------------------------------------------------------------------


def _make_clean_mission(parent: Path, slug: str = "test-mission") -> Path:
    """Create a minimal valid mission directory under parent."""
    mission_dir = parent / slug
    mission_dir.mkdir(parents=True, exist_ok=True)
    (mission_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_id": "01KQHRB8GCFJAX7HM4ZY52AQGR",
                "mission_slug": slug,
                "mission_type": "software-dev",
                "target_branch": "main",
            }
        ),
        encoding="utf-8",
    )
    return mission_dir


# ---------------------------------------------------------------------------
# Section A: Error cases (exit 2) — mode validation and flag conflicts
# ---------------------------------------------------------------------------


class TestModeValidationErrors:
    """Characterize error paths that exit 2 before any dispatch occurs."""

    def test_no_mode_flag_exits_0_with_help_hint(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Without --audit, --fix, or --teamspace-dry-run: exit 0, suggests flags.

        Arrange: minimal project root.
        Act: invoke mission-state with no mode flag.
        Assert: exit_code == 0, output mentions --audit.
        """
        monkeypatch.setattr(mission_state_mod, "locate_project_root", lambda: tmp_path)
        result = runner.invoke(app, ["mission-state"])
        assert result.exit_code == 0
        assert "--audit" in result.output

    def test_conflicting_audit_and_fix_exits_2(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """--audit and --fix together must exit 2 with an error message.

        Arrange: project root monkeypatched.
        Act: invoke mission-state --audit --fix.
        Assert: exit_code == 2, error message in output.
        """
        monkeypatch.setattr(mission_state_mod, "locate_project_root", lambda: tmp_path)
        result = runner.invoke(app, ["mission-state", "--audit", "--fix"])
        assert result.exit_code == 2
        combined = (result.output or "") + (result.stderr or "")
        assert "exactly one" in combined.lower() or "choose" in combined.lower()

    def test_conflicting_audit_and_teamspace_dry_run_exits_2(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """--audit and --teamspace-dry-run together must exit 2.

        Arrange: project root monkeypatched.
        Act: invoke mission-state --audit --teamspace-dry-run.
        Assert: exit_code == 2.
        """
        monkeypatch.setattr(mission_state_mod, "locate_project_root", lambda: tmp_path)
        result = runner.invoke(app, ["mission-state", "--audit", "--teamspace-dry-run"])
        assert result.exit_code == 2

    def test_conflicting_fix_and_teamspace_dry_run_exits_2(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """--fix and --teamspace-dry-run together must exit 2.

        Arrange: project root monkeypatched.
        Act: invoke mission-state --fix --teamspace-dry-run.
        Assert: exit_code == 2.
        """
        monkeypatch.setattr(mission_state_mod, "locate_project_root", lambda: tmp_path)
        result = runner.invoke(app, ["mission-state", "--fix", "--teamspace-dry-run"])
        assert result.exit_code == 2

    def test_invalid_fail_on_value_exits_2(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """An unrecognized --fail-on value exits 2 with the valid values listed.

        Arrange: project root monkeypatched.
        Act: invoke mission-state --audit --fail-on critical.
        Assert: exit_code == 2, 'teamspace-blocker' in error (valid values listed).
        """
        monkeypatch.setattr(mission_state_mod, "locate_project_root", lambda: tmp_path)
        result = runner.invoke(
            app,
            [
                "mission-state",
                "--audit",
                "--fail-on",
                "critical",
                "--fixture-dir",
                str(tmp_path),
            ],
        )
        assert result.exit_code == 2
        combined = (result.output or "") + (result.stderr or "")
        assert "teamspace-blocker" in combined

    def test_include_fixtures_and_fixture_dir_mutually_exclusive(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """--include-fixtures and --fixture-dir are mutually exclusive (exit 2).

        Arrange: project root monkeypatched, fixture dir present.
        Act: invoke mission-state --audit --include-fixtures --fixture-dir <dir>.
        Assert: exit_code == 2.
        """
        monkeypatch.setattr(mission_state_mod, "locate_project_root", lambda: tmp_path)
        fixture_dir = tmp_path / "fixtures"
        _make_clean_mission(fixture_dir)
        result = runner.invoke(
            app,
            [
                "mission-state",
                "--audit",
                "--include-fixtures",
                "--fixture-dir",
                str(fixture_dir),
            ],
        )
        assert result.exit_code == 2

    def test_missing_repo_root_exits_1(self) -> None:
        """When locate_project_root returns None and no fixture_dir, exit 1.

        Arrange: locate_project_root returns None (no project).
        Act: invoke mission-state --audit (no --fixture-dir).
        Assert: exit_code == 1.

        The ``mission-state`` command shell resolves the project root through
        the doctor shim's ``locate_project_root`` seam (#2059, mirrors the
        ``workspaces`` shell) and forwards it to ``run_mission_state``; patch
        that seam to drive the no-project path through the public surface.
        """
        import specify_cli.cli.commands.doctor as doctor_mod

        with patch.object(doctor_mod, "locate_project_root", return_value=None):
            result = runner.invoke(app, ["mission-state", "--audit"])
        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# Section B: --audit mode characterization
# ---------------------------------------------------------------------------


class TestAuditModeCharacterization:
    """Characterize the --audit dispatch arm.

    These supplement tests/audit/test_audit_cli.py which covers --audit
    comprehensively; this class focuses on the dispatch arm's entry/exit shape.
    """

    def test_audit_clean_fixture_exits_0(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """--audit on a clean mission exits 0.

        Arrange: one clean mission directory in fixture_dir.
        Act: invoke mission-state --audit --fixture-dir <dir>.
        Assert: exit_code == 0.
        """
        fixture_dir = tmp_path / "fixtures"
        _make_clean_mission(fixture_dir)
        monkeypatch.setattr(mission_state_mod, "locate_project_root", lambda: tmp_path)
        result = runner.invoke(app, ["mission-state", "--audit", "--fixture-dir", str(fixture_dir)])
        assert result.exit_code == 0

    def test_audit_json_output_has_missions_key(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """--audit --json output is valid JSON with 'missions' key.

        Arrange: one clean mission directory.
        Act: invoke mission-state --audit --json --fixture-dir <dir>.
        Assert: exit_code == 0, JSON output contains 'missions'.
        """
        fixture_dir = tmp_path / "fixtures"
        _make_clean_mission(fixture_dir)
        monkeypatch.setattr(mission_state_mod, "locate_project_root", lambda: tmp_path)
        result = runner.invoke(
            app,
            ["mission-state", "--audit", "--json", "--fixture-dir", str(fixture_dir)],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "missions" in data
        assert "repo_summary" in data


# ---------------------------------------------------------------------------
# Section C: --fix mode characterization
# ---------------------------------------------------------------------------


class TestFixModeCharacterization:
    """Characterize the --fix dispatch arm using a mocked repair_repo."""

    def _build_repair_report(self, *, with_error: bool = False) -> MagicMock:
        """Build a RepairReport mock carrying realistic per-mission detail.

        Always includes a *normalized* mission (``status='updated'`` with a
        non-empty ``meta_actions``) so the per-mission rendering path is
        exercised without forcing a non-zero exit. When ``with_error`` is set an
        additional *errored* mission (``status='error'`` with
        ``validation_errors``) is appended — its presence flips the command exit
        to 1 (WP02 T008: errored + normalized rendered together).
        """
        normalized = MagicMock()
        normalized.status = "updated"
        normalized.mission_slug = "normalized-mission"
        normalized.validation_errors = []
        normalized.meta_actions = ["normalized_change_mode:regular"]

        missions = [normalized]
        missions_json: list[dict[str, object]] = [
            {
                "mission_slug": "normalized-mission",
                "status": "updated",
                "validation_errors": [],
                "meta_actions": ["normalized_change_mode:regular"],
            }
        ]
        error_count = 0
        if with_error:
            errored = MagicMock()
            errored.status = "error"
            errored.mission_slug = "errored-mission"
            errored.validation_errors = ["Invalid canonical meta.json"]
            errored.meta_actions = []
            missions.append(errored)
            missions_json.append(
                {
                    "mission_slug": "errored-mission",
                    "status": "error",
                    "validation_errors": ["Invalid canonical meta.json"],
                    "meta_actions": [],
                }
            )
            error_count = 1

        summary = {
            "missions_updated": 1,
            "missions_unchanged": 0,
            "missions_error": error_count,
        }
        report = MagicMock()
        report.to_json.return_value = json.dumps(
            {
                "run_id": "test-run",
                "missions": missions_json,
                "summary": summary,
            }
        )
        report.to_dict.return_value = {"summary": summary}
        report.missions = missions
        report.manifest_path = ".kittify/migrations/mission-state/test-run.json"
        return report

    def test_fix_mode_json_output_exits_0_on_success(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """--fix --json exits 0 when repair_repo succeeds with no errors.

        Arrange: mocked repair_repo returning a successful RepairReport.
        Act: invoke mission-state --fix --json.
        Assert: exit_code == 0, JSON output is parseable.
        """
        monkeypatch.setattr(doctor_mod, "locate_project_root", lambda: tmp_path)
        report_mock = self._build_repair_report()

        with patch(
            "specify_cli.migration.mission_state.repair_repo",
            return_value=report_mock,
        ):
            result = runner.invoke(
                app,
                ["mission-state", "--fix", "--json", "--allow-dirty"],
            )

        assert result.exit_code == 0, result.output
        # Output must be parseable JSON
        data = json.loads(result.output)
        assert "run_id" in data or "missions" in data or "summary" in data

    def test_fix_mode_pretty_output_shows_summary(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """--fix (no --json) shows summary AND per-mission normalized detail.

        Arrange: mocked repair_repo returning a report with a normalized
        mission (``meta_actions``).
        Act: invoke mission-state --fix.
        Assert: exit_code == 0, summary line present, and the normalized
        mission's slug + action rendered per-mission (WP02 T013, FR-005).
        """
        monkeypatch.setattr(doctor_mod, "locate_project_root", lambda: tmp_path)
        report_mock = self._build_repair_report()

        with patch(
            "specify_cli.migration.mission_state.repair_repo",
            return_value=report_mock,
        ):
            result = runner.invoke(
                app,
                ["mission-state", "--fix", "--allow-dirty"],
            )

        assert result.exit_code == 0, result.output
        combined = (result.output or "") + (result.stderr or "")
        assert "repair" in combined.lower() or "updated" in combined.lower()
        # Per-mission detail, not just the summary counts.
        assert "normalized-mission" in combined
        assert "normalized_change_mode:regular" in combined

    def test_fix_mode_pretty_output_shows_per_mission_detail(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """--fix terminal names each errored AND normalized mission + reason.

        Arrange: mocked repair_repo returning a report with an errored mission
        AND a normalized mission (``meta_actions=['normalized_change_mode:regular']``).
        Act: invoke mission-state --fix (no --json).
        Assert: exit_code == 1 (errored mission present) and the terminal
        renders each mission's slug + reason/actions, not just counts
        (WP02 T008, FR-005).
        """
        monkeypatch.setattr(doctor_mod, "locate_project_root", lambda: tmp_path)
        report_mock = self._build_repair_report(with_error=True)

        with patch(
            "specify_cli.migration.mission_state.repair_repo",
            return_value=report_mock,
        ):
            result = runner.invoke(
                app,
                ["mission-state", "--fix", "--allow-dirty"],
            )

        assert result.exit_code == 1, result.output
        combined = (result.output or "") + (result.stderr or "")
        # Errored mission: slug + validation reason.
        assert "errored-mission" in combined
        assert "Invalid canonical meta.json" in combined
        # Normalized mission: slug + recorded action.
        assert "normalized-mission" in combined
        assert "normalized_change_mode:regular" in combined

    def test_fix_mode_json_carries_per_mission_meta_actions(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """--fix --json carries a per-mission record incl. meta_actions.

        Arrange: mocked repair_repo returning a normalized + errored report.
        Act: invoke mission-state --fix --json.
        Assert: JSON missions[] carry mission_slug, validation_errors, and
        meta_actions — full triage detail obtainable from stdout with no
        gitignored `.kittify/migrations/` read (WP02 T012, FR-006/NFR-003).
        """
        monkeypatch.setattr(doctor_mod, "locate_project_root", lambda: tmp_path)
        report_mock = self._build_repair_report(with_error=True)

        with patch(
            "specify_cli.migration.mission_state.repair_repo",
            return_value=report_mock,
        ):
            result = runner.invoke(
                app,
                ["mission-state", "--fix", "--json", "--allow-dirty"],
            )

        data = json.loads(result.output)
        slugs = {m["mission_slug"] for m in data["missions"]}
        assert {"normalized-mission", "errored-mission"} <= slugs
        by_slug = {m["mission_slug"]: m for m in data["missions"]}
        assert by_slug["normalized-mission"]["meta_actions"] == ["normalized_change_mode:regular"]
        assert by_slug["errored-mission"]["validation_errors"] == ["Invalid canonical meta.json"]
        # NFR-003: triage detail lives in the payload, not only in the sidecar.
        assert "normalized_change_mode:regular" in result.output
        assert "Invalid canonical meta.json" in result.output

    def test_fix_mode_exits_1_on_repair_error(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """--fix exits 1 when repair_repo raises MissionStateRepairError.

        Arrange: mocked repair_repo raising MissionStateRepairError.
        Act: invoke mission-state --fix --json.
        Assert: exit_code == 1, error info in output.
        """
        monkeypatch.setattr(doctor_mod, "locate_project_root", lambda: tmp_path)

        from specify_cli.migration.mission_state import MissionStateRepairError

        with patch(
            "specify_cli.migration.mission_state.repair_repo",
            side_effect=MissionStateRepairError("No mission directories found"),
        ):
            result = runner.invoke(
                app,
                ["mission-state", "--fix", "--json", "--allow-dirty"],
            )

        assert result.exit_code == 1
        combined = (result.output or "") + (result.stderr or "")
        assert "MISSION_STATE_REPAIR_FAILED" in combined or "error" in combined.lower()

    def test_fix_mode_exits_1_when_missions_have_errors(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """--fix exits 1 when any MissionRepairResult.status == 'error'.

        Arrange: mocked repair_repo returning a report with one error result.
        Act: invoke mission-state --fix --json.
        Assert: exit_code == 1.
        """
        monkeypatch.setattr(mission_state_mod, "locate_project_root", lambda: tmp_path)

        error_result = MagicMock()
        error_result.status = "error"

        report = MagicMock()
        report.to_json.return_value = json.dumps({"run_id": "test", "missions": []})
        report.to_dict.return_value = {
            "summary": {
                "missions_updated": 0,
                "missions_unchanged": 0,
                "missions_error": 1,
            }
        }
        report.missions = [error_result]
        report.manifest_path = ".kittify/migrations/mission-state/test.json"

        with patch(
            "specify_cli.migration.mission_state.repair_repo",
            return_value=report,
        ):
            result = runner.invoke(
                app,
                ["mission-state", "--fix", "--json", "--allow-dirty"],
            )

        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# Section D: --teamspace-dry-run mode characterization
# ---------------------------------------------------------------------------


class TestTeamspaceDryRunModeCharacterization:
    """Characterize the --teamspace-dry-run dispatch arm using a mocked runner."""

    def _build_dry_run_report(self, *, valid: bool = True) -> MagicMock:
        """Build a TeamspaceDryRunReport mock with realistic per-error records.

        The invalid report carries a structured ``errors[]`` list shaped like
        the real dry-run blockers (``mission_slug``/``artifact_path``/
        ``line_number``/``error``/``message``) so the per-mission rendering and
        JSON parity paths are exercised (WP02 T013).
        """
        errors: list[dict[str, object]] = (
            []
            if valid
            else [
                {
                    "mission_slug": "blocked-mission",
                    "artifact_path": "kitty-specs/blocked-mission/status.events.jsonl",
                    "line_number": 7,
                    "error": "STATUS_ROW_NOT_REPAIRED",
                    "message": "row remains; run --fix",
                }
            ]
        )
        report = MagicMock()
        report.to_json.return_value = json.dumps(
            {
                "valid": valid,
                "envelope_count": 3 if valid else 0,
                "errors": errors,
                "events_package_version": "0.1.0",
            }
        )
        report.valid = valid
        report.envelope_count = 3 if valid else 0
        report.errors = errors
        report.events_package_version = "0.1.0"
        return report

    def test_teamspace_dry_run_json_exits_0_on_success(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """--teamspace-dry-run --json exits 0 when validation passes.

        Arrange: mocked teamspace_dry_run returning a valid report.
        Act: invoke mission-state --teamspace-dry-run --json.
        Assert: exit_code == 0, JSON output is parseable.
        """
        monkeypatch.setattr(mission_state_mod, "locate_project_root", lambda: tmp_path)
        report_mock = self._build_dry_run_report(valid=True)

        with patch(
            "specify_cli.migration.mission_state.teamspace_dry_run",
            return_value=report_mock,
        ):
            result = runner.invoke(
                app,
                ["mission-state", "--teamspace-dry-run", "--json"],
            )

        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert "valid" in data

    def test_teamspace_dry_run_pretty_shows_valid_message(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """--teamspace-dry-run (no --json) shows 'valid' when validation passes.

        Arrange: mocked teamspace_dry_run returning a valid report.
        Act: invoke mission-state --teamspace-dry-run.
        Assert: exit_code == 0, 'valid' in output.
        """
        monkeypatch.setattr(mission_state_mod, "locate_project_root", lambda: tmp_path)
        report_mock = self._build_dry_run_report(valid=True)

        with patch(
            "specify_cli.migration.mission_state.teamspace_dry_run",
            return_value=report_mock,
        ):
            result = runner.invoke(
                app,
                ["mission-state", "--teamspace-dry-run"],
            )

        assert result.exit_code == 0, result.output
        combined = (result.output or "") + (result.stderr or "")
        assert "valid" in combined.lower()

    def test_teamspace_dry_run_exits_1_on_validation_failure(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """--teamspace-dry-run exits 1 AND renders per-mission detail on failure.

        Arrange: mocked teamspace_dry_run returning an invalid report with a
        structured per-error record.
        Act: invoke mission-state --teamspace-dry-run.
        Assert: exit_code stays 1 (refusal semantics untouched, C-006) and the
        terminal names the affected mission + reason, not just the count
        (WP02 T013, FR-007).
        """
        monkeypatch.setattr(mission_state_mod, "locate_project_root", lambda: tmp_path)
        report_mock = self._build_dry_run_report(valid=False)

        with patch(
            "specify_cli.migration.mission_state.teamspace_dry_run",
            return_value=report_mock,
        ):
            result = runner.invoke(
                app,
                ["mission-state", "--teamspace-dry-run"],
            )

        assert result.exit_code == 1
        combined = (result.output or "") + (result.stderr or "")
        assert "blocked-mission" in combined
        assert "STATUS_ROW_NOT_REPAIRED" in combined

    def test_teamspace_dry_run_pretty_shows_per_mission_detail(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """--teamspace-dry-run terminal names each affected mission + reason.

        Arrange: mocked teamspace_dry_run returning an invalid report whose
        ``errors[]`` use the ``line`` key variant.
        Act: invoke mission-state --teamspace-dry-run.
        Assert: each per-mission line (slug / error code / message) renders,
        not only the count header (WP02 T010, FR-007).
        """
        monkeypatch.setattr(mission_state_mod, "locate_project_root", lambda: tmp_path)
        errors = [
            {
                "mission_slug": "blocked-mission",
                "artifact_path": "kitty-specs/blocked-mission/status.events.jsonl",
                "line": 7,
                "error": "STATUS_ROW_NOT_REPAIRED",
                "message": "row remains; run --fix",
            },
        ]
        report_mock = MagicMock()
        report_mock.valid = False
        report_mock.envelope_count = 0
        report_mock.errors = errors
        report_mock.events_package_version = "0.1.0"
        report_mock.to_json.return_value = json.dumps({"valid": False, "errors": errors})

        with patch(
            "specify_cli.migration.mission_state.teamspace_dry_run",
            return_value=report_mock,
        ):
            result = runner.invoke(
                app,
                ["mission-state", "--teamspace-dry-run"],
            )

        assert result.exit_code == 1
        combined = (result.output or "") + (result.stderr or "")
        assert "blocked-mission" in combined
        assert "STATUS_ROW_NOT_REPAIRED" in combined
        assert "row remains; run --fix" in combined

    def test_teamspace_dry_run_json_carries_per_mission_errors(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """--teamspace-dry-run --json emits structured per-mission errors[].

        Arrange: mocked teamspace_dry_run returning an invalid report.
        Act: invoke mission-state --teamspace-dry-run --json.
        Assert: errors[] carry mission_slug/artifact_path/error/message —
        shape-equivalent to the repair report's records (WP02 T012, FR-008
        parity); triage detail is obtainable from stdout (NFR-003).
        """
        monkeypatch.setattr(mission_state_mod, "locate_project_root", lambda: tmp_path)
        report_mock = self._build_dry_run_report(valid=False)

        with patch(
            "specify_cli.migration.mission_state.teamspace_dry_run",
            return_value=report_mock,
        ):
            result = runner.invoke(
                app,
                ["mission-state", "--teamspace-dry-run", "--json"],
            )

        assert result.exit_code == 1
        data = json.loads(result.output)
        assert data["errors"], "per-mission errors[] must be present in --json"
        entry = data["errors"][0]
        assert entry["mission_slug"] == "blocked-mission"
        assert entry["error"] == "STATUS_ROW_NOT_REPAIRED"
        assert "message" in entry and "artifact_path" in entry

    def test_teamspace_dry_run_exits_1_on_error(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """--teamspace-dry-run exits 1 when teamspace_dry_run raises.

        Arrange: mocked teamspace_dry_run raising MissionStateDryRunError.
        Act: invoke mission-state --teamspace-dry-run --json.
        Assert: exit_code == 1, error info in output.
        """
        monkeypatch.setattr(mission_state_mod, "locate_project_root", lambda: tmp_path)

        from specify_cli.migration.mission_state import MissionStateDryRunError

        with patch(
            "specify_cli.migration.mission_state.teamspace_dry_run",
            side_effect=MissionStateDryRunError("Cannot proceed"),
        ):
            result = runner.invoke(
                app,
                ["mission-state", "--teamspace-dry-run", "--json"],
            )

        assert result.exit_code == 1
        combined = (result.output or "") + (result.stderr or "")
        assert "TEAMSPACE_DRY_RUN_FAILED" in combined or "error" in combined.lower()
