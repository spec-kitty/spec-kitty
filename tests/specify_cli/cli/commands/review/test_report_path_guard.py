"""#7753: ``spec-kitty review`` owns only its own machine report.

Unit coverage of the report-path guard in ``review/_report.py`` plus the
CLI-level rerun contract: a previous machine report (either generation of its
frontmatter) is still refreshed, anything else is refused and left untouched.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.review._report import (
    AGENT_REVIEW_FILENAME,
    REVIEW_REPORT_FILENAME,
    ReportPathOccupiedError,
    ensure_report_path_writable,
    is_machine_review_report,
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
        ],
    )
    def test_foreign_text_is_not_a_machine_report(self, text: str) -> None:
        assert not is_machine_review_report(text)


class TestEnsureReportPathWritable:
    def test_absent_path_is_writable(self, tmp_path: Path) -> None:
        assert ensure_report_path_writable(tmp_path) == tmp_path / REVIEW_REPORT_FILENAME

    def test_previous_machine_report_is_writable(self, tmp_path: Path) -> None:
        (tmp_path / REVIEW_REPORT_FILENAME).write_text(_LEGACY_MACHINE_REPORT, encoding="utf-8")
        assert ensure_report_path_writable(tmp_path) == tmp_path / REVIEW_REPORT_FILENAME

    def test_agent_report_is_refused(self, tmp_path: Path) -> None:
        (tmp_path / REVIEW_REPORT_FILENAME).write_text(_AGENT_REPORT, encoding="utf-8")
        with pytest.raises(ReportPathOccupiedError, match="MISSION_REVIEW_REPORT_PATH_OCCUPIED"):
            ensure_report_path_writable(tmp_path)

    def test_undecodable_file_is_refused(self, tmp_path: Path) -> None:
        (tmp_path / REVIEW_REPORT_FILENAME).write_bytes(b"\xff\xfe\x00binary")
        with pytest.raises(ReportPathOccupiedError):
            ensure_report_path_writable(tmp_path)

    def test_directory_at_path_is_refused(self, tmp_path: Path) -> None:
        (tmp_path / REVIEW_REPORT_FILENAME).mkdir()
        with pytest.raises(ReportPathOccupiedError):
            ensure_report_path_writable(tmp_path)

    def test_symlink_is_refused_even_to_a_machine_report(self, tmp_path: Path) -> None:
        target = tmp_path / "elsewhere.md"
        target.write_text(_CURRENT_MACHINE_REPORT, encoding="utf-8")
        try:
            (tmp_path / REVIEW_REPORT_FILENAME).symlink_to(target)
        except OSError:
            pytest.skip("symlinks unavailable on this platform")
        with pytest.raises(ReportPathOccupiedError):
            ensure_report_path_writable(tmp_path)
        assert target.read_text(encoding="utf-8") == _CURRENT_MACHINE_REPORT

    def test_agent_review_filename_differs_from_report_filename(self) -> None:
        assert AGENT_REVIEW_FILENAME != REVIEW_REPORT_FILENAME


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
