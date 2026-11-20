"""Per-PR guard for P0 spec-kitty/spec-kitty#7753 (in-matrix lift).

``spec-kitty review`` once replaced ``kitty-specs/<slug>/mission-review-report.md``
unconditionally, destroying an agent-written mission review saved under that
name. The red-first reproduction and the full guard suite live in
``tests/specify_cli/cli/commands/`` (``test_p0_repro_7753_*`` and
``review/test_report_path_guard.py``), which ``.github/ci-module-registry.yml``
lists under ``out_of_matrix_test_dirs``: they run in the nightly only. This
file lifts the contract into ``tests/cli``, the per-PR test dir of the ``cli``
module that owns ``src/specify_cli/cli/**``, so a regression reds the PR that
causes it.

The pinned contract:
- a foreign file at the report path is refused with
  ``MISSION_REVIEW_REPORT_PATH_OCCUPIED`` and exit 1, with the JSON diagnostic
  line, before any gate runs, and its bytes are left untouched;
- a foreign file saved while the gates run is refused at the write;
- the command's own previous report is still refreshed.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

import specify_cli.cli.commands.review as review_pkg
from tests.specify_cli.cli.commands._review_fixtures import (
    MISSION_SLUG,
    build_cli_app,
    make_mock_resolved,
    setup_fixture,
)

pytestmark = [pytest.mark.fast, pytest.mark.non_sandbox]

_CODE = "MISSION_REVIEW_REPORT_PATH_OCCUPIED"
REVIEW_REPORT_FILENAME = "mission-review-report.md"
_AGENT_REVIEW = b"# Mission Review Report: x\n\n**Reviewer**: agent-7753\n\n## Final Verdict\n\nPASS\n"
_PREVIOUS_MACHINE_REPORT = "---\nverdict: fail\nreviewed_at: 2026-11-01T00:00:00+00:00\nfindings: 99\n---\n\n## Findings\n"


def _prepare(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    repo_root, feature_dir = setup_fixture(tmp_path, {"WP01": "done", "WP02": "done"})
    monkeypatch.chdir(repo_root)
    monkeypatch.setattr("specify_cli.cli.commands.review.find_repo_root", lambda: repo_root)
    resolved = make_mock_resolved(feature_dir)
    monkeypatch.setattr("specify_cli.cli.commands.review.resolve_mission_handle", lambda handle, repo_root: resolved)
    return repo_root, feature_dir


def test_foreign_report_is_refused_before_any_gate_and_kept_byte_identical(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _repo_root, feature_dir = _prepare(tmp_path, monkeypatch)
    report_path = feature_dir / REVIEW_REPORT_FILENAME
    report_path.write_bytes(_AGENT_REVIEW)
    gates_run: list[str] = []
    monkeypatch.setattr(review_pkg, "_run_lane_gate", lambda *a, **k: gates_run.append("lane"))

    result = CliRunner().invoke(build_cli_app(), ["--mission", MISSION_SLUG])

    assert result.exit_code == 1, result.output
    assert _CODE in result.output, result.output
    assert f'"diagnostic_code": "{_CODE}"' in result.output, result.output
    assert gates_run == [], "the refusal must come before any gate runs"
    assert report_path.read_bytes() == _AGENT_REVIEW


def test_foreign_report_saved_while_gates_run_is_refused_at_write(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _repo_root, feature_dir = _prepare(tmp_path, monkeypatch)
    report_path = feature_dir / REVIEW_REPORT_FILENAME
    real_gate = review_pkg._run_ble001_gate

    def gate_then_agent_saves(*args: Any, **kwargs: Any) -> Any:
        result = real_gate(*args, **kwargs)
        report_path.write_bytes(_AGENT_REVIEW)
        return result

    monkeypatch.setattr(review_pkg, "_run_ble001_gate", gate_then_agent_saves)

    result = CliRunner().invoke(build_cli_app(), ["--mission", MISSION_SLUG])

    assert result.exit_code == 1, result.output
    assert _CODE in result.output, result.output
    assert "Report written" not in result.output, result.output
    assert report_path.read_bytes() == _AGENT_REVIEW


def test_own_previous_report_is_refreshed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _repo_root, feature_dir = _prepare(tmp_path, monkeypatch)
    report_path = feature_dir / REVIEW_REPORT_FILENAME
    report_path.write_text(_PREVIOUS_MACHINE_REPORT, encoding="utf-8")

    result = CliRunner().invoke(build_cli_app(), ["--mission", MISSION_SLUG])

    assert _CODE not in result.output, result.output
    assert "Report written" in result.output, result.output
    refreshed = report_path.read_text(encoding="utf-8")
    assert "findings: 99" not in refreshed
    assert refreshed.startswith("---\n")
    assert "verdict: " in refreshed
