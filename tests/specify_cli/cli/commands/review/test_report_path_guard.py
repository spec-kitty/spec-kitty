"""#7753: ``spec-kitty review`` owns only its own machine report.

Unit coverage of the report-path guard in ``review/_report.py`` plus the
CLI-level rerun contract: a previous machine report (either generation of its
frontmatter) is still refreshed, anything else is refused and left untouched.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import typer
from rich.console import Console
from typer.testing import CliRunner

from specify_cli.cli.commands.review import _report
from specify_cli.cli.commands.review._report import (
    AGENT_REVIEW_FILENAME,
    REASON_NOT_MACHINE_REPORT,
    REASON_NOT_REGULAR_FILE,
    REASON_SYMLINK,
    REASON_UNREADABLE,
    REPORT_GENERATOR,
    REVIEW_REPORT_FILENAME,
    ReportPathOccupiedError,
    ensure_report_path_writable,
    is_machine_review_report,
    refuse_occupied_report_path,
)
from tests.specify_cli.cli.commands._review_fixtures import (
    MISSION_SLUG,
    build_cli_app,
    make_mock_resolved,
    setup_fixture,
)

pytestmark = [pytest.mark.fast, pytest.mark.non_sandbox]

# Frontmatter of the current machine report (WP03 added gates_recorded etc.).
_CURRENT_MACHINE_REPORT = """---
verdict: fail
mode: post-merge
reviewed_at: 2026-11-18T23:02:30.312448+00:00
findings: 99
gates_recorded:
  - id: gate_1
    name: wp_lane_check
    command: spec-kitty review
    exit_code: 1
    result: fail
issue_matrix_present: not_applicable
mission_exception_present: not_applicable
---

## Findings

- **wp_not_done** `WP09`: lane is `planned`
"""

# Frontmatter of the earliest machine reports still committed in kitty-specs/.
_LEGACY_MACHINE_REPORT = """---
verdict: pass_with_notes
reviewed_at: 2026-05-01T10:00:00+00:00
findings: 99
---

