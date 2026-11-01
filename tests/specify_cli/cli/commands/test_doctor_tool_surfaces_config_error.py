"""``doctor tool-surfaces`` must honour the doctor family's 0/1/2 JSON-envelope
contract on a non-mapping ``.kittify/config.yaml`` (OP-FRESH-001).

``_tool_config_or_exit`` calls ``load_agent_config``, which raises
``AgentConfigError`` for a non-mapping top-level YAML document (a bare scalar
or a list). Before this fix that call site was unguarded, so the error
propagated uncaught past ``run_tool_surfaces_audit`` as a raw exception
instead of the structured ``config_error`` envelope the sibling command
``doctor skills`` already emits (see
``test_doctor_skills.py::test_skills_json_config_errors_are_machine_parseable``,
which this test mirrors).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

import specify_cli.cli.commands._command_surface_doctor as surface_doctor_mod
from specify_cli.cli.commands.doctor import app

pytestmark = [pytest.mark.unit, pytest.mark.fast]

runner = CliRunner()


def _write_non_mapping_config(repo_root: Path) -> None:
    """Write a ``.kittify/config.yaml`` whose top-level YAML is a bare scalar.

    Parses without a YAML syntax error but is not a ``dict``, so
    ``load_agent_config`` raises ``AgentConfigError`` for an invalid config
    *shape* (as opposed to a YAML *syntax* error, which the sibling
    ``doctor skills`` config_error test already covers).
    """
    kittify = repo_root / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    (kittify / "config.yaml").write_text("just a bare scalar\n", encoding="utf-8")


def test_tool_surfaces_json_config_error_is_machine_parseable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_non_mapping_config(tmp_path)
    monkeypatch.setattr(surface_doctor_mod, "locate_project_root", lambda: tmp_path)

    result = runner.invoke(app, ["tool-surfaces", "--json"])

    assert result.exit_code == 2, result.output
    payload = json.loads(result.output)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "config_error"
    assert result.stderr == ""
