"""CLI boundary contracts: FR-005/007/008 and shared doctor guard (#4532)."""

from __future__ import annotations

import importlib
import json
import logging
import warnings
from pathlib import Path
from typing import Any

import pytest
import typer
from typer.testing import CliRunner

from charter.resolution import GitCommonDirUnavailableError, NotInsideRepositoryError
from specify_cli.cli import helpers
from specify_cli.cli.commands import _doctor_shared, doctor

pytestmark = [pytest.mark.fast, pytest.mark.unit]
runner = CliRunner()


def test_root_helper_json_missing_project(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(helpers, "locate_project_root", lambda start: None)
    app = typer.Typer()

    @app.command()
    def command() -> None:
        helpers.get_project_root_or_exit(json_output=True)

    result = runner.invoke(app, [])
    assert result.exit_code == 1
    assert json.loads(result.stdout)["error"]["code"] == "not_in_project"
    assert result.stderr == ""


@pytest.mark.parametrize("json_output", [False, True])
def test_root_helper_success_preserves_path(json_output: bool, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(helpers, "locate_project_root", lambda start: start)
    assert helpers.get_project_root_or_exit(tmp_path, json_output=json_output) == tmp_path


@pytest.mark.parametrize("missing_git", [False, True])
@pytest.mark.parametrize("json_output", [False, True])
def test_git_failure_stream_and_exit(missing_git: bool, json_output: bool, tmp_path: Path) -> None:
    error = GitCommonDirUnavailableError(tmp_path, "git unavailable") if missing_git else NotInsideRepositoryError(tmp_path)
    app = typer.Typer()

    @app.command()
    def command() -> None:
        helpers.exit_git_resolution_failure(error, tmp_path, json_output=json_output)

    result = runner.invoke(app, [])
    assert result.exit_code == 1
    expected_message = helpers.git_resolution_failure_message(error, tmp_path)
    if json_output:
        assert json.loads(result.stdout) == {"ok": False, "error": {"code": "git_resolution_failed", "message": expected_message}}
        assert result.stderr == ""
    else:
        assert "Error:" in result.stdout
        assert "git" in result.stdout


_DOCTORS = [
    ("state-roots", "doctor", 1, ()),
    ("workspaces", "doctor", 1, ()),
    ("identity", "doctor", 1, ()),
    ("topology", "doctor", 1, ()),
    ("mission-type", "doctor", 1, ()),
    ("shim-registry", "doctor", 2, ()),
    ("contracts", "doctor", 2, ()),
    ("invocation-pairing", "doctor", 1, ()),
    ("ops", "doctor", 1, ()),
    ("doctrine", "doctor", 1, ()),
    ("cutover", "doctor", 1, ()),
    ("review-cycle-reconcile", "doctor", 1, ()),
    ("skills", "doctor", 2, ()),
    ("command-files", "_command_surface_doctor", 1, ()),
    ("tool-surfaces", "_command_surface_doctor", 2, ()),
    ("provenance", "_provenance_doctor", 1, ()),
    ("env-file", "_env_file_doctor", 1, ()),
    ("coordination", "_coordination_doctor", 1, ()),
    ("mission-state", "doctor", 1, ("--audit",)),
]


@pytest.mark.parametrize("command,module_name,exit_code,extra", _DOCTORS)
@pytest.mark.parametrize("raises", [False, True])
def test_doctors_delegate_root_failure_to_one_guard(
    command: str, module_name: str, exit_code: int, extra: tuple[str, ...], raises: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    """#4532: both failure arms pass through one guard, preserving the frozen output."""
    module = importlib.import_module(f"specify_cli.cli.commands.{module_name}")

    def resolver() -> None:
        if raises:
            raise RuntimeError("broken root lookup")
        return None

    monkeypatch.setattr(module, "locate_project_root", resolver)
    guard = getattr(_doctor_shared, "resolve_project_root_or_exit", None)
    calls: list[dict[str, Any]] = []

    def observed_guard(*args: Any, **kwargs: Any) -> Any:
        calls.append(kwargs)
        assert guard is not None
        return guard(*args, **kwargs)

    monkeypatch.setattr(_doctor_shared, "resolve_project_root_or_exit", observed_guard, raising=False)
    result = runner.invoke(doctor.app, [command, *extra, "--json"])
    assert result.exit_code == exit_code, result.output
    assert json.loads(result.stdout) == {"ok": False, "error": {"code": "not_in_project", "message": "Not in a spec-kitty project"}}
    assert result.stderr == ""
    assert len(calls) == 1, f"{command} bypasses the shared root guard"


def test_json_guard_restores_warning_filters_and_logging_on_failure() -> None:
    previous_filters = warnings.filters[:]
    previous_disable = logging.root.manager.disable
    with pytest.raises(RuntimeError), _doctor_shared._json_output_guard(True):
        assert logging.root.manager.disable == logging.CRITICAL
        warnings.warn("suppressed boundary warning", stacklevel=1)
        raise RuntimeError("command failed")
    assert warnings.filters == previous_filters
    assert logging.root.manager.disable == previous_disable


def test_doctor_reexports_canonical_contract() -> None:
    from specify_cli.cli.json_contract import json_error, json_output_guard

    assert _doctor_shared._json_error is json_error
    assert _doctor_shared._json_output_guard is json_output_guard


@pytest.mark.parametrize("raises", [False, True])
def test_fixture_only_root_preserves_none_but_not_resolver_failure(raises: bool, capsys: pytest.CaptureFixture[str]) -> None:
    def resolver() -> None:
        if raises:
            raise RuntimeError("lookup failed")
        return None

    if raises:
        with pytest.raises(typer.Exit) as error:
            _doctor_shared.resolve_project_root_or_exit(resolver, True, allow_none=True)
        assert error.value.exit_code == 1
        captured = capsys.readouterr()
        assert json.loads(captured.out)["error"]["code"] == "not_in_project"
        assert captured.err == ""
    else:
        assert _doctor_shared.resolve_project_root_or_exit(resolver, True, allow_none=True) is None
        assert capsys.readouterr().out == ""
