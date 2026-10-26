"""#6454: ``charter context`` refuses with a coded invariant error's body, not only its code."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

import specify_cli.cli.commands.charter as charter_pkg
from charter.activation.synthesizer.reach_only import SynthesisMembershipUnreadableError
from specify_cli.cli.commands.charter import charter_app

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_BODY = "the synthesis manifest cannot be read. Remediation: restore it."


@pytest.fixture
def _refusing_context(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def _raise(*_args: object, **_kwargs: object) -> None:
        raise SynthesisMembershipUnreadableError(_BODY)

    monkeypatch.setattr(charter_pkg, "find_repo_root", lambda: tmp_path)
    monkeypatch.setattr("charter.activation.context.build_charter_context", _raise)


@pytest.mark.usefixtures("_refusing_context")
def test_context_renders_the_coded_error_body() -> None:
    result = CliRunner().invoke(charter_app, ["context", "--action", "implement"])

    assert result.exit_code == 1
    assert "SYNTHESIS_MEMBERSHIP_UNREADABLE" in result.output
    assert "Remediation: restore it." in result.output
    assert "Unexpected" not in result.output


@pytest.mark.usefixtures("_refusing_context")
def test_context_json_carries_the_code_and_body() -> None:
    result = CliRunner().invoke(charter_app, ["context", "--action", "implement", "--json"])

    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["code"] == "SYNTHESIS_MEMBERSHIP_UNREADABLE"
    assert _BODY in json.dumps(payload)
