"""``spec-kitty charter consistency-check`` (#3732, FR-006, OD-8).

The command checks the active charter, so it moved from ``charter pack`` to the
top of the ``charter`` group; ``charter pack consistency-check`` is gone (no
alias, C-001). Flags and the ``--json`` shape are unchanged.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from charter.activation.consistency_check import run_consistency_check
from charter.activation.invocation_context import ProjectContext
from specify_cli.cli.commands.charter._app import charter_app

pytestmark = [pytest.mark.unit]

runner = CliRunner()

_REAL_DIRECTIVE_ID = "001-architectural-integrity-standard"


def _project(tmp_path: Path, directive_id: str) -> Path:
    kittify = tmp_path / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    (kittify / "config.yaml").write_text(
        f"activated_directives:\n  - {directive_id}\nmission_type_activations:\n  - software-dev\n",
        encoding="utf-8",
    )
    return tmp_path


def test_coherent_charter_exits_0(tmp_path: Path) -> None:
    root = _project(tmp_path, _REAL_DIRECTIVE_ID)
    result = runner.invoke(charter_app, ["consistency-check", "--repo-root", str(root)])
    assert result.exit_code == 0, result.output
    assert "Active charter is coherent." in result.output


def test_incoherent_charter_exits_1_naming_the_reference(tmp_path: Path) -> None:
    root = _project(tmp_path, "totally-fake-directive-zzz")
    result = runner.invoke(charter_app, ["consistency-check", "--repo-root", str(root)])
    assert result.exit_code == 1, result.output
    assert "Consistency issues found" in result.output
    assert "totally-fake-directive-zzz" in result.output


def test_json_shape_is_the_report(tmp_path: Path) -> None:
    root = _project(tmp_path, _REAL_DIRECTIVE_ID)
    result = runner.invoke(charter_app, ["consistency-check", "--json", "--repo-root", str(root)])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    expected = json.loads(run_consistency_check(ProjectContext.from_repo(root)).to_json())
    assert sorted(payload) == sorted(expected)
    assert payload["coherent"] is True


def test_pack_spelling_is_not_registered(tmp_path: Path) -> None:
    root = _project(tmp_path, _REAL_DIRECTIVE_ID)
    old = runner.invoke(charter_app, ["pack", "consistency-check", "--repo-root", str(root)])
    assert old.exit_code == 2, old.output
    assert "No such command" in old.output
    # Control: the new spelling runs on the same fixture.
    assert runner.invoke(charter_app, ["consistency-check", "--repo-root", str(root)]).exit_code == 0
