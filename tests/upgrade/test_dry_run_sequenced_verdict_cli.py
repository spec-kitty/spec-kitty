"""The operator sees the dry run's prediction in the CLI output, on the production path (#6552).

``tests/upgrade/test_dry_run_sequenced_verdict.py`` pins the runner's sequenced verdict. This
module drives the real ``spec-kitty upgrade`` command and asserts the RENDERED output, because
a verdict the operator cannot tell apart from a direct detection is only half the fix
(tactic ``acceptance-criteria-non-vacuity``, "exercise the production path"):

* the dry-run summary lists the predicted migration under ``Migrations applied:`` **and**
  names the migration it follows, so the operator can tell a prediction from a detection;
* ``--dry-run --verbose``'s pre-run detection preview agrees with that summary instead of
  calling the same migration ``skipped``;
* the same fixture upgraded for real lists the migration as applied without the prediction
  line (the positive control that the fixture really has the work pending).

The fixture is shared with the runner-level module so the two proofs cannot drift apart.
"""

from __future__ import annotations

import contextlib
import re
from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

from specify_cli.cli.commands.upgrade import upgrade
from specify_cli.upgrade.migrations.m_3_2_6_gate_artifact_merge_drivers import (
    GateArtifactMergeDriverMigration,
)
from specify_cli.upgrade.migrations.m_3_2_6_issue_matrix_driver_repoint import (
    IssueMatrixDriverRepointMigration,
)
from specify_cli.upgrade.registry import MigrationRegistry
from tests.upgrade.test_dry_run_sequenced_verdict import (
    _copy,
    _pair_project,
    _tree_digest,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_GATE = "3.2.6_gate_artifact_merge_drivers"
_REPOINT = "3.2.6_issue_matrix_driver_repoint"
_PREDICTION_HEADER = "Predicted by an earlier migration in this run (dry run):"

_test_app = typer.Typer(add_completion=False)
_test_app.command()(upgrade)
_runner = CliRunner()


def _invoke(project: Path, args: list[str], monkeypatch: pytest.MonkeyPatch) -> object:
    """Run the real ``upgrade`` command inside *project*, offline."""
    monkeypatch.setenv("CI", "1")
    with contextlib.chdir(project):
        return _runner.invoke(_test_app, args, catch_exceptions=False)


def _lines(output: str, needle: str) -> list[str]:
    """Rendered lines mentioning *needle*, ANSI/box-drawing noise aside."""
    return [line for line in output.splitlines() if needle in line]


def _only_the_reported_pair() -> None:
    """Narrow the candidate set to the reported pair (registry restored by tests/upgrade/conftest.py)."""
    MigrationRegistry.clear()
    MigrationRegistry.register(GateArtifactMergeDriverMigration)
    MigrationRegistry.register(IssueMatrixDriverRepointMigration)


def test_the_dry_run_summary_names_the_migration_it_predicts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """M1 of the round-1 review: the prediction is operator-visible, not just data."""
    project = _pair_project(tmp_path)
    before = _tree_digest(project)

    result = _invoke(project, ["--project", "--dry-run", "--no-worktrees"], monkeypatch)

    assert result.exit_code == 0, result.output
    assert "Migrations applied:" in result.output
    assert re.search(rf"✓\s+{re.escape(_REPOINT)}", result.output), result.output
    assert _PREDICTION_HEADER in result.output, result.output
    assert re.search(
        rf"•\s+{re.escape(_REPOINT)}\s+would apply after\s+{re.escape(_GATE)}",
        result.output,
    ), result.output
    # The old, false claim is gone for the predicted migration...
    assert not _lines(result.output, f"{_REPOINT} not needed"), result.output
    # ...and the preview wrote nothing.
    assert _tree_digest(project) == before


def test_the_verbose_preview_agrees_with_the_dry_run_summary(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """M2 of the round-1 review: the pre-run preview uses the same sequencing decision."""
    project = _pair_project(tmp_path)

    result = _invoke(project, ["--project", "--dry-run", "--verbose", "--no-worktrees"], monkeypatch)

    assert result.exit_code == 0, result.output
    preview = [line for line in _lines(result.output, f"{_REPOINT}:") if "ready" in line or "skipped" in line]
    assert preview, result.output
    assert "ready" in preview[0], result.output
    assert f"would apply after {_GATE}" in preview[0], result.output
    # The gate migration's own line carries no prediction note: it is directly detected.
    gate_line = [line for line in _lines(result.output, f"{_GATE}:") if "ready" in line or "skipped" in line][0]
    assert "would apply after" not in gate_line, gate_line


def test_a_real_run_lists_the_migration_without_a_prediction(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Positive control: the fixture has the work pending, and a real run never predicts."""
    project = _copy(_pair_project(tmp_path), tmp_path / "real")
    _only_the_reported_pair()
    before = _tree_digest(project)

    result = _invoke(project, ["--project", "--yes", "--no-worktrees"], monkeypatch)

    assert result.exit_code == 0, result.output
    assert re.search(rf"✓\s+{re.escape(_REPOINT)}", result.output), result.output
    assert _PREDICTION_HEADER not in result.output, result.output
    assert _tree_digest(project) != before, "the real run must write, or the dry-run no-writes check is vacuous"
