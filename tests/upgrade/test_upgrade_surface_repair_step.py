"""``spec-kitty upgrade`` has exactly one surface-repair path: the prepared one.

The real ``upgrade`` command is driven in-process through ``CliRunner``, with a counter
around the live apply seam, to pin when the surface repair is applied and when it is
skipped: applied after a successful preparation on a real run; skipped when preparation
raises, on a dry run, and after a failed migration. What each of those runs reports is a
row of the outcome matrix in ``test_upgrade_outcome_rendering.py``.
"""

from __future__ import annotations

import contextlib
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
import typer
from typer.testing import CliRunner

from specify_cli import app as root_app
from specify_cli.cli.commands import upgrade as upgrade_module
from specify_cli.core.agent_config import AgentConfigError
from specify_cli.migration.schema_version import MAX_SUPPORTED_SCHEMA
from specify_cli.upgrade import assessment
from specify_cli.upgrade.runner import MigrationRunner, UpgradeResult

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_CURRENT_VERSION = "3.2.0rc37"
_STALE_VERSION = "0.0.1"
_PREPARE = "prepare_upgrade_repairs"
_APPLY = "apply_upgrade_repairs"

_test_app = typer.Typer(add_completion=False)
_test_app.command()(upgrade_module.upgrade)
_runner = CliRunner()


def _write_project(project: Path, *, version: str) -> None:
    kittify = project / ".kittify"
    kittify.mkdir(parents=True)
    (kittify / "metadata.yaml").write_text(
        f"spec_kitty:\n  version: \"{version}\"\n  schema_version: {MAX_SUPPORTED_SCHEMA}\n  initialized_at: '2026-01-01T00:00:00+00:00'\n",
        encoding="utf-8",
    )
    (kittify / "config.yaml").write_text("vcs:\n  type: git\nmission_type_activations:\n  - software-development\n", encoding="utf-8")
    (project / "kitty-specs").mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=project, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=project, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=project, check=True)
    subprocess.run(["git", "add", "-A"], cwd=project, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=project, check=True)


class _Spies:
    """Call counter for the live apply seam."""

    def __init__(self) -> None:
        self.apply_calls = 0


@pytest.fixture
def spies(monkeypatch: pytest.MonkeyPatch) -> _Spies:
    """Count calls to the live apply seam while running the real flow."""
    counters = _Spies()
    monkeypatch.setenv("CI", "1")

    real_apply = getattr(assessment, _APPLY)

    def _counting_apply(*args: Any, **kwargs: Any) -> Any:
        counters.apply_calls += 1
        return real_apply(*args, **kwargs)

    monkeypatch.setattr(assessment, _APPLY, _counting_apply)
    return counters


def _invoke(project: Path, args: list[str]) -> Any:
    with contextlib.chdir(project):
        return _runner.invoke(_test_app, args, catch_exceptions=False)


def _real_run_args(target: str) -> list[str]:
    return ["--target", target, "--force", "--no-worktrees", "--no-nag"]


def test_surface_repair_is_applied_when_preparation_succeeds(tmp_path: Path, spies: _Spies) -> None:
    project = tmp_path / "prepared"
    project.mkdir()
    _write_project(project, version=_CURRENT_VERSION)

    result = _invoke(project, _real_run_args(_CURRENT_VERSION))

    assert result.exit_code == 0, result.output
    assert spies.apply_calls == 1  # the prepared path did the surface repair


@pytest.mark.parametrize(
    "error",
    [OSError("disk unreadable"), ValueError("bad agent config"), AgentConfigError("agent config invalid")],
    ids=["oserror", "valueerror", "agentconfigerror"],
)
def test_surface_repair_is_skipped_when_preparation_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, spies: _Spies, error: Exception) -> None:
    project = tmp_path / "prep-raises"
    project.mkdir()
    _write_project(project, version=_CURRENT_VERSION)

    def _raise(*args: Any, **kwargs: Any) -> Any:
        raise error

    monkeypatch.setattr(assessment, _PREPARE, _raise)

    result = _invoke(project, [*_real_run_args(_CURRENT_VERSION), "--json"])

    assert result.exit_code == 1, result.output
    payload = json.loads(result.output.strip().splitlines()[-1])
    assert payload["failure_reasons"] == ["repair_preparation_failed"]  # not an activation error: no provisioning ran
    assert payload["errors"] == [str(error)]
    assert spies.apply_calls == 0  # surface repair skipped


def test_surface_repair_is_not_applied_on_dry_run(tmp_path: Path, spies: _Spies) -> None:
    project = tmp_path / "dry-run"
    project.mkdir()
    _write_project(project, version=_CURRENT_VERSION)

    result = _invoke(project, [*_real_run_args(_CURRENT_VERSION), "--dry-run"])

    assert result.exit_code == 0, result.output
    assert spies.apply_calls == 0


def test_surface_repair_is_skipped_after_a_failed_migration(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, spies: _Spies) -> None:
    project = tmp_path / "failed-migration"
    project.mkdir()
    _write_project(project, version=_STALE_VERSION)

    def _failed_upgrade(self: MigrationRunner, target_version: str, **kwargs: Any) -> UpgradeResult:
        return UpgradeResult(success=False, from_version=_STALE_VERSION, to_version=target_version, errors=["migration failed"])

    monkeypatch.setattr(MigrationRunner, "upgrade", _failed_upgrade)

    result = _invoke(project, _real_run_args("3.2.0rc38"))

    assert result.exit_code == 1, result.output
    assert spies.apply_calls == 0


@pytest.mark.slow
def test_upgrade_recreates_a_deleted_tool_folder_without_an_owner_effect_conflict(tmp_path: Path) -> None:
    """#4275: managed skills and agent profiles both plan ``create .claude``; it must be planned once."""
    project = tmp_path / "project"
    project.mkdir()
    with contextlib.chdir(project):
        init_result = _runner.invoke(root_app, ["init", "--ai", "claude,codex", "--non-interactive"], catch_exceptions=False)
    assert init_result.exit_code == 0, init_result.output
    assert (project / ".claude").is_dir()
    assert (project / ".agents" / "skills").is_dir()

    shutil.rmtree(project / ".claude")

    with contextlib.chdir(project):
        result = _runner.invoke(root_app, ["upgrade", "--yes"], catch_exceptions=False)

    assert result.exit_code == 0, result.output
    assert "Owner effect conflict" not in result.output
    assert (project / ".claude").is_dir()
    assert any((project / ".claude").iterdir())
    assert (project / ".agents" / "skills").is_dir()
