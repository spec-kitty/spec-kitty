"""Issue #4242: every ``doctor`` subcommand that accepts ``--json`` must keep
stdout machine-consumable on the not-in-project error path.

The success path of these commands emits a well-formed JSON object on stdout,
but the not-in-project guard historically printed the human prose
``Error: Not in a spec-kitty project`` on stdout regardless of ``--json`` — so
``doctor <cmd> --json | jq`` got a parse error it could not distinguish from a
crash. The ``skills`` subcommand already routes this path through the shared
``_json_error`` helper and is the fix exemplar (its envelope is frozen by
``test_doctor_skills_not_in_project_envelope_frozen``).

This is a class-closing gate. The defect spans the whole ``doctor`` command
family, not just the seven subcommands named in the issue — including siblings
that live in separate modules (``provenance``, ``env-file``, ``coordination``,
``command-files``). All of them now route their not-in-project guard through the
single canonical renderer ``_doctor_shared._emit_not_in_project``. The seam that
resolves the project root is bound per-module, so each command is exercised by
patching ``locate_project_root`` in the module that actually owns it.

``mission-state`` is special: a *returned* ``None`` is a valid fixtures-only
state it forwards rather than an error, so it is absent from the ``None``-path
matrix; but a *raised* locate IS a genuine not-in-project error, so it must
honor ``--json`` too — covered by the raise-path matrix.
"""

from __future__ import annotations

import json

import pytest
from click.testing import Result
from typer.testing import CliRunner

import specify_cli.cli.commands._command_surface_doctor as cmdsurf_mod
import specify_cli.cli.commands._coordination_doctor as coord_mod
import specify_cli.cli.commands._env_file_doctor as env_mod
import specify_cli.cli.commands._provenance_doctor as prov_mod
import specify_cli.cli.commands.doctor as doctor_mod
from specify_cli.cli.commands.doctor import app

pytestmark = [pytest.mark.unit, pytest.mark.fast]

runner = CliRunner()


# (command-name, module that owns the ``locate_project_root`` seam, exit code)
_NONE_PATH_COMMANDS: list[tuple[str, object, int]] = [
    # The seven enumerated in the issue.
    ("state-roots", doctor_mod, 1),
    ("workspaces", doctor_mod, 1),
    ("identity", doctor_mod, 1),
    ("topology", doctor_mod, 1),
    ("mission-type", doctor_mod, 1),
    ("shim-registry", doctor_mod, 2),
    ("contracts", doctor_mod, 2),
    # Same defect class in doctor.py — closed together.
    ("invocation-pairing", doctor_mod, 1),
    ("ops", doctor_mod, 1),
    ("doctrine", doctor_mod, 1),
    ("cutover", doctor_mod, 1),
    ("review-cycle-reconcile", doctor_mod, 1),
    # Same defect class in sibling modules — each owns its own locate seam.
    ("command-files", cmdsurf_mod, 1),
    ("provenance", prov_mod, 1),
    ("env-file", env_mod, 1),
    ("coordination", coord_mod, 1),
]

# ``mission-state`` forwards a returned ``None`` as a valid fixtures-only state,
# so it only belongs to the raise-path matrix (its locate seam is doctor.py's).
_RAISE_PATH_COMMANDS: list[tuple[str, object, int]] = [
    *_NONE_PATH_COMMANDS,
    ("mission-state", doctor_mod, 1),
]


def _assert_json_not_in_project(result: Result, exit_code: int) -> None:
    assert result.exit_code == exit_code, result.output
    payload = json.loads(result.output)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "not_in_project"
    assert payload["error"]["message"] == "Not in a spec-kitty project"


@pytest.mark.parametrize("command,module,exit_code", _NONE_PATH_COMMANDS)
def test_json_not_in_project_emits_json_on_stdout(command: str, module: object, exit_code: int, monkeypatch: pytest.MonkeyPatch) -> None:
    """``doctor <cmd> --json`` outside a project emits a JSON error object, not prose."""
    monkeypatch.setattr(module, "locate_project_root", lambda *a, **k: None)

    result = runner.invoke(app, [command, "--json"])

    _assert_json_not_in_project(result, exit_code)


@pytest.mark.parametrize("command,module,exit_code", _RAISE_PATH_COMMANDS)
def test_json_not_in_project_on_locate_raise(command: str, module: object, exit_code: int, monkeypatch: pytest.MonkeyPatch) -> None:
    """The JSON contract also holds when ``locate_project_root`` raises."""

    def _boom(*_a: object, **_k: object) -> None:
        raise RuntimeError("no repo here")

    monkeypatch.setattr(module, "locate_project_root", _boom)

    result = runner.invoke(app, [command, "--json"])

    _assert_json_not_in_project(result, exit_code)


@pytest.mark.parametrize("command,module,exit_code", _NONE_PATH_COMMANDS)
def test_non_json_not_in_project_still_prints_prose(command: str, module: object, exit_code: int, monkeypatch: pytest.MonkeyPatch) -> None:
    """The human (non-``--json``) path keeps its Rich prose + exit code."""
    monkeypatch.setattr(module, "locate_project_root", lambda *a, **k: None)

    result = runner.invoke(app, [command])

    assert result.exit_code == exit_code, result.output
    assert "Not in a spec-kitty project" in result.output
