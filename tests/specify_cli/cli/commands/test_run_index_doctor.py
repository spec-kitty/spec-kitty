"""Tests for ``spec-kitty doctor run-index`` and its doctor.py auto-discovery
(mission runindex-feature-runs-port, #5390)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

import specify_cli.cli.commands.doctor as doctor_module
from runtime.next import run_index
from specify_cli.cli.commands import _run_index_doctor

pytestmark = [pytest.mark.fast]

runner = CliRunner()


def _write_index(repo: Path, index: dict) -> None:
    path = run_index.feature_runs_path(repo)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(index), encoding="utf-8")


def test_run_index_is_registered_on_doctor_app_without_hand_wiring() -> None:
    names = {cmd.name for cmd in doctor_module.app.registered_commands}
    assert "run-index" in names


def test_register_is_idempotent_safe_to_call_directly() -> None:
    scratch_app = typer.Typer()
    _run_index_doctor.register(scratch_app)
    names = [cmd.name for cmd in scratch_app.registered_commands]
    assert names == ["run-index"]


def test_no_leaks_exits_zero(tmp_path: Path) -> None:
    _write_index(tmp_path, {"01A": {"run_id": "r1", "run_dir": ".kittify/runtime/runs/r1"}})
    with pytest.raises(typer.Exit) as exc:
        _run_index_doctor._run_index_audit(tmp_path, json_output=False)
    assert exc.value.exit_code == 0


def test_absolute_leak_exits_one(tmp_path: Path) -> None:
    _write_index(tmp_path, {"01A": {"run_id": "r1", "run_dir": "/orig/.kittify/runtime/runs/r1"}})
    with pytest.raises(typer.Exit) as exc:
        _run_index_doctor._run_index_audit(tmp_path, json_output=False)
    assert exc.value.exit_code == 1


def test_json_output_shape(tmp_path: Path) -> None:
    _write_index(tmp_path, {"01A": {"run_id": "r1", "run_dir": "/orig/.kittify/runtime/runs/r1"}})
    with pytest.raises(typer.Exit) as exc:
        _run_index_doctor._run_index_audit(tmp_path, json_output=True)
    assert exc.value.exit_code == 1


def test_doctor_run_index_via_cli_runner(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_index(tmp_path, {"01A": {"run_id": "r1", "run_dir": "/orig/.kittify/runtime/runs/r1"}})
    monkeypatch.setattr(
        "specify_cli.cli.commands._run_index_doctor.locate_project_root",
        lambda *a, **k: tmp_path,
    )
    result = runner.invoke(doctor_module.app, ["run-index", "--json"])
    assert result.exit_code == 1
    assert "run_dir" in result.stdout
