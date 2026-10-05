"""The behaviours GitHub issue #4925 broke, pinned through the real ``upgrade`` command.

On an up-to-date project (no migrations pending) with one managed tool-surface
file that needs the operator's consent before it is overwritten,
``spec-kitty upgrade --yes`` printed ``Project is already up to date!`` and
exited 1 with no reason. A repair that was not applied at all was worded
a drift message that counted zero files.

Both are exercised here through the pre-existing entry point: the command is
driven with ``CliRunner`` on a real project, and only the prepared repair
inventory (the input the drift comes from) is shaped by the fixture. The outcome
object is never constructed by hand. The fixed behaviour is also a row of the
outcome matrix in ``test_upgrade_outcome_rendering.py``; these two tests stay as
the focused, behaviour-named witnesses (they were committed red before the fix).
"""

from __future__ import annotations

import contextlib
import json
import subprocess
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
import typer
from typer.testing import CliRunner

from specify_cli.cli.commands import upgrade as upgrade_module
from specify_cli.migration.schema_version import MAX_SUPPORTED_SCHEMA
from specify_cli.tool_surface.operations import Disposition, OwnerApplyResult, OwnerAssessment
from specify_cli.upgrade import assessment

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_VERSION = "3.2.0rc37"
_OWNER = "agent_profiles"
_DRIFTED_PATH = ".claude/agents/reviewer.md"
_DRIFT_MESSAGE = f"Not updated, your local edit was kept: {_DRIFTED_PATH}"
_NOT_APPLIED_MESSAGE = "Tool-surface repair for agent_profiles was not applied"

_test_app = typer.Typer(add_completion=False)
_test_app.command()(upgrade_module.upgrade)
_runner = CliRunner()


def _write_project(project: Path) -> None:
    kittify = project / ".kittify"
    kittify.mkdir(parents=True)
    (kittify / "metadata.yaml").write_text(
        f"spec_kitty:\n  version: \"{_VERSION}\"\n  schema_version: {MAX_SUPPORTED_SCHEMA}\n  initialized_at: '2026-01-01T00:00:00+00:00'\n",
        encoding="utf-8",
    )
    (kittify / "config.yaml").write_text("vcs:\n  type: git\nmission_type_activations:\n  - software-development\n", encoding="utf-8")
    (project / "kitty-specs").mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=project, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=project, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=project, check=True)
    subprocess.run(["git", "add", "-A"], cwd=project, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=project, check=True)


def _with_one_drifted_owner(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make the prepared inventory report one managed file that needs consent.

    The drift is a disposition (a file preserved pending consent), not an effect,
    so there is nothing to write: the apply step is stubbed to report no result.
    """
    original = assessment.prepare_upgrade_repairs
    monkeypatch.setattr(assessment, "apply_upgrade_repairs", lambda _prepared: ())

    def _prepare(*args: Any, **kwargs: Any) -> Any:
        prepared = original(*args, **kwargs)
        drifted = OwnerAssessment(
            owner_key=_OWNER,
            root=prepared.root,
            dispositions=(Disposition(_OWNER, prepared.root.root_id, _DRIFTED_PATH, "consent_required", "edited by hand"),),
        )
        return replace(prepared, remaining=(*prepared.remaining, drifted))

    monkeypatch.setattr(assessment, "prepare_upgrade_repairs", _prepare)


def _with_unapplied_repair_and_no_drift(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make the repair report a failure while no managed file is drifted."""

    def _apply(_prepared: Any) -> tuple[OwnerApplyResult, ...]:
        return (OwnerApplyResult(owner_key=_OWNER, failed=("effect-1",), outcome="failed"),)

    monkeypatch.setattr(assessment, "apply_upgrade_repairs", _apply)


def _invoke(project: Path, args: list[str]) -> Any:
    with contextlib.chdir(project):
        return _runner.invoke(_test_app, ["--target", _VERSION, "--no-worktrees", "--no-nag", *args], catch_exceptions=False)


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("CI", "1")
    monkeypatch.setattr(upgrade_module, "show_banner", lambda: None)
    root = tmp_path / "project"
    root.mkdir()
    _write_project(root)
    return root


def test_unresolved_drift_on_a_no_migrations_run_is_reported_in_text_mode(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """#4925: a non-zero exit names its reason and never claims the project is up to date."""
    _with_one_drifted_owner(monkeypatch)

    result = _invoke(project, ["--yes"])

    assert result.exit_code != 0, result.output
    assert _DRIFT_MESSAGE in result.output
    assert "already up to date" not in result.output.lower()


def test_unapplied_repair_is_not_reported_as_drift_in_zero_files(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A repair that was not applied is a repair failure, never ``drift in 0 file(s)``."""
    _with_unapplied_repair_and_no_drift(monkeypatch)

    result = _invoke(project, ["--yes", "--json"])

    payload = json.loads(result.output.strip().splitlines()[-1])
    assert result.exit_code != 0, result.output
    assert payload["errors"], payload
    assert not any(" 0 managed file(s)" in error for error in payload["errors"]), payload
    assert any(_NOT_APPLIED_MESSAGE in error for error in payload["errors"]), payload