## Findings
"""

_AGENT_REPORT = "# Mission Review Report: some-mission\n\n**Reviewer**: claude\n"


class TestIsMachineReviewReport:
    @pytest.mark.parametrize("text", [_CURRENT_MACHINE_REPORT, _LEGACY_MACHINE_REPORT])
    def test_both_machine_report_generations_are_recognised(self, text: str) -> None:
        assert is_machine_review_report(text)

    @pytest.mark.parametrize(
        "text",
        [
            pytest.param(_AGENT_REPORT, id="no-frontmatter"),
            pytest.param("", id="empty"),
            pytest.param("---\nverdict: pass\nreviewed_at: x\nfindings: 0\n", id="unterminated"),
            pytest.param("---\n- a\n- b\n---\nbody\n", id="non-mapping"),
            pytest.param("---\nverdict: [unclosed\n---\n", id="invalid-yaml"),
            pytest.param("---\nverdict: PASS WITH NOTES\nreviewed_at: x\nfindings: 1\n---\n", id="foreign-verdict"),
            pytest.param("---\nverdict: pass\nfindings: 0\n---\n", id="no-reviewed-at"),
            pytest.param("---\nverdict: pass\nreviewed_at: x\nfindings: none\n---\n", id="non-int-findings"),
            pytest.param("---\nverdict: pass\nreviewed_at: x\nfindings: true\n---\n", id="bool-findings"),
            pytest.param("---\ngenerator: my-agent\nverdict: pass\nreviewed_at: x\nfindings: 0\n---\n", id="foreign-generator"),
        ],
    )
    def test_foreign_text_is_not_a_machine_report(self, text: str) -> None:
        assert not is_machine_review_report(text)

    def test_generator_marker_is_recognised(self) -> None:
        text = f"---\ngenerator: {REPORT_GENERATOR}\nverdict: pass\nreviewed_at: x\nfindings: 0\n---\n"
        assert is_machine_review_report(text)


class TestEnsureReportPathWritable:
    def test_absent_path_is_writable(self, tmp_path: Path) -> None:
        assert ensure_report_path_writable(tmp_path) == tmp_path / REVIEW_REPORT_FILENAME

    def test_previous_machine_report_is_writable(self, tmp_path: Path) -> None:
        (tmp_path / REVIEW_REPORT_FILENAME).write_text(_LEGACY_MACHINE_REPORT, encoding="utf-8")
        assert ensure_report_path_writable(tmp_path) == tmp_path / REVIEW_REPORT_FILENAME

    def test_agent_report_is_refused(self, tmp_path: Path) -> None:
        (tmp_path / REVIEW_REPORT_FILENAME).write_text(_AGENT_REPORT, encoding="utf-8")
        with pytest.raises(ReportPathOccupiedError, match="MISSION_REVIEW_REPORT_PATH_OCCUPIED") as excinfo:
            ensure_report_path_writable(tmp_path)
        assert excinfo.value.reason == REASON_NOT_MACHINE_REPORT

    def test_undecodable_file_is_refused(self, tmp_path: Path) -> None:
        (tmp_path / REVIEW_REPORT_FILENAME).write_bytes(b"\xff\xfe\x00binary")
        with pytest.raises(ReportPathOccupiedError) as excinfo:
            ensure_report_path_writable(tmp_path)
        assert excinfo.value.reason == REASON_UNREADABLE

    def test_directory_at_path_is_refused(self, tmp_path: Path) -> None:
        (tmp_path / REVIEW_REPORT_FILENAME).mkdir()
        with pytest.raises(ReportPathOccupiedError) as excinfo:
            ensure_report_path_writable(tmp_path)
        assert excinfo.value.reason == REASON_NOT_REGULAR_FILE

    def test_symlink_is_refused_even_to_a_machine_report(self, tmp_path: Path) -> None:
        target = tmp_path / "elsewhere.md"
        target.write_text(_CURRENT_MACHINE_REPORT, encoding="utf-8")
        try:
            (tmp_path / REVIEW_REPORT_FILENAME).symlink_to(target)
        except OSError:
            pytest.skip("symlinks unavailable on this platform")
        with pytest.raises(ReportPathOccupiedError) as excinfo:
            ensure_report_path_writable(tmp_path)
        assert excinfo.value.reason == REASON_SYMLINK
        assert target.read_text(encoding="utf-8") == _CURRENT_MACHINE_REPORT

    def test_agent_review_filename_differs_from_report_filename(self) -> None:
        assert AGENT_REVIEW_FILENAME != REVIEW_REPORT_FILENAME


class TestWriteReport:
    """The write itself never clobbers a file that appears after the check."""

    def test_absent_path_is_created(self, tmp_path: Path) -> None:
        path = _report._write_report(tmp_path, _CURRENT_MACHINE_REPORT)
        assert path.read_text(encoding="utf-8") == _CURRENT_MACHINE_REPORT
        assert sorted(p.name for p in tmp_path.iterdir()) == [REVIEW_REPORT_FILENAME]

    def test_machine_report_is_replaced_without_leftovers(self, tmp_path: Path) -> None:
        (tmp_path / REVIEW_REPORT_FILENAME).write_text(_LEGACY_MACHINE_REPORT, encoding="utf-8")
        _report._write_report(tmp_path, _CURRENT_MACHINE_REPORT)
        assert (tmp_path / REVIEW_REPORT_FILENAME).read_text(encoding="utf-8") == _CURRENT_MACHINE_REPORT
        assert sorted(p.name for p in tmp_path.iterdir()) == [REVIEW_REPORT_FILENAME]

    def _race(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, appearing: str) -> None:
        """Make *appearing* land at the report path right after the first check."""
        real_check = _report._check_report_path
        calls = {"n": 0}

        def racing_check(feature_dir: Path) -> tuple[Path, bool]:
            path, holds_machine_report = real_check(feature_dir)
            calls["n"] += 1
            if calls["n"] == 1:
                path.write_text(appearing, encoding="utf-8")
            return path, holds_machine_report

        monkeypatch.setattr(_report, "_check_report_path", racing_check)

    def test_foreign_file_appearing_after_the_check_is_refused(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        self._race(monkeypatch, tmp_path, _AGENT_REPORT)
        with pytest.raises(ReportPathOccupiedError):
            _report._write_report(tmp_path, _CURRENT_MACHINE_REPORT)
        assert (tmp_path / REVIEW_REPORT_FILENAME).read_text(encoding="utf-8") == _AGENT_REPORT

    def test_machine_report_appearing_after_the_check_is_replaced(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        self._race(monkeypatch, tmp_path, _LEGACY_MACHINE_REPORT)
        _report._write_report(tmp_path, _CURRENT_MACHINE_REPORT)
        assert (tmp_path / REVIEW_REPORT_FILENAME).read_text(encoding="utf-8") == _CURRENT_MACHINE_REPORT

    def test_failed_replace_leaves_no_temp_file(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        (tmp_path / REVIEW_REPORT_FILENAME).write_text(_LEGACY_MACHINE_REPORT, encoding="utf-8")

        def failing_replace(src: str, dst: object) -> None:
            raise OSError("disk full")

        monkeypatch.setattr("specify_cli.cli.commands.review._report.os.replace", failing_replace)
        with pytest.raises(OSError, match="disk full"):
            _report._write_report(tmp_path, _CURRENT_MACHINE_REPORT)
        assert sorted(p.name for p in tmp_path.iterdir()) == [REVIEW_REPORT_FILENAME]
        assert (tmp_path / REVIEW_REPORT_FILENAME).read_text(encoding="utf-8") == _LEGACY_MACHINE_REPORT


def test_refusal_outside_repo_root_prints_absolute_path_and_json_line(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    report_path = tmp_path / "elsewhere" / REVIEW_REPORT_FILENAME
    console = Console(width=400, force_terminal=False, record=True)
    with pytest.raises(typer.Exit) as excinfo:
        refuse_occupied_report_path(ReportPathOccupiedError(report_path, REASON_SYMLINK), tmp_path / "repo", console)
    assert excinfo.value.exit_code == 1
    assert f"{report_path} is a symlink" in console.export_text()
    diagnostic = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert diagnostic == {
        "diagnostic_code": "MISSION_REVIEW_REPORT_PATH_OCCUPIED",
        "message": f"{report_path} is a symlink; refusing to overwrite it. Nothing was written.",
        "remediation": f"git mv {report_path} {report_path.with_name(AGENT_REVIEW_FILENAME)}",
    }


def _invoke_review(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, existing: str | None) -> tuple[Path, int, str]:
    repo_root, feature_dir = setup_fixture(tmp_path, {"WP01": "done", "WP02": "done"})
    report_path = feature_dir / REVIEW_REPORT_FILENAME
    if existing is not None:
        report_path.write_text(existing, encoding="utf-8")
    monkeypatch.chdir(repo_root)
    monkeypatch.setattr("specify_cli.cli.commands.review.find_repo_root", lambda: repo_root)
    resolved = make_mock_resolved(feature_dir)
    monkeypatch.setattr(
        "specify_cli.cli.commands.review.resolve_mission_handle",
        lambda handle, repo_root: resolved,
    )
    result = CliRunner().invoke(build_cli_app(), ["--mission", MISSION_SLUG])
    return report_path, result.exit_code, result.output


@pytest.mark.parametrize("previous", [_CURRENT_MACHINE_REPORT, _LEGACY_MACHINE_REPORT], ids=["current", "legacy"])
def test_rerun_refreshes_its_own_previous_report(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, previous: str) -> None:
    """Re-running ``spec-kitty review`` over its own report still overwrites it."""
    report_path, exit_code, output = _invoke_review(tmp_path, monkeypatch, previous)

    assert "MISSION_REVIEW_REPORT_PATH_OCCUPIED" not in output, output
    assert "Report written" in output, output
    refreshed = report_path.read_text(encoding="utf-8")
    assert refreshed != previous
    assert "findings: 99" not in refreshed
    assert is_machine_review_report(refreshed)
    # The fresh report must itself be recognised, so the next rerun refreshes it too.
    assert exit_code in (0, 1), output
    assert f"generator: {REPORT_GENERATOR}" in refreshed


def test_agent_report_saved_while_gates_run_is_refused_at_write_time(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The write-time re-check: a review saved mid-run survives (#7753 review finding 1)."""
    repo_root, feature_dir = setup_fixture(tmp_path, {"WP01": "done", "WP02": "done"})
    report_path = feature_dir / REVIEW_REPORT_FILENAME
    import specify_cli.cli.commands.review as review_pkg

    real_gate = review_pkg._run_ble001_gate

    def gate_then_agent_saves(*args: Any, **kwargs: Any) -> Any:
        result = real_gate(*args, **kwargs)
        report_path.write_text(_AGENT_REPORT, encoding="utf-8")
        return result

    monkeypatch.setattr(review_pkg, "_run_ble001_gate", gate_then_agent_saves)
    monkeypatch.chdir(repo_root)
    monkeypatch.setattr("specify_cli.cli.commands.review.find_repo_root", lambda: repo_root)
    resolved = make_mock_resolved(feature_dir)
    monkeypatch.setattr("specify_cli.cli.commands.review.resolve_mission_handle", lambda handle, repo_root: resolved)

    result = CliRunner().invoke(build_cli_app(), ["--mission", MISSION_SLUG])

    assert result.exit_code == 1, result.output
    assert "MISSION_REVIEW_REPORT_PATH_OCCUPIED" in result.output, result.output
    assert '"diagnostic_code": "MISSION_REVIEW_REPORT_PATH_OCCUPIED"' in result.output, result.output
    assert "Report written" not in result.output, result.output
    assert report_path.read_text(encoding="utf-8") == _AGENT_REPORT
